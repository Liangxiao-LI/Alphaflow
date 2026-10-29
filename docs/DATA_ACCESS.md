# Data access contract and entitlement matrix

**Purpose:** record which Nasdaq Data Link tables AlphaFlow may use, what each one can and cannot support for point-in-time (PIT) research, and the licensing rules for the repository. This is the M0 gate: later milestones can rely only on tables marked **Verified** here.

> **Verification state (2026-10-29): NOT YET VERIFIED FOR THIS ACCOUNT.**
> The vendor-documented properties below come from public Nasdaq Data Link / Sharadar documentation. They are design assumptions until `make entitlements` is run with the project's key and the *Account access* column is filled in from its report.

## 1. How to verify entitlements

```bash
cp .env.example .env            # add NASDAQ_API_KEY locally; never commit .env
make entitlements               # = python -m alphaflow.ingestion.entitlements
```

For each candidate in [`configs/entitlements.yaml`](../configs/entitlements.yaml) the probe:

1. requests table **metadata** (columns, filters, primary key, `premium`, `status.refreshed_at`, `status.update_frequency`);
2. requests **one row of one column** (`qopts.per_page=1`, `qopts.columns=<first column>`) and keeps only the HTTP status (`200` accessible, `403` not subscribed, `401` invalid key, `429` rate-limited);
3. writes a JSON report to `reports/entitlements/` (gitignored) and prints a Markdown summary to paste into §3.

It never stores data rows. The API key is redacted from error messages.

**After probing, also check by hand** (these cannot be inferred from a single request):

- [ ] Run the probe on 3+ different days and record `refreshed_at`. That establishes the real publication window, which sets `signal.cutoff_time` in `configs/prediction_contract.yaml`.
- [ ] For each accessible table, confirm the earliest available date (history depth) with a filtered query run locally. Do not commit the output.
- [ ] Confirm that a known delisted ticker returns history (survivorship coverage).
- [ ] Confirm that you have the full subscription, not a free *sample* (Sharadar samples return HTTP 200 but only a subset of tickers).
- [ ] Read the subscription's licence terms and fill in §5.

## 2. API usage limits (vendor-documented; verify on account page)

| Item | Documented value | AlphaFlow handling (M1) |
| --- | --- | --- |
| Authenticated rate limit | 300 calls / 10 s; 2,000 calls / 10 min; 50,000 calls / day | Client-side throttle well below limits; exponential backoff on `429` |
| Tables API page size | 10,000 rows per page, cursor via `meta.next_cursor_id` → `qopts.cursor_id` | Follow cursors until exhausted; checkpoint per page |
| Bulk download | `qopts.export=true` returns a zipped file link | Use for initial backfill; incremental queries thereafter |
| Filters | Only columns listed in metadata `filters` can be filtered server-side | Probe report records them; incremental extraction filters on `lastupdated` where supported |

## 3. Entitlement matrix

*Account access* is `UNVERIFIED` until it is replaced with the probe output: `accessible` / `not_subscribed` / `sample-only`, plus the probe date.

| Table | Role | Account access | PIT availability timestamp | Revisions / vintages | Delisted coverage | Refresh (documented) | History (documented) | Key limitations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `SHARADAR/SEP` | Daily equity OHLCV | UNVERIFIED | None per row. Use `date` + the observed publication window. `lastupdated` marks changes | Prices are **retroactively re-adjusted** after splits (`open/high/low/close` split-adjusted; `closeadj` split+dividend adjusted; `closeunadj` raw) | Yes (vendor) | Daily, after US close | ~1998+ | Must snapshot raw extracts per run to reconstruct as-of adjustments; use `closeunadj` for price-level universe filters |
| `SHARADAR/SFP` | Benchmark (SPY) prices | UNVERIFIED | As SEP | As SEP | Yes (vendor) | Daily | ~1998+ | Needed only for the benchmark; check that SPY is present |
| `SHARADAR/SF1` | Fundamentals | UNVERIFIED | **`datekey`** = SEC filing date (use as `available_at` date). Also `reportperiod`, `calendardate`, `lastupdated` | **AR\*** dimensions (ARQ/ARY/ART) are as-reported and exclude restatements. **MR\*** dimensions include restatements and are **not PIT-safe** | Yes (vendor) | Daily | ~1998+ | `datekey` is a date, not a timestamp: treat it as available after that day's cutoff (conservative +1 session). AlphaFlow uses **AR\* only** |
| `SHARADAR/TICKERS` | Security master | UNVERIFIED | `firstpricedate`, `lastpricedate`, `lastupdated` | Current snapshot only: exchange, category and sector reflect **today**, not history | `isdelisted` flag | Daily | N/A | Historical exchange/category membership cannot be fully reconstructed. Stable ID: `permaticker` |
| `SHARADAR/ACTIONS` | Corporate actions | UNVERIFIED | `date` of the action | Append-style events | Includes delisting events | Daily | ~1998+ | Use for ticker changes and delisting returns where available |
| `SHARADAR/DAILY` | Daily valuation metrics | UNVERIFIED | `date`, `lastupdated` | Ratios may be computed from **MR\*** (restated) fundamentals | — | Daily | — | **Do not use as model input** unless the vendor confirms an as-reported basis. Recompute ratios from SEP + SF1 (ARQ) instead |
| `QUOTEMEDIA/PRICES` | Alternative prices | UNVERIFIED | `date` | Adjusted fields revised after corporate actions | Check | Daily | Check | Fallback only if SEP is unavailable |
| `ZACKS/FC` | Alternative fundamentals | UNVERIFIED | Check for a filing/announcement date column | Check | Check | Check | Check | Fallback only. Without a filing date, **fundamental features are not PIT** |

### Decision rule (applied when the matrix is filled in)

| If the probe shows… | Then |
| --- | --- |
| SEP + SFP + SF1 + TICKERS accessible (full) | Proceed with the design as written. Fundamentals are PIT via `datekey` and AR\* dimensions |
| Prices accessible, SF1 not | M2 builds technical features only. Document that fundamentals are out of scope |
| Fundamentals without filing dates | Fundamental features may only use a conservative fixed lag (for example period end + 90 days). **Disclose that the evaluation is not fully PIT** |
| No delisted coverage | Report survivorship bias in M4. Do not describe backtests as survivorship-free |

## 4. Point-in-time limitations to carry forward (known even before probing)

1. **Retroactive price adjustment.** SEP adjusted prices change after each split or dividend. Features computed from today's download for a past date use adjustment factors that were not known then. Mitigation: features use ratios (returns and volatility) that are invariant to adjustment. Price-level filters (`min_close_price`) use `closeunadj`, and raw extracts are retained per run.
2. **Filing date granularity.** `datekey` has no time of day. A filing at 16:05 ET on day D could be treated as known at D's 20:00 cutoff. AlphaFlow conservatively makes it available at the **next** session's cutoff.
3. **Security master is a current snapshot.** Historical exchange and category membership is approximated from current values. Only `firstpricedate` and `lastpricedate` are used historically.
4. **Benchmark total return.** `closeadj` for SPY includes distributions. Securities and benchmark use the same `closeadj` convention.

## 5. Licensing and repository rules

Nasdaq Data Link Terms of Use and the specific dataset licence apply. Until the subscription terms are read and recorded below, AlphaFlow assumes the most restrictive interpretation: **personal, non-commercial, non-display use; no redistribution.**

| Item | Value |
| --- | --- |
| Subscription / plan | _TBD (fill in from account page)_ |
| Licence type | _TBD_ |
| Redistribution of raw or derived data | Assumed **prohibited** |
| Publishing aggregated metrics (IC, Sharpe) | Assumed permitted; confirm |
| Publishing per-security predictions | Assumed **prohibited** publicly. The API must require authentication |

Enforced in the repository:

- `.gitignore` excludes `/data/`, `/raw/`, `/curated/`, `/features/`, `/labels/`, `/predictions/`, `reports/entitlements/`, `mlruns/`, and all `*.parquet`, `*.csv`, `*.feather`, `*.arrow`, `*.duckdb` and `*.zip` files.
- `tests/test_repo_hygiene.py` fails CI if any tracked file is `.env` or has a data extension, and fails locally if the value of `NASDAQ_API_KEY` appears in a tracked file.
- Tests and demos use only `alphaflow.data.synthetic`.
- The API key is read from the environment (Secrets Manager in AWS). It is excluded from `Settings.__repr__` and redacted from probe errors.
