"""Shared synthetic fixtures. Tests never need network access or a Nasdaq key."""

from __future__ import annotations

import pandas as pd
import pytest

from alphaflow.contracts import PredictionContract, TradingCalendar, load_contract
from alphaflow.data import synthetic


@pytest.fixture(scope="session")
def sessions():
    return synthetic.make_sessions(start="2024-01-02", periods=300)


@pytest.fixture(scope="session")
def calendar(sessions) -> TradingCalendar:
    return TradingCalendar(sessions)


@pytest.fixture(scope="session")
def contract() -> PredictionContract:
    return load_contract()


@pytest.fixture(scope="session")
def security_master() -> pd.DataFrame:
    return synthetic.make_security_master()


@pytest.fixture(scope="session")
def prices(security_master, sessions) -> pd.DataFrame:
    return synthetic.make_prices(security_master, sessions)


@pytest.fixture(scope="session")
def fundamentals(security_master, sessions) -> pd.DataFrame:
    return synthetic.make_fundamentals(security_master, sessions)
