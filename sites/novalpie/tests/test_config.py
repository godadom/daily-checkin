from __future__ import annotations

import json
import unittest

from checkin.config import ACTION_PATH, BASE_URL, STATUS_PATH, ConfigError, load_settings


def env(**overrides):
    values = {
        "CHECKIN_TOKEN": "fixture-token",
        "CHECKIN_TIMEZONE": "UTC",
    }
    values.update(overrides)
    return values


class ConfigTests(unittest.TestCase):
    def test_single_bearer_and_verified_endpoints(self):
        settings = load_settings(env())
        self.assertEqual(settings.accounts[0].auth_type, "bearer")
        self.assertEqual((settings.base_url, settings.status_path, settings.checkin_path), (BASE_URL, STATUS_PATH, ACTION_PATH))

    def test_endpoint_environment_overrides_are_ignored(self):
        settings = load_settings(
            env(
                CHECKIN_BASE_URL="https://untrusted.invalid",
                CHECKIN_STATUS_PATH="/api/unreviewed-status",
                CHECKIN_ACTION_PATH="/api/unreviewed-action",
            )
        )
        self.assertEqual(
            (settings.base_url, settings.status_path, settings.checkin_path),
            (BASE_URL, STATUS_PATH, ACTION_PATH),
        )

    def test_rejects_invalid_timezone_and_bearer_prefix(self):
        with self.assertRaisesRegex(ConfigError, "installed IANA timezone"):
            load_settings(env(CHECKIN_TIMEZONE="Shanghai"))
        with self.assertRaisesRegex(ConfigError, "without the Bearer prefix"):
            load_settings(env(CHECKIN_TOKEN="Bearer fixture-token"))

    def test_multi_account_order_isolation_and_duplicate_validation(self):
        accounts = json.dumps([{"name": "one", "token": "fixture-one"}, {"name": "two", "token": "fixture-two"}])
        parsed = load_settings(env(CHECKIN_ACCOUNTS=accounts)).accounts
        self.assertEqual([item.name for item in parsed], ["one", "two"])
        self.assertNotEqual(parsed[0].secret, parsed[1].secret)
        duplicate = json.dumps([{"name": "one", "token": "fixture-one"}, {"name": "ONE", "token": "fixture-two"}])
        with self.assertRaisesRegex(ConfigError, "unique"):
            load_settings(env(CHECKIN_ACCOUNTS=duplicate))

    def test_invalid_config_does_not_echo_secret(self):
        secret = "fixture-secret-not-for-errors"
        for values in (
            env(CHECKIN_ACCOUNTS="["),
            env(CHECKIN_ACCOUNTS=json.dumps([{"name": "one", "token": secret, "extra": True}])),
        ):
            with self.subTest(values=list(values)):
                with self.assertRaises(ConfigError) as raised:
                    load_settings(values)
                self.assertNotIn(secret, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
