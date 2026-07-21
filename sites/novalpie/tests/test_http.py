from __future__ import annotations

import socket
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from helpers import QueueTransport, account, deny_live_network, fixture, response, service
from checkin.client import MAX_RESPONSE_BYTES, HttpResponse, ReliableHttpClient, ResponseTooLarge, read_bounded
from checkin.models import CheckinStatus


class HttpReliabilityTests(unittest.TestCase):
    def test_global_socket_guard_blocks_accidental_live_network(self):
        self.assertIs(socket.create_connection, deny_live_network)
        with self.assertRaisesRegex(AssertionError, "must not open sockets"):
            deny_live_network()

    def test_response_body_cap_is_a_site_change_without_retry(self):
        class OversizedResponse:
            def read(self, limit):
                self.limit = limit
                return b"x" * limit

        source = OversizedResponse()
        with self.assertRaises(ResponseTooLarge):
            read_bounded(source)
        self.assertEqual(source.limit, MAX_RESPONSE_BYTES + 1)
        worker, transport = service(ResponseTooLarge("fixture"))
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SITE_CHANGED)
        self.assertEqual(len(transport.calls), 1)

    def test_get_timeout_429_and_5xx_use_only_bounded_safe_retries(self):
        cases = (
            (TimeoutError(), TimeoutError(), TimeoutError()),
            (response({"success": False}, 429, {"Retry-After": "0"}),) * 3,
            (response({"success": False}, 503),) * 3,
        )
        for outcomes in cases:
            with self.subTest():
                worker, transport = service(*outcomes)
                self.assertEqual(worker.check_in(account()).status, CheckinStatus.TEMPORARY_ERROR)
                self.assertEqual(len(transport.calls), 3)

    def test_security_challenge_or_markerless_html_stops_without_retry(self):
        challenge = HttpResponse(503, {"Content-Type": "text/html", "CF-Mitigated": "challenge"}, b"<html>cf-chl</html>")
        worker, transport = service(challenge)
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE)
        self.assertEqual(len(transport.calls), 1)
        changed = HttpResponse(503, {"Content-Type": "text/html"}, b"<html>maintenance</html>")
        worker, transport = service(changed)
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SITE_CHANGED)
        self.assertEqual(len(transport.calls), 1)

    def test_ambiguous_post_is_confirmed_without_repeating_post(self):
        worker, transport = service(fixture("status-unchecked.json"), TimeoutError(), fixture("status-checked.json"))
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SUCCESS)
        self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST", "GET"])

    def test_post_5xx_and_429_query_status_once_instead_of_reposting(self):
        delayed = []
        transport = QueueTransport(
            fixture("status-unchecked.json"),
            response({"success": False}, 429, {"Retry-After": "7"}),
            fixture("status-checked.json"),
        )
        worker, _ = service()
        worker.client = ReliableHttpClient(transport, max_retries=2, sleeper=delayed.append)
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SUCCESS)
        self.assertEqual(([call["method"] for call in transport.calls], delayed), (["GET", "POST", "GET"], [7.0]))
        transport = QueueTransport(fixture("status-unchecked.json"), response({"success": False}, 503), fixture("status-unchecked.json"))
        worker, _ = service()
        worker.client = ReliableHttpClient(transport, max_retries=2, sleeper=lambda _: None)
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.TEMPORARY_ERROR)
        self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST", "GET"])

    def test_retry_after_seconds_date_and_safe_cap(self):
        delays = []
        transport = QueueTransport(response({"success": False}, 429, {"Retry-After": "7"}), fixture("status-checked.json"))
        client = ReliableHttpClient(transport, max_retries=1, sleeper=delays.append)
        result = client.request("GET", "https://checkin.example.invalid/status", {})
        self.assertEqual((delays, result.attempts), ([7.0], 2))
        future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=20))
        parsed = client._retry_after({"Retry-After": future}, 1)
        self.assertGreater(parsed, 0)
        self.assertLessEqual(parsed, 60)
        self.assertIsNone(client._retry_after({"Retry-After": "120"}, 1))

    def test_request_contract_has_timeouts_honest_agent_and_no_csrf(self):
        delays = []
        transport = QueueTransport(TimeoutError(), TimeoutError(), fixture("status-checked.json"))
        client = ReliableHttpClient(transport, connect_timeout=4, read_timeout=9, max_retries=2, sleeper=delays.append)
        worker, _ = service(fixture("status-checked.json"))
        worker.client = client
        self.assertEqual(worker.check_in(account(secret="fixture-token")).status, CheckinStatus.ALREADY_DONE)
        call = transport.calls[-1]
        self.assertEqual(call["timeouts"], (4, 9))
        self.assertEqual(call["headers"]["User-Agent"], "novalpie-checkin/1.0 (+authorized-automation)")
        self.assertEqual(call["headers"]["Authorization"], "Bearer fixture-token")
        self.assertFalse(any("csrf" in key.casefold() for key in call["headers"]))


if __name__ == "__main__":
    unittest.main()
