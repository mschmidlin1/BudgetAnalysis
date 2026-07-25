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


if __name__ == "__main__":
    unittest.main()
