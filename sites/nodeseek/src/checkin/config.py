"""Runtime configuration for the verified NodeSeek attendance flow."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import AccountConfig
from .site_config import ACTION_PATHS, BASE_URL, FORBIDDEN_OVERRIDE_ENV_NAMES, STATUS_PATH


class ConfigError(ValueError):
    """Raised for actionable configuration errors that do not reveal secrets."""


ACCOUNT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TIMEZONE_RE = re.compile(r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$")
@dataclass(frozen=True)
class Settings:
    base_url: str
    status_path: str
    checkin_path: str
    attendance_mode: str
    accounts: tuple[AccountConfig, ...]
    connect_timeout: float = 5.0
    read_timeout: float = 15.0
    max_retries: int = 2
    jitter_max_seconds: int = 0
    timezone: str = "Asia/Shanghai"
    notify_mode: str = "log"
    user_agent: str = "nodeseek-attendance/1.0 (+authorized-automation)"


def _number(env: Mapping[str, str], name: str, default: str, kind: type, minimum: float, maximum: float) -> int | float:
    try:
        value = kind(env.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a valid {kind.__name__}") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def _secret(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("each account requires a non-empty cookie")
    value = value.strip()
    if len(value) > 16_384 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ConfigError("account cookie contains unsupported control characters or is too long")
    return value


def _account(item: object, index: int) -> AccountConfig:
    if not isinstance(item, dict) or set(item) - {"name", "cookie", "sensitive_fields"}:
        raise ConfigError(f"CHECKIN_ACCOUNTS item {index} must contain only name, cookie, and optional sensitive_fields")
    name = item.get("name")
    if not isinstance(name, str) or not ACCOUNT_NAME_RE.fullmatch(name):
        raise ConfigError(f"CHECKIN_ACCOUNTS item {index} name must be a non-sensitive 1-64 character alias")
    fields = item.get("sensitive_fields", [])
    if not isinstance(fields, list) or not all(isinstance(field, str) and field for field in fields):
        raise ConfigError(f"account {name!r} sensitive_fields must be a list of field names")
    return AccountConfig(name, "cookie", _secret(item.get("cookie")), sensitive_fields=tuple(fields))


def _accounts(env: Mapping[str, str]) -> tuple[AccountConfig, ...]:
    raw = env.get("CHECKIN_ACCOUNTS", "").strip()
    if raw:
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"CHECKIN_ACCOUNTS must be valid JSON: {exc.msg}") from exc
        if not isinstance(items, list) or not items or len(items) > 50:
            raise ConfigError("CHECKIN_ACCOUNTS must be a JSON array with 1-50 items")
        accounts = tuple(_account(item, index) for index, item in enumerate(items))
    else:
        name = env.get("CHECKIN_ACCOUNT_NAME", "default")
        if not ACCOUNT_NAME_RE.fullmatch(name):
            raise ConfigError("CHECKIN_ACCOUNT_NAME must be a non-sensitive 1-64 character alias")
        accounts = (AccountConfig(name, "cookie", _secret(env.get("CHECKIN_COOKIE"))),)
    names = [account.name.casefold() for account in accounts]
    if len(names) != len(set(names)):
        raise ConfigError("account names must be unique")
    return accounts


def _reject_site_overrides(env: Mapping[str, str]) -> None:
    present = [name for name in FORBIDDEN_OVERRIDE_ENV_NAMES if name in env]
    if present:
        names = ", ".join(present)
        raise ConfigError(f"remove fixed site override variables: {names}; values are built into site_config.py")


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    _reject_site_overrides(env)
    timezone = env.get("CHECKIN_TIMEZONE", "Asia/Shanghai").strip()
    if not TIMEZONE_RE.fullmatch(timezone):
        raise ConfigError("CHECKIN_TIMEZONE must name an installed IANA timezone such as Asia/Shanghai")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError("CHECKIN_TIMEZONE must name an installed IANA timezone such as Asia/Shanghai") from exc
    notify_mode = env.get("CHECKIN_NOTIFY_MODE", "log").strip().lower()
    if notify_mode not in {"log", "off"}:
        raise ConfigError("CHECKIN_NOTIFY_MODE must be log or off")
    attendance_mode = env.get("CHECKIN_ATTENDANCE_MODE", "fixed").strip().lower()
    if attendance_mode not in {"fixed", "random"}:
        raise ConfigError("CHECKIN_ATTENDANCE_MODE must be fixed or random")
    return Settings(
        base_url=BASE_URL,
        status_path=STATUS_PATH,
        checkin_path=ACTION_PATHS[attendance_mode],
        attendance_mode=attendance_mode,
        accounts=_accounts(env),
        connect_timeout=float(_number(env, "CHECKIN_CONNECT_TIMEOUT", "5", float, 0.1, 120)),
        read_timeout=float(_number(env, "CHECKIN_READ_TIMEOUT", "15", float, 0.1, 120)),
        max_retries=int(_number(env, "CHECKIN_MAX_RETRIES", "2", int, 0, 5)),
        jitter_max_seconds=int(_number(env, "CHECKIN_JITTER_MAX_SECONDS", "0", int, 0, 900)),
        timezone=timezone,
        notify_mode=notify_mode,
    )
