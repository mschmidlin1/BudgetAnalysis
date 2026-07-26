"""Unit tests for analysis date filtering and ignore-string filtering."""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from analysis_utils import filter_ignored_descriptions, filter_transactions_by_date


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


class FilterIgnoredDescriptionsTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "Source": ["a.csv", "a.csv", "a.csv", "a.csv"],
                "Date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
                "Amount": [-10.0, -20.0, -30.0, -40.0],
                "Description": [
                    "WEGMANS GROCERY",
                    "PAYMENT THANK YOU",
                    "VENMO CASHOUT",
                    "TARGET STORE",
                ],
            }
        )

    def test_ignores_matching_rows(self):
        kept, ignored = filter_ignored_descriptions(
            self.df, ["PAYMENT THANK YOU"]
        )
        self.assertEqual(kept["Description"].tolist(), [
            "WEGMANS GROCERY",
            "VENMO CASHOUT",
            "TARGET STORE",
        ])
        self.assertEqual(ignored["Description"].tolist(), ["PAYMENT THANK YOU"])

    def test_case_insensitive_match(self):
        kept, ignored = filter_ignored_descriptions(self.df, ["payment thank you"])
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored["Description"].iloc[0], "PAYMENT THANK YOU")
        self.assertEqual(len(kept), 3)

    def test_empty_ignore_list_unchanged(self):
        kept, ignored = filter_ignored_descriptions(self.df, [])
        self.assertEqual(len(kept), 4)
        self.assertTrue(ignored.empty)

        kept_none, ignored_none = filter_ignored_descriptions(self.df, None)
        self.assertEqual(len(kept_none), 4)
        self.assertTrue(ignored_none.empty)

    def test_multiple_ignore_strings(self):
        kept, ignored = filter_ignored_descriptions(
            self.df, ["PAYMENT", "VENMO"]
        )
        self.assertEqual(kept["Description"].tolist(), [
            "WEGMANS GROCERY",
            "TARGET STORE",
        ])
        self.assertEqual(sorted(ignored["Description"].tolist()), [
            "PAYMENT THANK YOU",
            "VENMO CASHOUT",
        ])

    def test_overlapping_matches_once(self):
        """A row matching multiple ignore strings appears once in ignored_df."""
        kept, ignored = filter_ignored_descriptions(
            self.df, ["PAYMENT", "THANK YOU"]
        )
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored["Description"].iloc[0], "PAYMENT THANK YOU")
        self.assertEqual(len(kept), 3)

    def test_literal_special_characters(self):
        """Ignore strings are literal substrings, not regex."""
        df = pd.DataFrame(
            {
                "Source": ["a.csv", "a.csv"],
                "Date": ["2026-01-01", "2026-01-02"],
                "Amount": [-10.0, -20.0],
                "Description": ["PARAMOUNT+", "PARAMOUNTX"],
            }
        )
        kept, ignored = filter_ignored_descriptions(df, ["PARAMOUNT+"])
        self.assertEqual(ignored["Description"].tolist(), ["PARAMOUNT+"])
        self.assertEqual(kept["Description"].tolist(), ["PARAMOUNTX"])


if __name__ == "__main__":
    unittest.main()
