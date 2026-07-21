from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def deny_live_network(*args, **kwargs):
    raise AssertionError("offline tests must not open sockets")


socket.create_connection = deny_live_network

from checkin.client import HttpResponse, ReliableHttpClient  # noqa: E402
from checkin.config import Settings  # noqa: E402
from checkin.models import AccountConfig  # noqa: E402
from checkin.service import CheckinService  # noqa: E402
from checkin.site_config import ACTION_PATH, BASE_URL, STATUS_PATH  # noqa: E402


class QueueTransport:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def request(self, method, url, headers, body, connect_timeout, read_timeout):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body, "timeouts": (connect_timeout, read_timeout)})
        if not self.outcomes:
            raise AssertionError("unexpected mock request")
        result = self.outcomes.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def response(payload, status=200, headers=None):
    return HttpResponse(status, headers or {"Content-Type": "application/json"}, json.dumps(payload).encode())


def account(name="alice", secret="session=fixture-cookie"):
    return AccountConfig(name, "cookie", secret)


def settings(accounts=None, attendance_mode="fixed"):
    path = "/api/attendance?random=true" if attendance_mode == "random" else ACTION_PATH
    return Settings(BASE_URL, STATUS_PATH, path, attendance_mode, tuple(accounts or [account()]), max_retries=2)


def service(*outcomes):
    transport = QueueTransport(*outcomes)
    return CheckinService(settings(), ReliableHttpClient(transport, max_retries=2, sleeper=lambda _: None)), transport


def unchecked():
    return response({"list": [], "record": None, "order": 0, "total": 0})


def checked():
    return response({"list": [], "record": {"id": 1, "member_id": 2, "day_id": 3, "gain": 5, "created_at": "2026-07-17T00:00:00Z"}, "order": 1, "total": 1})
