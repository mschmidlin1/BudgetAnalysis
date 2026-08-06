"""Detect recurring payments from credit card transaction data."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Optional

import numpy as np
import pandas as pd

RESULT_COLUMNS = [
    "name",
    "amount",
    "credit_card",
    "category",
    "start_date",
    "end_date",
    "frequency",
    "active",
]

DISPLAY_COLUMNS = {
    "name": "Recurring Expense Name",
    "amount": "Recurring Amount",
    "credit_card": "Credit Card",
    "category": "Category",
    "start_date": "Start Date",
    "end_date": "End Date",
    "frequency": "Frequency",
    "active": "Active",
}

MIN_OCCURRENCES = 3
MAX_GAP_CV = 0.35
AMOUNT_TOLERANCE_ABS = 1.0
AMOUNT_TOLERANCE_PCT = 0.05

FREQUENCY_BINS = {
    "weekly": (5, 9, 7),
    "biweekly": (11, 17, 14),
    "monthly": (25, 35, 30),
    "quarterly": (81, 101, 91),
    "yearly": (345, 385, 365),
}

_NOISE_PATTERNS = [
    re.compile(r"\bstore\s*#?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bcard\s*#?\s*\d+\b", re.IGNORECASE),
    re.compile(r"#\s*\d+\b"),
    re.compile(r"\b\d{4,}\b"),
]


def empty_recurring_dataframe() -> pd.DataFrame:
    """Return an empty recurring-payments result with the expected columns."""
    return pd.DataFrame(columns=RESULT_COLUMNS)


def normalize_description(description: Any) -> str:
    """Normalize merchant text for grouping (display uses original text)."""
    if description is None or (isinstance(description, float) and np.isnan(description)):
        return ""
    text = str(description).upper()
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub(" ", text)
    text = re.sub(r"[^A-Z0-9\s*&+./-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _amount_tolerance(amount: float) -> float:
    return max(AMOUNT_TOLERANCE_ABS, abs(amount) * AMOUNT_TOLERANCE_PCT)


def _amounts_similar(a: float, b: float) -> bool:
    return abs(a - b) <= max(_amount_tolerance(a), _amount_tolerance(b))


def assign_transaction_categories(
    df: pd.DataFrame, search_strings: list
) -> pd.DataFrame:
    """
    Tag each transaction with the category path from keyword matching.

    Uses the same first-match-wins, case-insensitive substring order as
    process_search_strings so labels stay consistent with the sunburst.
    Nested categories become a path joined with " / ".
    """
    if df is None or df.empty:
        out = df.copy() if df is not None else pd.DataFrame()
        if not out.empty or "Category" not in out.columns:
            out = out.copy()
            out["Category"] = pd.Series(dtype=object)
        return out

    out = df.copy()
    categories = pd.Series([""] * len(out), index=out.index, dtype=object)
    remaining_mask = pd.Series(True, index=out.index)
    descriptions = out["Description"].astype(str)

    def match_keyword(keyword: str, mask: pd.Series) -> pd.Series:
        return mask & descriptions.str.contains(
            keyword, case=False, na=False, regex=False
        )

    def walk(item: Any, path: list[str], mask: pd.Series) -> None:
        nonlocal categories, remaining_mask

        if isinstance(item, str):
            hit = match_keyword(item, mask & remaining_mask)
            if hit.any():
                label = " / ".join(path + [item]) if path else item
                categories.loc[hit] = label
                remaining_mask.loc[hit] = False
            return

        if isinstance(item, dict):
            for key, value in item.items():
                child_path = path + [str(key)]
                if isinstance(value, list):
                    for sub_item in value:
                        walk(sub_item, child_path, mask)
                else:
                    walk(value, child_path, mask)

    for item in search_strings or []:
        walk(item, [], remaining_mask)

    out["Category"] = categories
    return out


def _classify_frequency(gaps_days: np.ndarray) -> Optional[tuple[str, float, float]]:
    """Return (frequency, median_gap, cv) or None if irregular / unknown."""
    if len(gaps_days) == 0:
        return None

    median_gap = float(np.median(gaps_days))
    if median_gap <= 0:
        return None

    std = float(np.std(gaps_days, ddof=0))
    cv = std / median_gap if median_gap else float("inf")
    if cv > MAX_GAP_CV:
        return None

    for name, (low, high, _) in FREQUENCY_BINS.items():
        if low <= median_gap <= high:
            return name, median_gap, cv
    return None


def _expected_period_days(frequency: str) -> float:
    return float(FREQUENCY_BINS[frequency][2])


def _is_active(end_date: pd.Timestamp, dataset_max: pd.Timestamp, frequency: str) -> bool:
    period = _expected_period_days(frequency)
    delta_days = (dataset_max.normalize() - pd.Timestamp(end_date).normalize()).days
    return delta_days <= 1.5 * period


def _mode_or_join(values: pd.Series, join: bool = False) -> str:
    cleaned = [str(v) for v in values.dropna().tolist() if str(v).strip()]
    if not cleaned:
        return ""
    if join:
        # Preserve first-seen order of unique values
        seen = []
        for v in cleaned:
            if v not in seen:
                seen.append(v)
        return ", ".join(seen)
    counts = Counter(cleaned)
    return counts.most_common(1)[0][0]


def _series_from_group(
    group: pd.DataFrame,
    frequency: str,
    gap_cv: float,
    dataset_max: pd.Timestamp,
) -> dict:
    abs_amounts = group["_abs_amount"]
    start = pd.Timestamp(group["Date"].min())
    end = pd.Timestamp(group["Date"].max())
    category = ""
    if "Category" in group.columns:
        non_empty = group["Category"].fillna("").astype(str)
        non_empty = non_empty[non_empty.str.strip() != ""]
        category = _mode_or_join(non_empty) if len(non_empty) else ""

    return {
        "name": _mode_or_join(group["Description"]),
        "amount": float(abs_amounts.median()),
        "credit_card": _mode_or_join(group["Source"], join=True),
        "category": category,
        "start_date": start.normalize(),
        "end_date": end.normalize(),
        "frequency": frequency,
        "active": _is_active(end, dataset_max, frequency),
        "_normalized": group["_normalized"].iloc[0],
        "_occurrences": len(group),
        "_gap_cv": gap_cv,
    }


def _prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, Optional[pd.Timestamp]]:
    if df is None or df.empty:
        return empty_recurring_dataframe(), None

    required = {"Date", "Amount", "Description", "Source"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    work = df.copy()
    work["Date"] = pd.to_datetime(work["Date"], format="mixed", errors="coerce")
    work = work.dropna(subset=["Date"])
    if work.empty:
        return empty_recurring_dataframe(), None

    work["_abs_amount"] = work["Amount"].astype(float).abs()
    work["_normalized"] = work["Description"].map(normalize_description)
    work = work[work["_normalized"] != ""].copy()
    if work.empty:
        return empty_recurring_dataframe(), None

    if "Category" not in work.columns:
        work["Category"] = ""

    dataset_max = pd.Timestamp(work["Date"].max())
    return work, dataset_max


def _cadence_candidates_from_groups(
    groups: list[pd.DataFrame],
    dataset_max: pd.Timestamp,
) -> list[dict]:
    candidates = []
    for group in groups:
        if len(group) < MIN_OCCURRENCES:
            continue
        ordered = group.sort_values("Date")
        dates = ordered["Date"].drop_duplicates().sort_values()
        if len(dates) < MIN_OCCURRENCES:
            continue
        gaps = dates.diff().dt.days.dropna().to_numpy(dtype=float)
        classified = _classify_frequency(gaps)
        if classified is None:
            continue
        frequency, _, gap_cv = classified
        # Use all rows in the amount/description group, not only unique dates
        candidates.append(
            _series_from_group(ordered, frequency, gap_cv, dataset_max)
        )
    return candidates


def _cluster_by_amount(group: pd.DataFrame) -> list[pd.DataFrame]:
    """Split a merchant group into amount-similar clusters."""
    if group.empty:
        return []

    remaining = group.sort_values("_abs_amount").copy()
    clusters: list[pd.DataFrame] = []

    while not remaining.empty:
        median = float(remaining["_abs_amount"].median())
        tol = _amount_tolerance(median)
        mask = (remaining["_abs_amount"] - median).abs() <= tol
        # Grow around seed median; if nothing matches (shouldn't), take closest
        if not mask.any():
            seed_idx = remaining["_abs_amount"].sub(median).abs().idxmin()
            mask = remaining.index == seed_idx
        cluster = remaining.loc[mask].copy()
        clusters.append(cluster)
        remaining = remaining.loc[~mask].copy()

    return clusters


def _detector_exact_desc_amount(
    work: pd.DataFrame, dataset_max: pd.Timestamp
) -> list[dict]:
    work = work.copy()
    work["_amount_key"] = work["_abs_amount"].round(2)
    groups = [
        g
        for _, g in work.groupby(["_normalized", "_amount_key"], sort=False)
    ]
    return _cadence_candidates_from_groups(groups, dataset_max)


def _detector_amount_tolerant(
    work: pd.DataFrame, dataset_max: pd.Timestamp
) -> list[dict]:
    candidates = []
    for _, merchant_group in work.groupby("_normalized", sort=False):
        for cluster in _cluster_by_amount(merchant_group):
            candidates.extend(
                _cadence_candidates_from_groups([cluster], dataset_max)
            )
    return candidates


def _detector_day_of_month(
    work: pd.DataFrame, dataset_max: pd.Timestamp
) -> list[dict]:
    candidates = []
    for _, merchant_group in work.groupby("_normalized", sort=False):
        for cluster in _cluster_by_amount(merchant_group):
            if len(cluster) < MIN_OCCURRENCES:
                continue

            ordered = cluster.sort_values("Date").copy()
            ordered["_day"] = ordered["Date"].dt.day
            ordered["_month_key"] = ordered["Date"].dt.to_period("M")

            # Pick the most common day-of-month and keep nearby days
            day_counts = ordered["_day"].value_counts()
            anchor_day = int(day_counts.index[0])
            near = ordered[ordered["_day"].sub(anchor_day).abs() <= 2].copy()
            if near["_month_key"].nunique() < MIN_OCCURRENCES:
                continue

            # One charge per month (earliest on that day cluster)
            monthly = (
                near.sort_values("Date")
                .groupby("_month_key", sort=True)
                .head(1)
                .copy()
            )
            if len(monthly) < MIN_OCCURRENCES:
                continue

            month_gaps = (
                monthly["Date"]
                .sort_values()
                .diff()
                .dt.days
                .dropna()
                .to_numpy(dtype=float)
            )
            median_gap = float(np.median(month_gaps)) if len(month_gaps) else 30.0

            if 70 <= median_gap <= 110:
                frequency = "quarterly"
            elif 20 <= median_gap <= 45:
                frequency = "monthly"
            else:
                continue

            # CV check on month gaps (looser for calendar-month detector)
            if len(month_gaps):
                std = float(np.std(month_gaps, ddof=0))
                cv = std / median_gap if median_gap else float("inf")
                if cv > 0.5:
                    continue
            else:
                cv = 0.0

            candidates.append(
                _series_from_group(near, frequency, cv, dataset_max)
            )
    return candidates


def _merge_candidates(candidates: list[dict]) -> pd.DataFrame:
    if not candidates:
        return empty_recurring_dataframe()

    kept: list[dict] = []
    for cand in sorted(
        candidates,
        key=lambda c: (-c["_occurrences"], c["_gap_cv"]),
    ):
        duplicate = False
        for existing in kept:
            if cand["_normalized"] != existing["_normalized"]:
                continue
            if not _amounts_similar(cand["amount"], existing["amount"]):
                continue
            # Overlapping or adjacent date ranges for same merchant+amount
            latest_start = max(cand["start_date"], existing["start_date"])
            earliest_end = min(cand["end_date"], existing["end_date"])
            if latest_start <= earliest_end + pd.Timedelta(days=45):
                duplicate = True
                break
        if not duplicate:
            kept.append(cand)

    rows = []
    for item in kept:
        rows.append({col: item[col] for col in RESULT_COLUMNS})

    result = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    if result.empty:
        return empty_recurring_dataframe()

    result["active_sort"] = result["active"].astype(int)
    result = result.sort_values(
        by=["active_sort", "amount"], ascending=[False, False]
    ).drop(columns=["active_sort"])
    result["active"] = result["active"].map({True: "Yes", False: "No"})
    result = result.reset_index(drop=True)
    return result


def detect_recurring_payments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect recurring payments using multiple algorithms and merge results.

    Parameters
    ----------
    df : pandas.DataFrame
        Transactions with Date, Amount, Description, Source. Optional Category.

    Returns
    -------
    pandas.DataFrame
        Columns: name, amount, credit_card, category, start_date, end_date,
        frequency, active ("Yes"/"No").
    """
    work, dataset_max = _prepare(df)
    if dataset_max is None or work.empty:
        return empty_recurring_dataframe()

    candidates: list[dict] = []
    candidates.extend(_detector_exact_desc_amount(work, dataset_max))
    candidates.extend(_detector_amount_tolerant(work, dataset_max))
    candidates.extend(_detector_day_of_month(work, dataset_max))
    return _merge_candidates(candidates)


def format_recurring_for_display(recurring_df: pd.DataFrame) -> pd.DataFrame:
    """Rename result columns to user-facing headers for UI/HTML export."""
    if recurring_df is None or recurring_df.empty:
        return pd.DataFrame(columns=list(DISPLAY_COLUMNS.values()))
    out = recurring_df.copy()
    # Ensure expected columns exist
    for col in RESULT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[RESULT_COLUMNS].rename(columns=DISPLAY_COLUMNS)
    return out
