from __future__ import annotations

import json
import unittest

from checkin.config import ConfigError, load_settings
from checkin.site_config import ACTION_PATH, BASE_URL, RANDOM_ACTION_PATH, STATUS_PATH


def env(**overrides):
    values = {"CHECKIN_COOKIE": "session=fixture-cookie", "CHECKIN_TIMEZONE": "UTC"}
    values.update(overrides)
    return values


class ConfigTests(unittest.TestCase):
    def test_single_cookie_and_verified_endpoints(self):
        settings = load_settings(env())
        self.assertEqual(settings.accounts[0].auth_type, "cookie")
        self.assertEqual((settings.base_url, settings.status_path, settings.checkin_path), (BASE_URL, STATUS_PATH, ACTION_PATH))
        self.assertEqual(load_settings(env(CHECKIN_ATTENDANCE_MODE="random")).checkin_path, RANDOM_ACTION_PATH)

    def test_rejects_fixed_site_environment_overrides(self):
        for name in ("CHECKIN_BASE_URL", "CHECKIN_STATUS_PATH", "CHECKIN_ACTION_PATH"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ConfigError, "built into site_config.py"):
                    load_settings(env(**{name: "https://untrusted.invalid"}))

    def test_rejects_invalid_mode_and_timezone(self):
        with self.assertRaisesRegex(ConfigError, "fixed or random"):
            load_settings(env(CHECKIN_ATTENDANCE_MODE="other"))
        with self.assertRaisesRegex(ConfigError, "installed IANA timezone"):
            load_settings(env(CHECKIN_TIMEZONE="Shanghai"))

    def test_multi_account_isolated_and_validated(self):
        accounts = json.dumps([{"name": "one", "cookie": "session=fixture-one"}, {"name": "two", "cookie": "session=fixture-two"}])
        self.assertEqual([item.name for item in load_settings(env(CHECKIN_ACCOUNTS=accounts)).accounts], ["one", "two"])
        with self.assertRaisesRegex(ConfigError, "valid JSON"):
            load_settings(env(CHECKIN_ACCOUNTS="["))
