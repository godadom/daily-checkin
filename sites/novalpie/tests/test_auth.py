from __future__ import annotations

import unittest

from helpers import account
from checkin.auth import BearerAuthProvider


class AuthProviderTests(unittest.TestCase):
    def test_bearer_header_is_account_isolated(self):
        first = BearerAuthProvider(account("one", "fixture-one"))
        second = BearerAuthProvider(account("two", "fixture-two"))
        self.assertEqual(first.headers(), {"Authorization": "Bearer fixture-one"})
        self.assertEqual(second.headers(), {"Authorization": "Bearer fixture-two"})
        self.assertFalse(first.refresh())

    def test_non_bearer_auth_is_rejected(self):
        item = type(account())("fixture", "cookie", "fixture-secret")
        with self.assertRaisesRegex(ValueError, "bearer"):
            BearerAuthProvider(item)


if __name__ == "__main__":
    unittest.main()
