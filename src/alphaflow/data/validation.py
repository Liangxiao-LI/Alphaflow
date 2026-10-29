"""Lightweight daily OHLCV checks. Pandera schemas replace/extend these in M1."""

from __future__ import annotations

import pandas as pd

OHLCV_COLUMNS = ("ticker", "date", "open", "high", "low", "close", "volume")


def validate_ohlcv(frame: pd.DataFrame) -> list[str]:
    """Return human-readable violations; an empty list means the frame passed."""
    missing = [c for c in OHLCV_COLUMNS if c not in frame.columns]
    if missing:
        return [f"missing columns: {missing}"]

    errors: list[str] = []
    if frame[list(OHLCV_COLUMNS)].isna().any().any():
        errors.append("null values in required columns")
    if frame.duplicated(subset=["ticker", "date"]).any():
        errors.append("duplicate (ticker, date) rows")
    prices = frame[["open", "high", "low", "close"]]
    if (prices <= 0).any().any():
        errors.append("non-positive prices")
    if (frame["high"] < prices.max(axis=1)).any() or (frame["low"] > prices.min(axis=1)).any():
        errors.append("high/low inconsistent with open/close")
    if (frame["volume"] < 0).any():
        errors.append("negative volume")
    return errors
