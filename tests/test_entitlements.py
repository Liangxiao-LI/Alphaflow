"""Entitlement probe behaviour with a fake HTTP layer (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from alphaflow.ingestion import entitlements

KEY = "synthetic-key-abc"
CONFIG = Path(__file__).resolve().parents[1] / "configs" / "entitlements.yaml"

METADATA = {
    "datatable": {
        "columns": [{"name": "ticker", "type": "String"}, {"name": "date", "type": "Date"}],
        "filters": ["ticker", "date"],
        "primary_key": ["ticker", "date"],
        "premium": True,
        "status": {"refreshed_at": "2026-01-01T22:00:00.000Z", "update_frequency": "DAILY"},
    }
}


def fake_fetch(url: str, timeout: float):
    if "SHARADAR/SEP" in url:
        if "metadata" in url:
            return 200, METADATA
        return 200, {"datatable": {"data": [["SYNTHETIC-ROW"]]}}
    if "SHARADAR/SF1" in url:
        return 403, {"quandl_error": {"code": "QEPx04"}}
    raise ConnectionError(f"boom while fetching {url}")


def test_probe_classifies_access(tmp_path, capsys):
    out = entitlements.run(CONFIG, KEY, tmp_path, fetch=fake_fetch)
    report = {r["code"]: r for r in json.loads(out.read_text())}

    sep = report["SHARADAR/SEP"]
    assert sep["status"] == "accessible"
    assert [c["name"] for c in sep["columns"]] == ["ticker", "date"]
    assert sep["refreshed_at"] == "2026-01-01T22:00:00.000Z"
    assert report["SHARADAR/SF1"]["status"] == "not_subscribed"
    assert report["ZACKS/FC"]["status"] == "error"

    assert "| `SHARADAR/SEP` | daily_prices | accessible | 200 |" in capsys.readouterr().out


def test_report_contains_no_rows_or_key(tmp_path):
    text = entitlements.run(CONFIG, KEY, tmp_path, fetch=fake_fetch).read_text()
    assert "SYNTHETIC-ROW" not in text
    assert KEY not in text  # also redacted from exception messages


def test_single_row_single_column_query():
    urls: list[str] = []

    def recording_fetch(url, timeout):
        urls.append(url)
        return (200, METADATA) if "metadata" in url else (200, {})

    entitlements.probe_table(
        "SHARADAR/SEP", "daily_prices", KEY, "https://example.invalid/api/v3", 1, recording_fetch
    )
    assert "qopts.per_page=1" in urls[1]
    assert "qopts.columns=ticker" in urls[1]
