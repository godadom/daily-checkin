from __future__ import annotations

import json
import unittest

from checkin.config import BASE_URL, STATUS_PATH, ConfigError, RANDOM_ACTION_PATH, load_settings


def env(**overrides):
    values = {"CHECKIN_BASE_URL": BASE_URL, "CHECKIN_STATUS_PATH": STATUS_PATH, "CHECKIN_COOKIE": "session=fixture-cookie", "CHECKIN_TIMEZONE": "UTC"}
    values.update(overrides)
    return values


class ConfigTests(unittest.TestCase):
    def test_single_cookie_and_verified_endpoints(self):
        settings = load_settings(env())
        self.assertEqual(settings.accounts[0].auth_type, "cookie")
        self.assertEqual(settings.status_path, STATUS_PATH)
        self.assertEqual(load_settings(env(CHECKIN_ATTENDANCE_MODE="random")).checkin_path, RANDOM_ACTION_PATH)

    def test_rejects_changed_endpoint_and_invalid_timezone(self):
        with self.assertRaisesRegex(ConfigError, "fixed or random"):
            load_settings(env(CHECKIN_ATTENDANCE_MODE="other"))
        with self.assertRaisesRegex(ConfigError, "installed IANA timezone"):
            load_settings(env(CHECKIN_TIMEZONE="Shanghai"))

    def test_multi_account_isolated_and_validated(self):
        accounts = json.dumps([{"name": "one", "cookie": "session=fixture-one"}, {"name": "two", "cookie": "session=fixture-two"}])
        self.assertEqual([item.name for item in load_settings(env(CHECKIN_ACCOUNTS=accounts)).accounts], ["one", "two"])
        with self.assertRaisesRegex(ConfigError, "valid JSON"):
            load_settings(env(CHECKIN_ACCOUNTS="["))
