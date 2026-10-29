"""Deterministic synthetic market data for tests and license-safe demos.

Nothing here is derived from vendor data. Shapes mirror the planned curated
contracts so tests can exercise point-in-time logic without a Nasdaq key.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import numpy as np
import pandas as pd

PRICE_PUBLISH_TIME_LOCAL = "18:00"
FILING_TIME_LOCAL = "16:30"
EXCHANGE_TZ = "America/New_York"


def make_sessions(start: str = "2024-01-02", periods: int = 300) -> list[date]:
    """Weekday sessions (no holidays): adequate for synthetic tests only."""
    return [ts.date() for ts in pd.bdate_range(start=start, periods=periods)]


def make_security_master(n_securities: int = 8) -> pd.DataFrame:
    """Security master with one ETF benchmark and one later-delisted stock."""
    rows = [
        {
            "ticker": f"SYN{i:02d}",
            "security_id": 100_000 + i,
            "exchange": "NASDAQ" if i % 2 else "NYSE",
            "category": "common_stock",
            "is_delisted": i == n_securities - 1,
        }
        for i in range(n_securities)
    ]
    rows.append(
        {
            "ticker": "SYNBM",
            "security_id": 199_999,
            "exchange": "NYSE_ARCA",
            "category": "etf",
            "is_delisted": False,
        }
    )
    return pd.DataFrame(rows)


def make_prices(master: pd.DataFrame, sessions: Sequence[date], seed: int = 7) -> pd.DataFrame:
    """Daily OHLCV with a publication timestamp; the delisted name stops trading early."""
    rng = np.random.default_rng(seed)
    frames = []
    n = len(sessions)
    for row in master.itertuples(index=False):
        length = int(n * 0.7) if row.is_delisted else n
        close = 20.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, length)))
        open_ = close * np.exp(rng.normal(0, 0.005, length))
        high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, length))
        low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, length))
        dates = pd.DatetimeIndex(pd.to_datetime(list(sessions[:length])))
        frames.append(
            pd.DataFrame(
                {
                    "ticker": row.ticker,
                    "date": dates,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "adj_close": close,
                    "volume": rng.integers(200_000, 2_000_000, length),
                    "available_at": _local_to_utc(dates, PRICE_PUBLISH_TIME_LOCAL),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def make_fundamentals(
    master: pd.DataFrame, sessions: Sequence[date], seed: int = 11
) -> pd.DataFrame:
    """Quarterly fundamentals filed 25-75 days after period end, plus one restatement."""
    rng = np.random.default_rng(seed)
    stocks = master.loc[master["category"] != "etf", "ticker"]
    quarter_ends = pd.date_range(
        start=pd.Timestamp(sessions[0]) - pd.offsets.QuarterEnd(2),
        end=pd.Timestamp(sessions[-1]),
        freq="QE",
    )
    rows = []
    for ticker in stocks:
        for period_end in quarter_ends:
            filed = period_end + pd.Timedelta(days=int(rng.integers(25, 76)))
            rows.append(
                {
                    "ticker": ticker,
                    "period_end": period_end,
                    "available_at": _local_to_utc(pd.DatetimeIndex([filed]), FILING_TIME_LOCAL)[0],
                    "revenue": float(rng.uniform(50, 500)),
                    "net_income": float(rng.normal(5, 10)),
                    "is_restatement": False,
                }
            )
    frame = pd.DataFrame(rows)
    # Restate the first filing 120 days later with a different value (a revision vintage).
    restated = frame.iloc[[0]].copy()
    restated["available_at"] += pd.Timedelta(days=120)
    restated["net_income"] -= 3.0
    restated["is_restatement"] = True
    return pd.concat([frame, restated], ignore_index=True)


def _local_to_utc(dates: pd.DatetimeIndex, hhmm: str) -> pd.DatetimeIndex:
    local = dates.normalize() + pd.Timedelta(hhmm + ":00")
    return local.tz_localize(EXCHANGE_TZ).tz_convert("UTC")
