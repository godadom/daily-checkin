"""Fail-closed state machine for NovalPie's verified daily check-in API."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .auth import AuthProvider, build_auth_provider
from .client import HttpResponse, NetworkError, ReliableHttpClient, ResponseTooLarge, is_html_response, is_security_challenge
from .config import Settings
from .models import AccountConfig, CheckinResult, CheckinStatus


class CheckinService:
    ALREADY_MARKERS = ("今天已经签到过了", "already checked")
    AUTH_MARKERS = ("unauthorized", "authentication", "未登录", "登录失效")
    ACCESS_MARKERS = ("access denied", "permission denied", "forbidden", "无权", "权限")

    def __init__(
        self,
        settings: Settings,
        client: ReliableHttpClient,
        auth_provider_factory: Callable[[AccountConfig], AuthProvider] = build_auth_provider,
        date_provider: Callable[[], str] | None = None,
    ):
        self.settings = settings
        self.client = client
        self.auth_provider_factory = auth_provider_factory
        self.auth_providers = {account: auth_provider_factory(account) for account in settings.accounts}
        self.date_provider = date_provider or (lambda: datetime.now(ZoneInfo(settings.timezone)).date().isoformat())

    def _auth(self, account: AccountConfig) -> AuthProvider:
        provider = self.auth_providers.get(account)
        if provider is None:
            provider = self.auth_provider_factory(account)
            self.auth_providers[account] = provider
        return provider

    def _headers(self, account: AccountConfig) -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": self.settings.user_agent, **self._auth(account).headers()}

    def _request(self, account: AccountConfig, method: str, url: str) -> HttpResponse:
        response = self.client.request(method, url, self._headers(account))
        self._auth(account).observe(response)
        return response

    @staticmethod
    def _payload(response: HttpResponse) -> Mapping[str, Any] | None:
        try:
            value = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _message(payload: Mapping[str, Any] | None) -> str:
        value = payload.get("message") if payload else None
        return value.casefold() if isinstance(value, str) else ""

    @classmethod
    def _contains(cls, message: str, markers: tuple[str, ...]) -> bool:
        return any(marker.casefold() in message for marker in markers)

    def _error_result(self, account: AccountConfig, response: HttpResponse, payload: Mapping[str, Any] | None, stage: str) -> CheckinResult | None:
        if is_security_challenge(response):
            return CheckinResult(account.name, CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE, "manual security challenge required")
        message = self._message(payload)
        if response.status == 401 or self._contains(message, self.AUTH_MARKERS):
            return CheckinResult(account.name, CheckinStatus.AUTH_EXPIRED, "authentication rejected")
        if response.status == 403:
            if self._contains(message, self.ACCESS_MARKERS):
                return CheckinResult(account.name, CheckinStatus.ACCESS_DENIED, "server denied account permission; do not retry or bypass")
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "unclassified HTTP 403; review sanitized evidence")
        if is_html_response(response) or payload is None:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, f"{stage} response schema changed")
        return None

    @staticmethod
    def _record_valid(record: object) -> bool:
        if not isinstance(record, dict):
            return False
        required = {"points", "streak", "time"}
        if not required.issubset(record):
            return False
        return (
            isinstance(record["points"], (int, float))
            and not isinstance(record["points"], bool)
            and isinstance(record["streak"], (int, float))
            and not isinstance(record["streak"], bool)
            and isinstance(record["time"], str)
        )

    def _status_url(self, day: str) -> str:
        query = urlencode({"start_date": day, "end_date": day})
        return f"{self.settings.base_url}{self.settings.status_path}?{query}"

    def _query(self, account: AccountConfig) -> tuple[CheckinResult | None, bool]:
        day = self.date_provider()
        try:
            response = self._request(account, "GET", self._status_url(day))
        except ResponseTooLarge:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "status response exceeded the safe size limit"), False
        except NetworkError as exc:
            return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, "status query timed out or failed", attempts=exc.attempts), False
        payload = self._payload(response)
        error = self._error_result(account, response, payload, "status")
        if error:
            return error, False
        if response.status == 429 or response.status >= 500:
            return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, f"status endpoint returned HTTP {response.status}", attempts=response.attempts), False
        if response.status != 200 or payload.get("success") is not True:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "unexpected status response"), False
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("records"), dict) or not isinstance(data.get("today_checked"), bool):
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "status response schema changed"), False
        checked = data["today_checked"]
        record = data["records"].get(day)
        if checked and not self._record_valid(record):
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "today's attendance record schema changed"), False
        if not checked and record is not None:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "status response is internally inconsistent"), False
        if checked:
            return CheckinResult(account.name, CheckinStatus.ALREADY_DONE, "already checked in today"), True
        return None, False

    def _confirm_after_post(self, account: AccountConfig, details: Mapping[str, Any] | None = None) -> CheckinResult:
        result, checked = self._query(account)
        if checked:
            return CheckinResult(account.name, CheckinStatus.SUCCESS, "check-in confirmed by today's attendance record", details or {})
        if result and result.status in {
            CheckinStatus.AUTH_EXPIRED,
            CheckinStatus.ACCESS_DENIED,
            CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE,
            CheckinStatus.SITE_CHANGED,
        }:
            return result
        return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, "check-in outcome is not confirmed; POST was not repeated")

    def check_in(self, account: AccountConfig) -> CheckinResult:
        before, _ = self._query(account)
        if before:
            return before
        try:
            response = self._request(account, "POST", self.settings.base_url + self.settings.checkin_path)
        except ResponseTooLarge:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "check-in response exceeded the safe size limit")
        except NetworkError:
            return self._confirm_after_post(account)
        payload = self._payload(response)
        error = self._error_result(account, response, payload, "check-in")
        if error:
            return error
        message = self._message(payload)
        if response.status in {400, 409} and self._contains(message, self.ALREADY_MARKERS):
            return CheckinResult(account.name, CheckinStatus.ALREADY_DONE, "already checked in today")
        if response.status == 429:
            delay = self.client.retry_delay(response)
            if delay is None:
                return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, "rate-limit window exceeds the safe wait cap; POST was not repeated", attempts=response.attempts)
            self.client.sleep(delay)
            return self._confirm_after_post(account)
        if response.status >= 500:
            if any(key.casefold() == "retry-after" for key in response.headers):
                delay = self.client.retry_delay(response)
                if delay is None:
                    return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, "server wait window exceeds the safe cap; POST was not repeated", attempts=response.attempts)
                self.client.sleep(delay)
            return self._confirm_after_post(account)
        if response.status != 200 or payload.get("success") is not True:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, f"unexpected check-in HTTP {response.status}")
        details: dict[str, int | float] = {}
        points = payload.get("points")
        if isinstance(points, (int, float)) and not isinstance(points, bool):
            details["points"] = points
        return self._confirm_after_post(account, details)
