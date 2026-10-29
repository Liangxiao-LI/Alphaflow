"""Prediction timing, label horizon and universe rules."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
import yaml

from alphaflow.contracts import DEFAULT_CONTRACT_PATH, ContractError, TradingCalendar, load_contract


def test_default_contract_values(contract):
    assert contract.version == 1
    assert contract.horizon_trading_days == 20
    assert contract.execution_session_offset == 1
    assert contract.benchmark == "SPY"


@pytest.mark.parametrize(
    ("as_of", "expected_utc"),
    [
        # 20:00 New York in winter (UTC-5) and summer (UTC-4).
        (date(2024, 1, 10), datetime(2024, 1, 11, 1, 0, tzinfo=UTC)),
        (date(2024, 7, 10), datetime(2024, 7, 11, 0, 0, tzinfo=UTC)),
    ],
)
def test_signal_cutoff_is_dst_aware(contract, as_of, expected_utc):
    assert contract.signal_cutoff(as_of) == expected_utc


def test_execution_is_next_session_after_weekend(contract, calendar):
    assert contract.execution_session(date(2024, 1, 5), calendar) == date(2024, 1, 8)


def test_label_window_spans_horizon_sessions(contract, calendar):
    start, end = contract.label_window(date(2024, 1, 5), calendar)
    sessions = calendar.sessions
    assert start == date(2024, 1, 8)
    assert sessions.index(end) - sessions.index(start) == 20


def test_label_maturity(contract, calendar):
    as_of = date(2024, 1, 5)
    available = contract.label_available_at(as_of, calendar)
    assert not contract.is_label_mature(as_of, available - timedelta(seconds=1), calendar)
    assert contract.is_label_mature(as_of, available, calendar)


def test_label_beyond_calendar_is_not_mature(contract, calendar):
    last = calendar.sessions[-1]
    assert not contract.is_label_mature(last, datetime(2100, 1, 1, tzinfo=UTC), calendar)


def test_naive_now_rejected(contract, calendar):
    naive = datetime(2024, 3, 1)
    with pytest.raises(ContractError):
        contract.is_label_mature(date(2024, 1, 5), naive, calendar)


def test_non_session_date_rejected(contract, calendar):
    with pytest.raises(ContractError, match="not a trading session"):
        contract.execution_session(date(2024, 1, 6), calendar)  # Saturday


def test_empty_calendar_rejected():
    with pytest.raises(ContractError):
        TradingCalendar([])


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("execution", "session_offset", 0),
        ("label", "horizon_trading_days", 0),
        ("execution", "price", "vwap"),
    ],
)
def test_invalid_contract_rejected(tmp_path, section, key, value):
    raw = yaml.safe_load(DEFAULT_CONTRACT_PATH.read_text())
    raw[section][key] = value
    path = tmp_path / "contract.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ContractError):
        load_contract(path)


def test_universe_rules(contract):
    snapshot = pd.DataFrame(
        {
            "exchange": ["NYSE", "NASDAQ", "NYSE", "OTC", "NYSE", "NASDAQ"],
            "category": ["common_stock"] * 4 + ["etf", "common_stock"],
            "close": [50.0, 4.0, 50.0, 50.0, 50.0, 50.0],
            "median_dollar_volume": [1e7, 1e7, 1e6, 1e7, 1e7, 1e7],
            "history_sessions": [500, 500, 500, 500, 500, 100],
        }
    )
    eligible = contract.universe.eligible(snapshot).tolist()
    # ok, penny stock, illiquid, wrong exchange, ETF, too little history
    assert eligible == [True, False, False, False, False, False]
