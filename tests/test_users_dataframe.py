"""Unit tests for users DataFrame dtype coercion."""

from __future__ import annotations

import unittest

import pandas as pd

from storage.user_tools import (
    add_user_to_dataframe,
    normalize_users_dataframe,
    update_user_in_dataframe,
)


class UsersDataframeTests(unittest.TestCase):
    def test_normalize_float_logged_in_column(self):
        df = pd.DataFrame(
            {
                "username": ["alice"],
                "email": ["a@example.com"],
                "first_name": ["Alice"],
                "last_name": ["A"],
                "password": ["hash"],
                "password_hint": [""],
                "logged_in": [float("nan")],
                "failed_login_attempts": [float("nan")],
                "roles": [float("nan")],
            }
        )
        normalized = normalize_users_dataframe(df)
        self.assertEqual(normalized.loc[0, "logged_in"], False)
        self.assertEqual(normalized.loc[0, "failed_login_attempts"], 0)
        self.assertEqual(normalized.loc[0, "roles"], "")

    def test_update_existing_user_with_false_logged_in(self):
        df = pd.DataFrame(
            {
                "username": ["alice"],
                "email": ["a@example.com"],
                "first_name": ["Alice"],
                "last_name": ["A"],
                "password": ["hash"],
                "password_hint": [""],
                "logged_in": [float("nan")],
                "failed_login_attempts": [float("nan")],
                "roles": [float("nan")],
            }
        )
        updated = update_user_in_dataframe(
            df,
            "alice",
            {"logged_in": False, "failed_login_attempts": 0, "email": "a@example.com"},
        )
        self.assertEqual(updated.loc[0, "logged_in"], False)
        self.assertEqual(updated.loc[0, "failed_login_attempts"], 0)

    def test_add_user_when_sheet_has_float_columns(self):
        df = pd.DataFrame(
            {
                "username": ["alice"],
                "email": ["a@example.com"],
                "first_name": ["Alice"],
                "last_name": ["A"],
                "password": ["hash"],
                "password_hint": [""],
                "logged_in": [float("nan")],
                "failed_login_attempts": [float("nan")],
                "roles": [float("nan")],
            }
        )
        result = add_user_to_dataframe(
            df,
            "bob",
            {
                "email": "b@example.com",
                "first_name": "Bob",
                "last_name": "B",
                "password": "hash2",
                "logged_in": False,
                "failed_login_attempts": 0,
            },
        )
        self.assertEqual(len(result), 2)
        bob = result[result["username"] == "bob"].iloc[0]
        self.assertEqual(bob["logged_in"], False)
        self.assertEqual(bob["failed_login_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
