"""Runtime settings read from the environment (never from committed files)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


class MissingApiKeyError(RuntimeError):
    """Raised when a live Nasdaq call is attempted without NASDAQ_API_KEY."""


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    log_level: str = "INFO"
    # Excluded from repr so the key never reaches logs or tracebacks.
    nasdaq_api_key: str | None = field(default=None, repr=False)

    def require_api_key(self) -> str:
        if not self.nasdaq_api_key:
            raise MissingApiKeyError(
                "NASDAQ_API_KEY is not set. Copy .env.example to .env and add a personal key."
            )
        return self.nasdaq_api_key


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    return Settings(
        data_dir=Path(env.get("ALPHAFLOW_DATA_DIR") or "./data"),
        log_level=(env.get("ALPHAFLOW_LOG_LEVEL") or "INFO").upper(),
        nasdaq_api_key=env.get("NASDAQ_API_KEY") or None,
    )


def load_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    """Minimal KEY=VALUE parser so local runs need no extra dependency.

    Returns the merged mapping; values already in ``os.environ`` take precedence.
    """
    values: dict[str, str] = {}
    if path.is_file():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    return {**values, **os.environ}
