"""Unit tests for recurring payment detection and HTML report inclusion."""

from __future__ import annotations

import os
import tempfile
import unittest

import pandas as pd
import plotly.graph_objects as go

from analysis.analysis_utils import create_html_report
from analysis.recurring_payments import (
    RESULT_COLUMNS,
    assign_transaction_categories,
    detect_recurring_payments,
    empty_recurring_dataframe,
    normalize_description,
)


def _tx_frame(rows):
    """Build a transactions DataFrame from list of dicts."""
    return pd.DataFrame(rows)


class NormalizeDescriptionTests(unittest.TestCase):
    def test_strips_store_numbers_and_card_suffix(self):
        raw = "SUNOCO GAS STATION #1234 Card 4242"
        self.assertEqual(normalize_description(raw), "SUNOCO GAS STATION")


class AssignCategoriesTests(unittest.TestCase):
    def test_assigns_nested_category_path(self):
        df = _tx_frame(
            [
                {
                    "Source": "visa.csv",
                    "Date": "2024-01-12",
                    "Amount": -15.99,
                    "Description": "Netflix Subscription",
                },
                {
                    "Source": "visa.csv",
                    "Date": "2024-01-20",
                    "Amount": -40.0,
                    "Description": "SUNOCO GAS",
                },
            ]
        )
        search = [{"Subscriptions": [{"Streaming": ["Netflix"]}]}]
        labeled = assign_transaction_categories(df, search)
        self.assertEqual(
            labeled.loc[0, "Category"], "Subscriptions / Streaming / Netflix"
        )
        self.assertEqual(labeled.loc[1, "Category"], "")


class DetectRecurringPaymentsTests(unittest.TestCase):
    def test_monthly_subscription_detected_as_active(self):
        rows = []
        for month in range(1, 7):
            rows.append(
                {
                    "Source": "chase.csv",
                    "Date": f"2024-{month:02d}-12",
                    "Amount": -15.99,
                    "Description": "Netflix Subscription",
                }
            )
        # Anchor dataset end near last charge
        rows.append(
            {
                "Source": "chase.csv",
                "Date": "2024-06-20",
                "Amount": -5.0,
                "Description": "ONE OFF SNACK",
            }
        )
        df = assign_transaction_categories(
            _tx_frame(rows), ["Netflix"]
        )
        result = detect_recurring_payments(df)
        self.assertFalse(result.empty)
        netflix = result[result["name"].str.contains("Netflix", case=False)]
        self.assertEqual(len(netflix), 1)
        self.assertEqual(netflix.iloc[0]["frequency"], "monthly")
        self.assertEqual(netflix.iloc[0]["active"], "Yes")
        self.assertEqual(netflix.iloc[0]["credit_card"], "chase.csv")
        self.assertEqual(netflix.iloc[0]["category"], "Netflix")
        self.assertAlmostEqual(netflix.iloc[0]["amount"], 15.99, places=2)

    def test_irregular_gas_not_detected(self):
        rows = [
            {"Source": "visa.csv", "Date": "2024-01-05", "Amount": -45.32, "Description": "SUNOCO GAS"},
            {"Source": "visa.csv", "Date": "2024-01-20", "Amount": -42.18, "Description": "SUNOCO GAS"},
            {"Source": "visa.csv", "Date": "2024-02-03", "Amount": -38.75, "Description": "SUNOCO GAS"},
            {"Source": "visa.csv", "Date": "2024-02-22", "Amount": -55.10, "Description": "SUNOCO GAS"},
            {"Source": "visa.csv", "Date": "2024-03-08", "Amount": -41.00, "Description": "SUNOCO GAS"},
            {"Source": "visa.csv", "Date": "2024-03-19", "Amount": -60.25, "Description": "SUNOCO GAS"},
            {"Source": "visa.csv", "Date": "2024-04-02", "Amount": -33.40, "Description": "SUNOCO GAS"},
            {"Source": "visa.csv", "Date": "2024-04-28", "Amount": -48.90, "Description": "SUNOCO GAS"},
        ]
        result = detect_recurring_payments(_tx_frame(rows))
        sunoco = result[result["name"].str.contains("SUNOCO", case=False)]
        self.assertTrue(sunoco.empty)

    def test_inactive_when_charges_stop_before_dataset_end(self):
        rows = []
        for month in range(1, 4):
            rows.append(
                {
                    "Source": "amex.csv",
                    "Date": f"2024-{month:02d}-01",
                    "Amount": -9.99,
                    "Description": "Hulu Plus",
                }
            )
        # Dataset continues many months after last Hulu charge
        rows.append(
            {
                "Source": "amex.csv",
                "Date": "2024-12-15",
                "Amount": -20.0,
                "Description": "OTHER STORE",
            }
        )
        result = detect_recurring_payments(_tx_frame(rows))
        hulu = result[result["name"].str.contains("Hulu", case=False)]
        self.assertEqual(len(hulu), 1)
        self.assertEqual(hulu.iloc[0]["active"], "No")

    def test_amount_tolerant_detects_small_price_change(self):
        rows = [
            {"Source": "visa.csv", "Date": "2024-01-10", "Amount": -12.99, "Description": "Spotify Premium"},
            {"Source": "visa.csv", "Date": "2024-02-10", "Amount": -12.99, "Description": "Spotify Premium"},
            {"Source": "visa.csv", "Date": "2024-03-10", "Amount": -13.49, "Description": "Spotify Premium"},
            {"Source": "visa.csv", "Date": "2024-04-10", "Amount": -13.49, "Description": "Spotify Premium"},
            {"Source": "visa.csv", "Date": "2024-05-10", "Amount": -13.49, "Description": "Spotify Premium"},
            {"Source": "visa.csv", "Date": "2024-05-15", "Amount": -1.0, "Description": "FILLER"},
        ]
        result = detect_recurring_payments(_tx_frame(rows))
        spotify = result[result["name"].str.contains("Spotify", case=False)]
        self.assertEqual(len(spotify), 1)
        self.assertEqual(spotify.iloc[0]["frequency"], "monthly")

    def test_day_of_month_with_varying_month_lengths(self):
        # Charges near end of month create 28-31 day gaps
        dates = [
            "2024-01-31",
            "2024-02-29",
            "2024-03-31",
            "2024-04-30",
            "2024-05-31",
        ]
        rows = [
            {
                "Source": "wells.csv",
                "Date": d,
                "Amount": -65.00,
                "Description": "YMCA Membership",
            }
            for d in dates
        ]
        rows.append(
            {
                "Source": "wells.csv",
                "Date": "2024-06-05",
                "Amount": -2.0,
                "Description": "FILLER",
            }
        )
        result = detect_recurring_payments(_tx_frame(rows))
        ymca = result[result["name"].str.contains("YMCA", case=False)]
        self.assertEqual(len(ymca), 1)
        self.assertEqual(ymca.iloc[0]["frequency"], "monthly")

    def test_empty_and_short_dataframe(self):
        empty = detect_recurring_payments(pd.DataFrame())
        self.assertTrue(empty.empty)
        self.assertEqual(list(empty.columns), RESULT_COLUMNS)

        short = _tx_frame(
            [
                {
                    "Source": "a.csv",
                    "Date": "2024-01-01",
                    "Amount": -10.0,
                    "Description": "Netflix",
                },
                {
                    "Source": "a.csv",
                    "Date": "2024-02-01",
                    "Amount": -10.0,
                    "Description": "Netflix",
                },
            ]
        )
        result = detect_recurring_payments(short)
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), RESULT_COLUMNS)

    def test_dedupe_same_series_from_multiple_detectors(self):
        rows = []
        for month in range(1, 6):
            rows.append(
                {
                    "Source": "joint.csv",
                    "Date": f"2024-{month:02d}-15",
                    "Amount": -15.99,
                    "Description": "Netflix Subscription",
                }
            )
        rows.append(
            {
                "Source": "joint.csv",
                "Date": "2024-05-20",
                "Amount": -3.0,
                "Description": "FILLER",
            }
        )
        result = detect_recurring_payments(_tx_frame(rows))
        netflix = result[result["name"].str.contains("Netflix", case=False)]
        self.assertEqual(len(netflix), 1)

    def test_multi_source_credit_card_joined(self):
        rows = [
            {"Source": "visa.csv", "Date": "2024-01-05", "Amount": -20.0, "Description": "Gym Club"},
            {"Source": "amex.csv", "Date": "2024-02-05", "Amount": -20.0, "Description": "Gym Club"},
            {"Source": "visa.csv", "Date": "2024-03-05", "Amount": -20.0, "Description": "Gym Club"},
            {"Source": "amex.csv", "Date": "2024-04-05", "Amount": -20.0, "Description": "Gym Club"},
            {"Source": "visa.csv", "Date": "2024-04-10", "Amount": -1.0, "Description": "FILLER"},
        ]
        result = detect_recurring_payments(_tx_frame(rows))
        gym = result[result["name"].str.contains("Gym", case=False)]
        self.assertEqual(len(gym), 1)
        cards = set(part.strip() for part in gym.iloc[0]["credit_card"].split(","))
        self.assertEqual(cards, {"visa.csv", "amex.csv"})

    def test_uncategorized_series_has_blank_category(self):
        rows = [
            {"Source": "a.csv", "Date": "2024-01-01", "Amount": -11.0, "Description": "Mystery Sub"},
            {"Source": "a.csv", "Date": "2024-02-01", "Amount": -11.0, "Description": "Mystery Sub"},
            {"Source": "a.csv", "Date": "2024-03-01", "Amount": -11.0, "Description": "Mystery Sub"},
            {"Source": "a.csv", "Date": "2024-03-05", "Amount": -1.0, "Description": "FILLER"},
        ]
        labeled = assign_transaction_categories(_tx_frame(rows), ["Netflix"])
        result = detect_recurring_payments(labeled)
        mystery = result[result["name"].str.contains("Mystery", case=False)]
        self.assertEqual(len(mystery), 1)
        self.assertEqual(mystery.iloc[0]["category"], "")


class HtmlReportRecurringTests(unittest.TestCase):
    def test_report_includes_recurring_section_and_names(self):
        expense_summary = {"Food": 100.0, "No Category": 0.0}
        fig = go.Figure(data=[go.Pie(labels=["Food"], values=[100])])
        recurring = pd.DataFrame(
            [
                {
                    "name": "Netflix Subscription",
                    "amount": 15.99,
                    "credit_card": "visa.csv",
                    "category": "Streaming",
                    "start_date": pd.Timestamp("2024-01-12"),
                    "end_date": pd.Timestamp("2024-06-12"),
                    "frequency": "monthly",
                    "active": "Yes",
                }
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.html")
            create_html_report(expense_summary, fig, path, recurring_df=recurring)
            with open(path, encoding="utf-8") as f:
                html = f.read()
        self.assertIn("Recurring Payments", html)
        self.assertIn("Netflix Subscription", html)
        self.assertIn("$15.99", html)

    def test_report_handles_empty_recurring(self):
        expense_summary = {"Food": 50.0, "No Category": 0.0}
        fig = go.Figure(data=[go.Pie(labels=["Food"], values=[50])])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.html")
            create_html_report(
                expense_summary, fig, path, recurring_df=empty_recurring_dataframe()
            )
            with open(path, encoding="utf-8") as f:
                html = f.read()
        self.assertIn("Recurring Payments", html)
        self.assertIn("No recurring payments detected", html)


if __name__ == "__main__":
    unittest.main()
