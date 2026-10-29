# Data access contract and entitlement matrix

**Purpose:** record which Nasdaq Data Link tables AlphaFlow may use, what each one can and cannot support for point-in-time (PIT) research, and the licensing rules for the repository. This is the M0 gate: later milestones can rely only on tables and properties recorded here **from a check run with the project's key**.

> **Rule:** nothing enters this document from memory or assumption. A table is listed only after its access has been checked with the project's key; a property (columns, timestamps, revisions, coverage, limits) is recorded only after it has been observed or confirmed in the vendor's documentation, with the source and date noted.
>
> **Verification state (2026-10-29): no tables verified yet.**

## 1. How to verify data access

Verification is done by hand, locally, with the key in `.env` (copied from `.env.example`; never commit `.env`):

- [ ] In the Nasdaq Data Link account, note which tables the subscription includes.
- [ ] For each table, make a small local request and record whether the key can access it and which columns it returns. Do not save or commit the returned rows.
- [ ] On 3+ different days, record when each table's daily data becomes available. That establishes the real publication window, which sets `signal.cutoff_time` in `configs/prediction_contract.yaml`.
- [ ] For each accessible table, confirm the earliest available date (history depth) with a filtered query run locally. Do not commit the output.
- [ ] Confirm whether delisted securities return history (survivorship coverage).
- [ ] Confirm whether the subscription is full or a sample.
- [ ] Identify which column, if any, says when each record became available (PIT timestamp), and whether past values are revised.
- [ ] Record the account's API rate limits and page sizes.
- [ ] Read the subscription's licence terms and fill in §4.

## 2. Entitlement matrix

Add one row per verified table. Every cell states what was observed and when; write `unknown` rather than guessing.

| Table | Role | Account access (check date) | PIT availability column | Revisions / vintages | Delisted coverage | Refresh (observed) | History (observed) | Limitations | Source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _none verified yet_ | | | | | | | | | |

### Decision rule (applied once the matrix is filled in)

| If the matrix shows… | Then |
| --- | --- |
| Prices and fundamentals with a PIT availability column | Proceed with the design as written |
| Prices accessible, fundamentals not | M2 builds price-based features only. Document that fundamentals are out of scope |
| Fundamentals without a PIT availability column | Fundamental features may only use a conservative fixed lag. **Disclose that the evaluation is not fully PIT** |
| No delisted coverage | Report survivorship bias in M4. Do not describe backtests as survivorship-free |

## 3. Point-in-time limitations to carry forward

_None recorded yet._ Add each limitation found during verification here, with the table it applies to and the mitigation.

## 4. Licensing and repository rules

Nasdaq Data Link Terms of Use and the specific dataset licence apply. Until the subscription terms are read and recorded below, AlphaFlow assumes the most restrictive interpretation: **personal, non-commercial, non-display use; no redistribution.**

| Item | Value |
| --- | --- |
| Subscription / plan | _TBD (fill in from account page)_ |
| Licence type | _TBD_ |
| Redistribution of raw or derived data | Assumed **prohibited** |
| Publishing aggregated metrics (IC, Sharpe) | Assumed **prohibited** until confirmed |
| Publishing per-security predictions | Assumed **prohibited** publicly. The API must require authentication |

Enforced in the repository:

- `.gitignore` excludes `/data/`, `/raw/`, `/curated/`, `/features/`, `/labels/`, `/predictions/`, `mlruns/`, and all `*.parquet`, `*.csv`, `*.feather`, `*.arrow`, `*.duckdb` and `*.zip` files.
- `tests/test_repo_hygiene.py` fails CI if any tracked file is `.env` or has a data extension, and fails locally if the value of `NASDAQ_API_KEY` appears in a tracked file.
- Tests and demos use only `alphaflow.data.synthetic`.
- The API key is read from the environment. It is excluded from `Settings.__repr__`.
