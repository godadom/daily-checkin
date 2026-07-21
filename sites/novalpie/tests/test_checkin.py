from __future__ import annotations

import unittest
from unittest.mock import patch

from helpers import TEST_DAY, account, fixture, response, service, settings
from checkin.client import HttpResponse
from checkin.main import execute_accounts, main, run
from checkin.models import CheckinResult, CheckinStatus, RunSummary


class CheckinStateTests(unittest.TestCase):
    def test_success_uses_get_post_get_and_status_confirmation(self):
        worker, transport = service(fixture("status-unchecked.json"), fixture("checkin-success.json"), fixture("status-checked.json"))
        result = worker.check_in(account(secret="fixture-token"))
        self.assertEqual(result.status, CheckinStatus.SUCCESS)
        self.assertEqual(result.details, {"points": 5})
        self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST", "GET"])
        self.assertIn(f"start_date={TEST_DAY}&end_date={TEST_DAY}", transport.calls[0]["url"])
        self.assertEqual(transport.calls[1]["body"], None)
        self.assertEqual(transport.calls[1]["headers"]["Authorization"], "Bearer fixture-token")
        self.assertNotIn("Content-Type", transport.calls[1]["headers"])

    def test_checked_status_skips_post(self):
        worker, transport = service(fixture("status-checked.json"))
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.ALREADY_DONE)
        self.assertEqual([call["method"] for call in transport.calls], ["GET"])

    def test_observed_400_and_supported_409_already_done_require_message_evidence(self):
        for status in (400, 409):
            with self.subTest(status=status):
                worker, transport = service(
                    fixture("status-unchecked.json"),
                    response({"success": False, "message": "今天已经签到过了"}, status),
                )
                self.assertEqual(worker.check_in(account()).status, CheckinStatus.ALREADY_DONE)
                self.assertEqual([call["method"] for call in transport.calls], ["GET", "POST"])
        worker, _ = service(fixture("status-unchecked.json"), response({"success": False, "message": "bad request"}, 400))
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SITE_CHANGED)

    def test_auth_permission_challenge_and_unknown_403_fail_closed(self):
        cases = (
            (response({"success": False, "message": "unauthorized"}, 401), CheckinStatus.AUTH_EXPIRED),
            (response({"success": False, "message": "permission denied"}, 403), CheckinStatus.ACCESS_DENIED),
            (response({"success": False, "message": "unknown"}, 403), CheckinStatus.SITE_CHANGED),
            (HttpResponse(403, {"Content-Type": "text/html", "CF-Mitigated": "challenge"}, b"<html>Just a moment</html>"), CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE),
        )
        for outcome, expected in cases:
            with self.subTest(expected=expected):
                worker, _ = service(outcome)
                self.assertEqual(worker.check_in(account()).status, expected)

    def test_changed_or_inconsistent_status_schema_is_not_success(self):
        cases = (
            fixture("schema-changed.json"),
            response({"success": True, "data": {"today_checked": True, "records": {}}}),
            response({"success": True, "data": {"today_checked": False, "records": {TEST_DAY: {"points": 5, "streak": 1, "time": "fixture"}}}}),
        )
        for outcome in cases:
            with self.subTest():
                worker, _ = service(outcome)
                self.assertEqual(worker.check_in(account()).status, CheckinStatus.SITE_CHANGED)

    def test_html_login_page_and_redirect_are_not_success(self):
        worker, _ = service(HttpResponse(200, {"Content-Type": "text/html"}, b"<html>login</html>"))
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SITE_CHANGED)
        worker, transport = service(HttpResponse(302, {"Location": "https://other.example.invalid/login"}, b""))
        self.assertEqual(worker.check_in(account()).status, CheckinStatus.SITE_CHANGED)
        self.assertEqual(len(transport.calls), 1)

    def test_partial_accounts_continue_and_exit_codes_are_stable(self):
        accounts = [account("one"), account("two"), account("three")]

        def runner(item):
            if item.name == "two":
                raise RuntimeError("fixture failure")
            return CheckinResult(item.name, CheckinStatus.SUCCESS, "ok")

        summary = execute_accounts(accounts, runner)
        self.assertEqual([result.status for result in summary.results], [CheckinStatus.SUCCESS, CheckinStatus.INTERNAL_ERROR, CheckinStatus.SUCCESS])
        self.assertEqual(summary.exit_code, 70)
        expected = {
            CheckinStatus.CONFIG_ERROR: 2,
            CheckinStatus.AUTH_EXPIRED: 3,
            CheckinStatus.TEMPORARY_ERROR: 4,
            CheckinStatus.SITE_CHANGED: 5,
            CheckinStatus.UNSUPPORTED_SECURITY_CHALLENGE: 6,
            CheckinStatus.ACCESS_DENIED: 7,
            CheckinStatus.INTERNAL_ERROR: 70,
        }
        mixed = [CheckinResult(str(index), status, "fixture") for index, status in enumerate(expected)]
        for status, code in expected.items():
            self.assertEqual(RunSummary.from_results([CheckinResult("one", status, "fixture")]).exit_code, code)
        self.assertEqual(RunSummary.from_results(mixed).exit_code, 7)

    def test_entry_errors_and_notification_failure_keep_exit_contract(self):
        with patch("checkin.main.load_settings", side_effect=RuntimeError("fixture")):
            self.assertEqual(main(), 70)
        success = CheckinResult("alice", CheckinStatus.SUCCESS, "ok")
        with patch("checkin.main.CheckinService.check_in", return_value=success), patch("checkin.main.notify", side_effect=RuntimeError("fixture")):
            self.assertEqual(run(settings()), 0)


if __name__ == "__main__":
    unittest.main()
