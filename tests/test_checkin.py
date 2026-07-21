from __future__ import annotations

import unittest

from helpers import account, checked, response, service, settings, unchecked
from checkin.client import HttpResponse
from checkin.models import CheckinStatus, RunSummary


class CheckinTests(unittest.TestCase):
    def test_success_uses_verified_get_then_single_post(self):
        worker, transport = service(unchecked(), response({"success": True, "message": "fixture success", "gain": 5, "current": 99}))
        result = worker.check_in(account())
        self.assertEqual(result.status, CheckinStatus.SUCCESS)
        self.assertEqual(result.details, {"gain": 5})
        self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST"])
        self.assertTrue(transport.calls[1]["url"].endswith("/api/attendance?random=false"))
        self.assertNotIn("fixture-cookie", str(result))

    def test_checked_record_skips_post(self):
        worker, transport = service(checked())
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.ALREADY_DONE)
        self.assertEqual([call["method"] for call in transport.calls], ["GET"])

    def test_random_mode_uses_the_verified_true_query(self):
        worker, transport = service(unchecked(), response({"success": True, "message": "fixture", "gain": 7, "current": 7}))
        worker.settings = settings(attendance_mode="random")
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SUCCESS)
        self.assertTrue(transport.calls[1]["url"].endswith("/api/attendance?random=true"))

    def test_ambiguous_post_is_confirmed_without_repeating(self):
        worker, transport = service(unchecked(), TimeoutError(), checked())
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SUCCESS)
        self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST", "GET"])

    def test_schema_auth_and_challenge_fail_closed(self):
        cases = (
            (response({"list": [], "record": "bad", "order": 0, "total": 0}), CheckinStatus.SITE_CHANGED),
            (response({"error": "expired"}, 401), CheckinStatus.AUTH_EXPIRED),
            (HttpResponse(403, {"Content-Type": "text/html", "CF-Mitigated": "challenge"}, b"<html>Just a moment</html>"), CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE),
        )
        for outcome, expected in cases:
            with self.subTest(expected=expected):
                worker, _ = service(outcome)
                self.assertEqual(worker.check_in(account()).status, expected)

    def test_403_requires_business_evidence_for_access_denied(self):
        cases = (
            (response({"code": "permission_denied"}, 403), CheckinStatus.ACCESS_DENIED),
            (response({"code": "auth_expired"}, 403), CheckinStatus.AUTH_EXPIRED),
            (response({"code": "unknown"}, 403), CheckinStatus.SITE_CHANGED),
            (HttpResponse(403, {"Content-Type": "text/html", "CF-Mitigated": "challenge"}, b"<html>Just a moment</html>"), CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE),
        )
        for outcome, expected in cases:
            with self.subTest(expected=expected):
                worker, _ = service(outcome)
                self.assertEqual(worker.check_in(account()).status, expected)

    def test_exit_codes(self):
        self.assertEqual(RunSummary.from_results([]).exit_code, 0)
        expected = {
            CheckinStatus.CONFIG_ERROR: 2,
            CheckinStatus.AUTH_EXPIRED: 3,
            CheckinStatus.TEMPORARY_ERROR: 4,
            CheckinStatus.SITE_CHANGED: 5,
            CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE: 6,
            CheckinStatus.ACCESS_DENIED: 7,
            CheckinStatus.INTERNAL_ERROR: 70,
        }
        for status, exit_code in expected.items():
            with self.subTest(status=status):
                self.assertEqual(RunSummary.from_results([worker_result(status)]).exit_code, exit_code)
        mixed = [worker_result(status) for status in expected]
        self.assertEqual(RunSummary.from_results(mixed).exit_code, 7)


def worker_result(status):
    from checkin.models import CheckinResult
    return CheckinResult("fixture", status, "fixture")
