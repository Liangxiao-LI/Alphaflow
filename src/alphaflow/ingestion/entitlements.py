"""Probe which Nasdaq Data Link tables the configured API key can access.

For each candidate table the probe requests (1) table metadata and (2) a single-row,
single-column data query. Only the HTTP status, column schema and refresh metadata are
recorded; the data row is discarded and never written to disk.

Usage:
    NASDAQ_API_KEY=... python -m alphaflow.ingestion.entitlements --config configs/entitlements.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from alphaflow.config import MissingApiKeyError, load_dotenv, load_settings

# fetch(url, timeout) -> (http_status, parsed_json_or_None)
Fetch = Callable[[str, float], tuple[int, Any]]

STATUS_BY_HTTP = {
    200: "accessible",
    400: "bad_request",
    401: "invalid_key",
    403: "not_subscribed",
    404: "not_found",
    410: "not_found",
    422: "bad_request",
    429: "rate_limited",
}


@dataclass
class ProbeResult:
    code: str
    role: str
    status: str
    http_status: int | None
    columns: list[dict[str, str]] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    premium: bool | None = None
    refreshed_at: str | None = None
    update_frequency: str | None = None
    error: str | None = None
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "***") if secret else text


def http_fetch(url: str, timeout: float) -> tuple[int, Any]:
    if not url.startswith("https://"):
        raise ValueError("Only https:// URLs are allowed")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read() or b"null")
        except ValueError:
            body = None
        return exc.code, body


def probe_table(
    code: str, role: str, api_key: str, api_base: str, timeout: float, fetch: Fetch
) -> ProbeResult:
    base = f"{api_base.rstrip('/')}/datatables/{code}"
    try:
        meta_status, meta = fetch(
            f"{base}/metadata.json?{urllib.parse.urlencode({'api_key': api_key})}", timeout
        )
        table = (meta or {}).get("datatable", {}) if meta_status == 200 else {}
        columns = [
            {"name": str(c.get("name")), "type": str(c.get("type"))}
            for c in table.get("columns", [])
        ]
        query: dict[str, Any] = {"api_key": api_key, "qopts.per_page": 1}
        if columns:
            query["qopts.columns"] = columns[0]["name"]
        data_status, payload = fetch(f"{base}.json?{urllib.parse.urlencode(query)}", timeout)
        del payload  # licensed content: never retained
    except Exception as exc:  # one failing table must not abort the whole matrix
        return ProbeResult(
            code=code, role=role, status="error", http_status=None, error=redact(str(exc), api_key)
        )

    status_meta = table.get("status") or {}
    return ProbeResult(
        code=code,
        role=role,
        status=STATUS_BY_HTTP.get(data_status, "error"),
        http_status=data_status,
        columns=columns,
        filters=[str(f) for f in table.get("filters", [])],
        primary_key=[str(k) for k in table.get("primary_key", [])],
        premium=table.get("premium"),
        refreshed_at=status_meta.get("refreshed_at"),
        update_frequency=status_meta.get("update_frequency"),
    )


def to_markdown(results: list[ProbeResult]) -> str:
    lines = [
        "| Table | Role | Access | HTTP | Columns | Refreshed at | Update frequency |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| `{r.code}` | {r.role} | {r.status} | {r.http_status or '-'} | "
            f"{len(r.columns) or '-'} | {r.refreshed_at or '-'} | {r.update_frequency or '-'} |"
        )
    return "\n".join(lines)


def run(config_path: Path, api_key: str, out_dir: Path, fetch: Fetch = http_fetch) -> Path:
    config = yaml.safe_load(config_path.read_text())
    results = [
        probe_table(
            code=c["code"],
            role=c.get("role", ""),
            api_key=api_key,
            api_base=config["api_base"],
            timeout=float(config.get("timeout_seconds", 20)),
            fetch=fetch,
        )
        for c in config["candidates"]
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"entitlements_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    out_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(to_markdown(results))
    print(f"\nFull report (columns, filters, keys): {out_path}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Nasdaq Data Link table entitlements.")
    parser.add_argument("--config", type=Path, default=Path("configs/entitlements.yaml"))
    parser.add_argument("--out-dir", type=Path, default=Path("reports/entitlements"))
    args = parser.parse_args(argv)

    settings = load_settings(load_dotenv())
    try:
        api_key = settings.require_api_key()
    except MissingApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    run(args.config, api_key, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
