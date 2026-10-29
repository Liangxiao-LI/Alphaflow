"""Guardrails: no secrets or licensed market data in version control."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = (".parquet", ".csv", ".csv.gz", ".feather", ".arrow", ".duckdb", ".zip")


def tracked_files() -> list[str]:
    git = shutil.which("git")
    if git is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    result = subprocess.run(  # noqa: S603
        [git, "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.splitlines()


def test_no_env_or_data_files_tracked():
    offenders = [
        f
        for f in tracked_files()
        if Path(f).name == ".env" or f.lower().endswith(FORBIDDEN_SUFFIXES)
    ]
    assert offenders == []


def test_api_key_value_not_committed():
    key = os.environ.get("NASDAQ_API_KEY")
    if not key:
        pytest.skip("NASDAQ_API_KEY not set locally")
    offenders = [
        f
        for f in tracked_files()
        if (ROOT / f).is_file() and key in (ROOT / f).read_text(errors="ignore")
    ]
    assert offenders == []


def test_env_example_has_no_secret_values():
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line.startswith("NASDAQ_API_KEY="):
            assert line == "NASDAQ_API_KEY="
