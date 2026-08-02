"""Unit tests for Plaid Link session binding helpers."""

from __future__ import annotations

import unittest

from ui import plaid_ui


class PendingLinkExchangeTests(unittest.TestCase):
    def setUp(self):
        self.username = "alice"
        self.session = {}

    def test_exchange_rejected_without_pending_session(self):
        with self.assertRaises(plaid_ui.PendingLinkError):
            plaid_ui.consume_pending_link_for_exchange(
                self.session,
                self.username,
                public_token="public-sandbox-token",
                link_session_id="link-session-1",
            )

    def test_exchange_rejected_without_link_session_id(self):
        plaid_ui.store_pending_link(
            self.session, self.username, "link-sandbox-token"
        )
        with self.assertRaises(plaid_ui.PendingLinkError) as ctx:
            plaid_ui.consume_pending_link_for_exchange(
                self.session,
                self.username,
                public_token="public-sandbox-token",
                link_session_id=None,
            )
        self.assertIn("link session id", str(ctx.exception).lower())
        # Pending session must remain so the user can retry after a bad payload.
        self.assertIsNotNone(
            plaid_ui.get_pending_link_token(self.session, self.username)
        )

    def test_exchange_succeeds_once_then_rejects_reuse(self):
        plaid_ui.store_pending_link(
            self.session, self.username, "link-sandbox-token"
        )
        consumed = plaid_ui.consume_pending_link_for_exchange(
            self.session,
            self.username,
            public_token="public-sandbox-token",
            link_session_id="link-session-1",
        )
        self.assertEqual(consumed, "link-sandbox-token")
        self.assertIsNone(
            plaid_ui.get_pending_link_token(self.session, self.username)
        )

        with self.assertRaises(plaid_ui.PendingLinkError):
            plaid_ui.consume_pending_link_for_exchange(
                self.session,
                self.username,
                public_token="public-sandbox-token",
                link_session_id="link-session-1",
            )

    def test_clear_plaid_session_keys_removes_prefixed_keys(self):
        self.session.update(
            {
                "plaid_pending_link_alice": {"link_token": "t"},
                "plaid_filter_start_date_alice": "2026-01-01",
                "plaid_filter_end_date_bob": "2026-12-31",
                "analysis_results": {"keep": True},
            }
        )
        plaid_ui.clear_plaid_session_keys(self.session)
        self.assertEqual(self.session, {"analysis_results": {"keep": True}})


if __name__ == "__main__":
    unittest.main()
