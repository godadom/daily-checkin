"""Fail-closed state machine for NodeSeek's verified attendance API."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .auth import authentication_headers
from .client import HttpResponse, NetworkError, ReliableHttpClient, ResponseTooLarge, is_html_response, is_security_challenge
from .config import Settings
from .models import AccountConfig, CheckinResult, CheckinStatus


class CheckinService:
    AUTH_ERROR_CODES = {"auth_expired", "invalid_session", "unauthorized"}
    ACCESS_DENIED_CODES = {"access_denied", "forbidden", "permission_denied"}

    def __init__(self, settings: Settings, client: ReliableHttpClient):
        self.settings = settings
        self.client = client

    def _headers(self, account: AccountConfig) -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": self.settings.user_agent, **authentication_headers(account)}

    @staticmethod
    def _payload(response: HttpResponse) -> Mapping[str, Any] | None:
        try:
            value = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _classify_common(self, account: AccountConfig, response: HttpResponse, payload: Mapping[str, Any] | None, stage: str) -> CheckinResult | None:
        if is_security_challenge(response):
            return CheckinResult(account.name, CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE, "manual security challenge required")
        code = payload.get("code") if payload else None
        if response.status == 401 or code in self.AUTH_ERROR_CODES:
            return CheckinResult(account.name, CheckinStatus.AUTH_EXPIRED, "authentication rejected")
        if response.status == 403:
            if code in self.ACCESS_DENIED_CODES:
                return CheckinResult(account.name, CheckinStatus.ACCESS_DENIED, "server denied account permission; do not retry or bypass")
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "unclassified HTTP 403; review sanitized evidence")
        if is_html_response(response) or payload is None:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, f"{stage} response schema changed")
        if response.status == 429 or response.status >= 500:
            return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, f"{stage} endpoint returned HTTP {response.status}", attempts=response.attempts)
        return None

    @staticmethod
    def _attendance_record(payload: Mapping[str, Any]) -> bool | None:
        if set(payload) - {"list", "record", "order", "total"}:
            return None
        record = payload.get("record")
        if record is None:
            return False
        if not isinstance(record, dict):
            return None
        required = {"id", "member_id", "day_id", "gain", "created_at"}
        if set(record) != required or not all(isinstance(record[key], (int, float)) and not isinstance(record[key], bool) for key in ("id", "member_id", "day_id", "gain")) or not isinstance(record["created_at"], str):
            return None
        return True

    def _query(self, account: AccountConfig) -> tuple[CheckinResult | None, bool | None]:
        try:
            response = self.client.request("GET", self.settings.base_url + self.settings.status_path, self._headers(account))
        except ResponseTooLarge:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "status response exceeded the safe size limit"), None
        except NetworkError as exc:
            return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, "status query timed out or failed", attempts=exc.attempts), None
        payload = self._payload(response)
        common = self._classify_common(account, response, payload, "status")
        if common:
            return common, None
        if response.status != 200:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, f"unexpected status HTTP {response.status}"), None
        checked = self._attendance_record(payload or {})
        if checked is None:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "attendance status response schema changed"), None
        if checked:
            return CheckinResult(account.name, CheckinStatus.ALREADY_DONE, "already checked in today"), True
        return None, False

    def _confirm_ambiguous_post(self, account: AccountConfig) -> CheckinResult:
        result, checked = self._query(account)
        if checked:
            return CheckinResult(account.name, CheckinStatus.SUCCESS, "check-in confirmed after an ambiguous response")
        if result and result.status in {CheckinStatus.AUTH_EXPIRED, CheckinStatus.ACCESS_DENIED, CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE, CheckinStatus.SITE_CHANGED}:
            return result
        return CheckinResult(account.name, CheckinStatus.TEMPORARY_ERROR, "check-in outcome is not confirmed; POST was not repeated")

    def check_in(self, account: AccountConfig) -> CheckinResult:
        before, _ = self._query(account)
        if before:
            return before
        try:
            response = self.client.request("POST", self.settings.base_url + self.settings.checkin_path, self._headers(account))
        except ResponseTooLarge:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "check-in response exceeded the safe size limit")
        except NetworkError:
            return self._confirm_ambiguous_post(account)
        payload = self._payload(response)
        common = self._classify_common(account, response, payload, "check-in")
        if common:
            if common.status is CheckinStatus.TEMPORARY_ERROR:
                return self._confirm_ambiguous_post(account)
            return common
        if response.status != 200 or not payload:
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, f"unexpected check-in HTTP {response.status}")
        if payload.get("success") is not True or not isinstance(payload.get("message"), str) or isinstance(payload.get("gain"), bool) or not isinstance(payload.get("gain"), (int, float)) or isinstance(payload.get("current"), bool) or not isinstance(payload.get("current"), (int, float)):
            return CheckinResult(account.name, CheckinStatus.SITE_CHANGED, "check-in response schema changed")
        return CheckinResult(account.name, CheckinStatus.SUCCESS, "check-in succeeded", {"gain": payload["gain"]})
