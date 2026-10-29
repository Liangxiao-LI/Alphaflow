"""Prediction timing, label and universe contract.

The contract is defined in ``configs/prediction_contract.yaml`` and explained in
``docs/PREDICTION_CONTRACT.md``. Trading sessions are supplied by a ``TradingCalendar``
built from observed trading dates (in production: the curated benchmark price series),
so this module carries no hard-coded holiday list.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

DEFAULT_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "configs" / "prediction_contract.yaml"


class ContractError(ValueError):
    """Raised for an invalid contract definition or an out-of-contract query."""


class TradingCalendar:
    """Ordered set of trading session dates."""

    def __init__(self, sessions: Iterable[date | str | pd.Timestamp]):
        normalized = sorted({pd.Timestamp(s).date() for s in sessions})
        if not normalized:
            raise ContractError("Trading calendar is empty")
        self._sessions = normalized
        self._index = {d: i for i, d in enumerate(normalized)}

    @property
    def sessions(self) -> list[date]:
        return list(self._sessions)

    def is_session(self, day: date) -> bool:
        return day in self._index

    def offset(self, day: date, n: int) -> date:
        """Return the session ``n`` sessions after ``day`` (which must itself be a session)."""
        if day not in self._index:
            raise ContractError(f"{day} is not a trading session")
        target = self._index[day] + n
        if not 0 <= target < len(self._sessions):
            raise ContractError(f"{day} offset by {n} sessions falls outside the calendar")
        return self._sessions[target]


@dataclass(frozen=True)
class UniverseRules:
    exchanges: tuple[str, ...]
    security_categories: tuple[str, ...]
    min_close_price: float
    min_median_dollar_volume: float
    dollar_volume_window_sessions: int
    min_history_sessions: int
    include_subsequently_delisted: bool

    def eligible(self, snapshot: pd.DataFrame) -> pd.Series:
        """Boolean mask over a per-security snapshot taken at the signal cutoff.

        Required columns: ``exchange``, ``category``, ``close``, ``median_dollar_volume``,
        ``history_sessions``. Values must be computed from data available at the cutoff.
        """
        return (
            snapshot["exchange"].isin(self.exchanges)
            & snapshot["category"].isin(self.security_categories)
            & (snapshot["close"] >= self.min_close_price)
            & (snapshot["median_dollar_volume"] >= self.min_median_dollar_volume)
            & (snapshot["history_sessions"] >= self.min_history_sessions)
        )


@dataclass(frozen=True)
class PredictionContract:
    version: int
    timezone: str
    cutoff_time: time
    execution_session_offset: int
    execution_price: str
    horizon_trading_days: int
    return_type: str
    benchmark: str
    universe: UniverseRules

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def signal_cutoff(self, as_of_date: date) -> datetime:
        """Latest ``available_at`` (UTC) a record may have to be used for ``as_of_date``."""
        local = datetime.combine(as_of_date, self.cutoff_time, tzinfo=self.tz)
        return local.astimezone(UTC)

    def execution_session(self, as_of_date: date, calendar: TradingCalendar) -> date:
        return calendar.offset(as_of_date, self.execution_session_offset)

    def label_window(self, as_of_date: date, calendar: TradingCalendar) -> tuple[date, date]:
        """(start, end) sessions of the forward return, both at the execution price."""
        start = self.execution_session(as_of_date, calendar)
        return start, calendar.offset(start, self.horizon_trading_days)

    def label_available_at(self, as_of_date: date, calendar: TradingCalendar) -> datetime:
        _, end = self.label_window(as_of_date, calendar)
        return self.signal_cutoff(end)

    def is_label_mature(self, as_of_date: date, now: datetime, calendar: TradingCalendar) -> bool:
        if now.tzinfo is None:
            raise ContractError("`now` must be timezone-aware")
        try:
            return now >= self.label_available_at(as_of_date, calendar)
        except ContractError:
            # End of label window lies beyond known sessions: not yet observable.
            return False


def load_contract(path: Path | str = DEFAULT_CONTRACT_PATH) -> PredictionContract:
    raw = yaml.safe_load(Path(path).read_text())
    try:
        signal, execution, label, universe = (
            raw["signal"],
            raw["execution"],
            raw["label"],
            raw["universe"],
        )
        contract = PredictionContract(
            version=int(raw["version"]),
            timezone=str(raw["timezone"]),
            cutoff_time=time.fromisoformat(str(signal["cutoff_time"])),
            execution_session_offset=int(execution["session_offset"]),
            execution_price=str(execution["price"]),
            horizon_trading_days=int(label["horizon_trading_days"]),
            return_type=str(label["return_type"]),
            benchmark=str(label["benchmark"]),
            universe=UniverseRules(
                exchanges=tuple(universe["exchanges"]),
                security_categories=tuple(universe["security_categories"]),
                min_close_price=float(universe["min_close_price"]),
                min_median_dollar_volume=float(universe["min_median_dollar_volume"]),
                dollar_volume_window_sessions=int(universe["dollar_volume_window_sessions"]),
                min_history_sessions=int(universe["min_history_sessions"]),
                include_subsequently_delisted=bool(universe["include_subsequently_delisted"]),
            ),
        )
    except (KeyError, TypeError) as exc:
        raise ContractError(f"Malformed contract {path}: missing or invalid {exc}") from exc
    _validate(contract)
    return contract


def _validate(contract: PredictionContract) -> None:
    if contract.execution_session_offset < 1:
        raise ContractError("Execution must be at least one session after the signal date")
    if contract.horizon_trading_days < 1:
        raise ContractError("Label horizon must be positive")
    if contract.execution_price not in {"open", "close"}:
        raise ContractError("execution.price must be 'open' or 'close'")
    ZoneInfo(contract.timezone)  # raises for an unknown zone
