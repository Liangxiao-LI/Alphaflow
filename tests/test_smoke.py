"""Smoke tests: the package imports and synthetic fixtures honour the data contracts."""

from __future__ import annotations

import importlib

import pandas as pd
import pytest

from alphaflow.data import synthetic
from alphaflow.data.validation import validate_ohlcv

SUBPACKAGES = [
    "ingestion",
    "data",
    "features",
    "models",
    "inference",
    "monitoring",
    "api",
    "workflows",
]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackages_import(name):
    assert importlib.import_module(f"alphaflow.{name}") is not None


def test_synthetic_prices_pass_validation(prices):
    assert validate_ohlcv(prices) == []


def test_synthetic_data_is_deterministic(security_master, sessions):
    first = synthetic.make_prices(security_master, sessions, seed=3)
    second = synthetic.make_prices(security_master, sessions, seed=3)
    pd.testing.assert_frame_equal(first, second)


def test_delisted_security_stops_trading(prices, security_master, sessions):
    delisted = security_master.loc[security_master["is_delisted"], "ticker"].item()
    last_date = prices.loc[prices["ticker"] == delisted, "date"].max()
    assert last_date < pd.Timestamp(sessions[-1])


def test_prices_published_after_session_close(prices):
    close_local = (prices["date"] + pd.Timedelta(hours=16)).dt.tz_localize("America/New_York")
    assert (prices["available_at"] > close_local).all()


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("close", -1.0, "non-positive prices"),
        ("volume", -5, "negative volume"),
        ("high", 0.01, "high/low inconsistent with open/close"),
    ],
)
def test_validation_catches_bad_rows(prices, column, value, message):
    bad = prices.head(5).copy()
    bad.loc[bad.index[0], column] = value
    assert message in validate_ohlcv(bad)


def test_validation_catches_duplicates(prices):
    bad = pd.concat([prices.head(3), prices.head(1)])
    assert "duplicate (ticker, date) rows" in validate_ohlcv(bad)


def test_fundamentals_available_only_after_period_end(fundamentals):
    period_end_utc = fundamentals["period_end"].dt.tz_localize("UTC")
    assert (fundamentals["available_at"] > period_end_utc).all()


def test_restatement_hidden_before_its_availability(fundamentals, contract):
    restated = fundamentals[fundamentals["is_restatement"]].iloc[0]
    same_period = (fundamentals["ticker"] == restated["ticker"]) & (
        fundamentals["period_end"] == restated["period_end"]
    )
    original = fundamentals[same_period & ~fundamentals["is_restatement"]].iloc[0]

    # A cutoff between the original filing and the restatement sees only the original.
    between = (original["available_at"] + pd.Timedelta(days=30)).date()
    visible = fundamentals[
        same_period & (fundamentals["available_at"] <= contract.signal_cutoff(between))
    ]
    assert len(visible) == 1
    assert not visible["is_restatement"].item()
