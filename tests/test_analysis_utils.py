"""Unit tests for analysis date filtering."""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from analysis_utils import filter_transactions_by_date


class FilterTransactionsByDateTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "Source": ["a.csv", "a.csv", "a.csv"],
                "Date": ["2026-01-01", "2026-02-15", "2026-03-31"],
                "Amount": [-10.0, -20.0, -30.0],
                "Description": ["Jan", "Feb", "Mar"],
            }
        )

    def test_filter_inclusive_range(self):
        filtered = filter_transactions_by_date(
            self.df,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
        )
        self.assertEqual(filtered["Description"].tolist(), ["Feb"])

    def test_use_all_dates_when_bounds_omitted(self):
        filtered = filter_transactions_by_date(self.df)
        self.assertEqual(len(filtered), 3)

    def test_empty_dataframe(self):
        empty = pd.DataFrame(columns=["Date", "Amount", "Description"])
        filtered = filter_transactions_by_date(
            empty,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.assertTrue(filtered.empty)

    def test_end_date_is_inclusive(self):
        filtered = filter_transactions_by_date(
            self.df,
            start_date=date(2026, 3, 31),
            end_date=date(2026, 3, 31),
        )
        self.assertEqual(filtered["Description"].tolist(), ["Mar"])

    def test_mixed_us_and_iso_date_formats(self):
        """Manual CSVs often use MM/DD/YYYY; Plaid writes ISO YYYY-MM-DD."""
        mixed = pd.DataFrame(
            {
                "Source": ["manual.csv", "bank_plaid.csv"],
                "Date": ["07/23/2026", "2026-07-23"],
                "Amount": [-10.0, -20.0],
                "Description": ["Manual", "Plaid"],
            }
        )
        filtered = filter_transactions_by_date(
            mixed,
            start_date=date(2026, 7, 23),
            end_date=date(2026, 7, 23),
        )
        self.assertEqual(len(filtered), 2)
        self.assertEqual(
            filtered["Date"].dt.normalize().tolist(),
            [pd.Timestamp("2026-07-23"), pd.Timestamp("2026-07-23")],
        )


class MixedDateParsingTests(unittest.TestCase):
    def test_to_datetime_mixed_formats(self):
        """Same parse path as combine_transaction_files after concat."""
        dates = pd.Series(["07/23/2026", "2026-07-24", "01/15/2026"])
        parsed = pd.to_datetime(dates, format="mixed")
        self.assertEqual(
            parsed.tolist(),
            [
                pd.Timestamp("2026-07-23"),
                pd.Timestamp("2026-07-24"),
                pd.Timestamp("2026-01-15"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
