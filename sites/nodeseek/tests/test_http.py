from __future__ import annotations

import unittest
import socket

from helpers import deny_live_network, response, service
from checkin.client import HttpResponse, ReliableHttpClient
from checkin.models import CheckinStatus


class HttpTests(unittest.TestCase):
    def test_network_guard_blocks_live_requests(self):
        self.assertIs(socket.create_connection, deny_live_network)

    def test_get_retries_are_bounded(self):
        worker, transport = service(TimeoutError(), TimeoutError(), TimeoutError())
        self.assertEqual(worker.check_in(worker.settings.accounts[0]).status, CheckinStatus.TEMPORARY_ERROR)
        self.assertEqual(len(transport.calls), 3)

    def test_post_429_queries_status_without_second_post(self):
        worker, transport = service(response({"list": [], "record": None, "order": 0, "total": 0}), response({"busy": True}, 429), response({"list": [], "record": None, "order": 0, "total": 0}))
        self.assertEqual(worker.check_in(worker.settings.accounts[0]).status, CheckinStatus.TEMPORARY_ERROR)
        self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST", "GET"])

    def test_html_response_stops_without_retry(self):
        worker, _ = service(HttpResponse(200, {"Content-Type": "text/html"}, b"<html>login</html>"))
        self.assertEqual(worker.check_in(worker.settings.accounts[0]).status, CheckinStatus.SITE_CHANGED)

    def test_5xx_post_is_confirmed_once_without_repeating(self):
        worker, transport = service(response({"list": [], "record": None, "order": 0, "total": 0}), response({"busy": True}, 503), response({"list": [], "record": None, "order": 0, "total": 0}))
        self.assertEqual(worker.check_in(worker.settings.accounts[0]).status, CheckinStatus.TEMPORARY_ERROR)
        self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST", "GET"])

    def test_csrf_is_not_invented_for_verified_contract(self):
        worker, transport = service(response({"list": [], "record": None, "order": 0, "total": 0}), response({"success": True, "message": "fixture", "gain": 5, "current": 5}))
        worker.check_in(worker.settings.accounts[0])
        self.assertNotIn("X-CSRF-Token", transport.calls[1]["headers"])

    def test_retry_after_is_bounded(self):
        delays = []
        client = ReliableHttpClient(type("T", (), {"request": lambda self, *args: response({"retry": True}, 429, {"Retry-After": "7"})})(), max_retries=1, sleeper=delays.append)
        client.request("GET", "https://example.invalid/", {})
        self.assertEqual(delays, [7.0])
