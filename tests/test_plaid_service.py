"""Unit tests for encrypted Plaid persistence and CSV synchronization."""

from __future__ import annotations

from datetime import date
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from cryptography.fernet import Fernet
import pandas as pd

from plaid_integration import plaid_service
from storage import storage_utils


class FakePlaidClient:
    def __init__(self, sync_responses=None, refresh_error=None):
        self.sync_responses = list(sync_responses or [])
        self.removed_access_token = None
        self.refresh_calls = 0
        self.refresh_error = refresh_error

    def transactions_refresh(self, request):
        self.refresh_calls += 1
        if self.refresh_error:
            raise self.refresh_error
        return SimpleNamespace()

    def transactions_sync(self, request):
        return self.sync_responses.pop(0)

    def item_remove(self, request):
        self.removed_access_token = request.access_token
        return SimpleNamespace()


def transaction(
    transaction_id: str,
    amount: float,
    merchant: str,
    pending: bool = False,
    day: int = 21,
):
    return SimpleNamespace(
        transaction_id=transaction_id,
        date=date(2026, 7, day),
        amount=amount,
        merchant_name=merchant,
        name=merchant,
        pending=pending,
    )


def sync_response(
    *,
    added=None,
    modified=None,
    removed=None,
    cursor="cursor-1",
    has_more=False,
):
    return SimpleNamespace(
        added=added or [],
        modified=modified or [],
        removed=removed or [],
        next_cursor=cursor,
        has_more=has_more,
    )


class PlaidServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.env_patcher = mock.patch.dict(
            os.environ, {"BUDGET_STORAGE_ROOT": str(self.root)}
        )
        self.env_patcher.start()
        self.username = "alice"
        self.encryption_key = Fernet.generate_key().decode("utf-8")

    def tearDown(self):
        self.env_patcher.stop()
        self._tmpdir.cleanup()

    def test_institution_csv_filename(self):
        self.assertEqual(
            plaid_service.institution_csv_filename("Robinhood"),
            "robinhood_plaid.csv",
        )
        self.assertEqual(
            plaid_service.institution_csv_filename("First Platypus Bank"),
            "first_platypus_bank_plaid.csv",
        )

    def test_settings_validate_environment_and_required_values(self):
        settings = plaid_service.PlaidSettings.from_mapping(
            {
                "client_id": "client",
                "secret": "secret",
                "env": "SANDBOX",
                "token_encryption_key": self.encryption_key,
            }
        )
        self.assertEqual(settings.environment, "sandbox")

        with self.assertRaises(plaid_service.PlaidConfigurationError):
            plaid_service.PlaidSettings.from_mapping(
                {
                    "client_id": "client",
                    "secret": "",
                    "token_encryption_key": self.encryption_key,
                }
            )

    def test_access_token_round_trip_and_wrong_key_is_safe(self):
        ciphertext = plaid_service.encrypt_access_token(
            "access-sandbox-secret-token",
            self.encryption_key,
        )
        self.assertNotIn(b"access-sandbox-secret-token", ciphertext)
        self.assertEqual(
            plaid_service.decrypt_access_token(ciphertext, self.encryption_key),
            "access-sandbox-secret-token",
        )
        with self.assertRaises(plaid_service.PlaidTokenError):
            plaid_service.decrypt_access_token(
                ciphertext,
                Fernet.generate_key().decode("utf-8"),
            )

    def test_save_connection_encrypts_token_and_loads_metadata(self):
        plaid_service.save_connection(
            self.username,
            "access-token",
            "item-id",
            self.encryption_key,
            "Robinhood Credit",
        )

        self.assertTrue(plaid_service.is_connected(self.username))
        self.assertEqual(
            plaid_service.load_access_token(self.username, self.encryption_key),
            "access-token",
        )
        metadata = plaid_service.load_metadata(self.username)
        self.assertEqual(metadata["item_id"], "item-id")
        self.assertEqual(metadata["institution_name"], "Robinhood Credit")
        self.assertEqual(metadata["csv_filename"], "robinhood_credit_plaid.csv")
        encrypted = storage_utils.read_bytes(
            f"{self.username}/secrets/plaid_access_token.enc"
        )
        self.assertNotIn(b"access-token", encrypted)

    def test_sync_writes_posted_transactions_and_mapping(self):
        plaid_service.save_connection(
            self.username,
            "access-token",
            "item-id",
            self.encryption_key,
            "Robinhood",
        )
        client = FakePlaidClient(
            [
                sync_response(
                    added=[
                        transaction("posted-1", 42.50, "Grocery Store"),
                        transaction("pending-1", 10.00, "Pending", pending=True),
                    ]
                )
            ]
        )

        result = plaid_service.sync_transactions(
            client, self.username, self.encryption_key
        )

        self.assertEqual(result.count, 1)
        self.assertEqual(result.earliest_date, "2026-07-21")
        self.assertEqual(result.latest_date, "2026-07-21")
        self.assertEqual(result.csv_filename, "robinhood_plaid.csv")
        self.assertEqual(client.refresh_calls, 1)
        csv_bytes = storage_utils.read_bytes(
            storage_utils.get_path_for_upload(self.username, "robinhood_plaid.csv")
        )
        dataframe = pd.read_csv(io.BytesIO(csv_bytes))
        self.assertEqual(dataframe["Transaction ID"].tolist(), ["posted-1"])
        self.assertEqual(dataframe["Amount"].tolist(), [42.5])
        self.assertEqual(dataframe["Source"].tolist(), ["Robinhood"])

        upload_config = storage_utils.load_json(
            storage_utils.get_path_for_config(self.username, "upload_config")
        )
        self.assertEqual(
            upload_config["file_mappings"]["robinhood_plaid.csv"],
            ["Date", "Amount", "Description"],
        )
        self.assertEqual(
            plaid_service.load_metadata(self.username)["cursor"], "cursor-1"
        )

    def test_date_filter_applies_only_to_analysis_csv(self):
        plaid_service.save_connection(
            self.username,
            "access-token",
            "item-id",
            self.encryption_key,
            "Robinhood",
        )
        # Widen the default calendar-year filter so both fixtures are included.
        plaid_service.set_date_filter(
            self.username,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        client = FakePlaidClient(
            [
                sync_response(
                    added=[
                        transaction("early", 10, "Early", day=1),
                        transaction("late", 20, "Late", day=21),
                    ]
                )
            ]
        )
        plaid_service.sync_transactions(client, self.username, self.encryption_key)

        count = plaid_service.set_date_filter(
            self.username,
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 31),
        )
        self.assertEqual(count, 1)
        csv_bytes = storage_utils.read_bytes(
            storage_utils.get_path_for_upload(self.username, "robinhood_plaid.csv")
        )
        dataframe = pd.read_csv(io.BytesIO(csv_bytes))
        self.assertEqual(dataframe["Description"].tolist(), ["Late"])

        restored = plaid_service.set_date_filter(
            self.username,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.assertEqual(restored, 2)

    def test_calendar_year_date_range(self):
        start, end = plaid_service.calendar_year_date_range(date(2026, 7, 21))
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 12, 31))

    def test_normalize_transaction_keeps_plaid_amount_signs(self):
        purchase = plaid_service._normalize_transaction(
            transaction("buy-1", 42.50, "Grocery Store"),
            "Robinhood",
        )
        payment = plaid_service._normalize_transaction(
            transaction("pay-1", -100.0, "Payment"),
            "Robinhood",
        )
        self.assertEqual(purchase["Amount"], 42.50)
        self.assertEqual(payment["Amount"], -100.0)

    def test_sync_applies_modified_and_removed_transactions(self):
        plaid_service.save_connection(
            self.username,
            "access-token",
            "item-id",
            self.encryption_key,
            "Robinhood",
        )
        first_client = FakePlaidClient(
            [
                sync_response(
                    added=[
                        transaction("keep", 10, "Old Name"),
                        transaction("remove", 20, "Remove Me"),
                    ]
                )
            ]
        )
        plaid_service.sync_transactions(
            first_client, self.username, self.encryption_key
        )

        second_client = FakePlaidClient(
            [
                sync_response(
                    modified=[transaction("keep", 15, "New Name")],
                    removed=[SimpleNamespace(transaction_id="remove")],
                    cursor="cursor-2",
                )
            ]
        )
        result = plaid_service.sync_transactions(
            second_client, self.username, self.encryption_key
        )

        self.assertEqual(result.count, 1)
        csv_bytes = storage_utils.read_bytes(
            storage_utils.get_path_for_upload(self.username, "robinhood_plaid.csv")
        )
        dataframe = pd.read_csv(io.BytesIO(csv_bytes))
        self.assertEqual(dataframe["Description"].tolist(), ["New Name"])
        self.assertEqual(dataframe["Amount"].tolist(), [15.0])

    def test_disconnect_removes_item_and_all_local_data(self):
        plaid_service.save_connection(
            self.username,
            "access-token",
            "item-id",
            self.encryption_key,
            "Robinhood",
        )
        storage_utils.write_text(
            storage_utils.get_path_for_upload(self.username, "robinhood_plaid.csv"),
            "Date,Amount,Description\n2026-01-01,1,Test\n",
        )
        storage_utils.save_json(
            {
                "file_mappings": {
                    "other.csv": ["Date", "Amount", "Description"],
                    "robinhood_plaid.csv": [
                        "Date",
                        "Amount",
                        "Description",
                    ],
                }
            },
            storage_utils.get_path_for_config(self.username, "upload_config"),
        )
        client = FakePlaidClient()

        removed = plaid_service.disconnect(
            client, self.username, self.encryption_key
        )

        self.assertTrue(removed)
        self.assertEqual(client.removed_access_token, "access-token")
        self.assertFalse(plaid_service.is_connected(self.username))
        self.assertFalse(
            storage_utils.exists(
                storage_utils.get_path_for_upload(
                    self.username, "robinhood_plaid.csv"
                )
            )
        )
        upload_config = storage_utils.load_json(
            storage_utils.get_path_for_config(self.username, "upload_config")
        )
        self.assertEqual(
            upload_config["file_mappings"],
            {"other.csv": ["Date", "Amount", "Description"]},
        )


if __name__ == "__main__":
    unittest.main()
