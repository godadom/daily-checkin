"""Runtime configuration for NovalPie's verified check-in API."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import AccountConfig


class ConfigError(ValueError):
    """Raised for actionable configuration errors that never reveal tokens."""


ACCOUNT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PHONE_ALIAS_RE = re.compile(r"^(?:1[3-9]\d{9}|\d{10,15})$")
FIELD_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TIMEZONE_RE = re.compile(r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$")
BASE_URL = "https://novalpie.cc"
STATUS_PATH = "/api/users/me/checkins"
ACTION_PATH = "/api/users/me/checkins"


@dataclass(frozen=True)
class Settings:
    base_url: str
    status_path: str
    checkin_path: str
    accounts: tuple[AccountConfig, ...]
    connect_timeout: float = 5.0
    read_timeout: float = 15.0
    max_retries: int = 2
    jitter_max_seconds: int = 0
    timezone: str = "Asia/Shanghai"
    notify_mode: str = "log"
    user_agent: str = "novalpie-checkin/1.0 (+authorized-automation)"


def _number(env: Mapping[str, str], name: str, default: str, kind: type, minimum: float, maximum: float) -> int | float:
    try:
        value = kind(env.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a valid {kind.__name__}") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def _token(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("each account requires a non-empty token")
    token = value.strip()
    if token.casefold().startswith("bearer "):
        raise ConfigError("provide only the token value, without the Bearer prefix")
    if len(token) > 16_384 or any(ord(character) < 32 or ord(character) == 127 for character in token):
        raise ConfigError("account token contains unsupported control characters or is too long")
    return token


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or not ACCOUNT_NAME_RE.fullmatch(value) or PHONE_ALIAS_RE.fullmatch(value):
        raise ConfigError(f"{label} must be a non-sensitive 1-64 character alias")
    return value


def _account(item: object, index: int) -> AccountConfig:
    if not isinstance(item, dict) or set(item) - {"name", "token", "sensitive_fields"}:
        raise ConfigError(f"CHECKIN_ACCOUNTS item {index} must contain only name, token, and optional sensitive_fields")
    name = _name(item.get("name"), f"CHECKIN_ACCOUNTS item {index} name")
    fields = item.get("sensitive_fields", [])
    if (
        not isinstance(fields, list)
        or len(fields) > 32
        or not all(isinstance(field, str) and FIELD_NAME_RE.fullmatch(field) for field in fields)
    ):
        raise ConfigError(f"account {name!r} sensitive_fields must contain at most 32 safe field names")
    return AccountConfig(name, "bearer", _token(item.get("token")), sensitive_fields=tuple(fields))


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
        name = _name(env.get("CHECKIN_ACCOUNT_NAME", "default"), "CHECKIN_ACCOUNT_NAME")
        accounts = (AccountConfig(name, "bearer", _token(env.get("CHECKIN_TOKEN"))),)
    names = [account.name.casefold() for account in accounts]
    if len(names) != len(set(names)):
        raise ConfigError("account names must be unique")
    return accounts


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
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
    return Settings(
        base_url=BASE_URL,
        status_path=STATUS_PATH,
        checkin_path=ACTION_PATH,
        accounts=_accounts(env),
        connect_timeout=float(_number(env, "CHECKIN_CONNECT_TIMEOUT", "5", float, 0.1, 120)),
        read_timeout=float(_number(env, "CHECKIN_READ_TIMEOUT", "15", float, 0.1, 120)),
        max_retries=int(_number(env, "CHECKIN_MAX_RETRIES", "2", int, 0, 5)),
        jitter_max_seconds=int(_number(env, "CHECKIN_JITTER_MAX_SECONDS", "0", int, 0, 900)),
        timezone=timezone,
        notify_mode=notify_mode,
    )
