# Prediction contract (v1)

**Purpose:** fix *when* a prediction is made, *when* it can be acted on, *what* it predicts, and *which* securities it covers, before any model is built. Machine-readable source: [`configs/prediction_contract.yaml`](../configs/prediction_contract.yaml). Implementation: `alphaflow.contracts`. Tests: `tests/test_contracts.py`.

Changing any value is a contract change. Bump `version`, add a row to the change log, and regenerate features, labels and models.

## 1. Timing

| Term | Definition (v1) |
| --- | --- |
| Exchange timezone | `America/New_York`. All local times are DST-aware; stored timestamps are UTC |
| Trading calendar | Sessions observed in the curated **benchmark (SPY) price series**. No hard-coded holiday list |
| `as_of_date` (D) | A trading session whose closing data the prediction is based on |
| Signal cutoff | **D at 20:00 ET**. Inputs must satisfy `available_at <= cutoff(D)` |
| Execution | **Close of the next session (D+1)**, an assumed market-on-close fill |
| Label horizon | **20 trading days** |
| Label window | Close(D+1) → Close(D+21) |
| Label maturity | Label for D becomes usable at the signal cutoff of D+21 |

The 20:00 ET cutoff is provisional. It must be later than the vendor's observed publication time (see [DATA_ACCESS.md §1](DATA_ACCESS.md#1-how-to-verify-entitlements)). If daily data typically lands later, move the cutoff rather than allowing late data.

**Why next-session close rather than next open:** the vendor provides a total-return-adjusted *close* (`closeadj`) but no equivalently adjusted open. Close-to-close keeps features, labels and benchmark on one adjustment convention. It also avoids assuming a trade on D's close, which happens before the features exist.

### Worked example

| Event | Date / time (ET) | UTC |
| --- | --- | --- |
| `as_of_date` | Tue 2026-10-27 | — |
| Signal cutoff | 2026-10-27 20:00 EDT | 2026-10-28 00:00 |
| Execution (MOC) | Wed 2026-10-28 close | — |
| Label end (20 sessions later; Thanksgiving 2026-11-26 is not a session) | Wed 2026-11-25 close | — |
| Label available | 2026-11-25 20:00 EST | 2026-11-26 01:00 |

The DST change on 2026-11-01 alters the UTC offset between the cutoff and maturity times. `signal_cutoff()` handles this.

## 2. Label

```
y(i, D) = [closeadj(i, D+21) / closeadj(i, D+1) - 1] - [closeadj(SPY, D+21) / closeadj(SPY, D+1) - 1]
```

- Total-return basis (split- and dividend-adjusted `closeadj`) for both the security and the benchmark.
- **Delisting inside the window:** use the last available `closeadj` plus any delisting proceeds from `ACTIONS` if available. Otherwise the label is missing and the case is counted in a reported `delisted_in_window` diagnostic. It is never silently dropped.
- Labels are generated only after maturity and are never inference inputs.

## 3. Universe (evaluated at each D using only data available at cutoff(D))

| Rule | v1 value | Notes |
| --- | --- | --- |
| Exchanges | NYSE, NASDAQ, NYSEMKT | Taken from the security master (a current snapshot; see DATA_ACCESS §4) |
| Security category | Domestic Common Stock | Excludes ETFs, ADRs, preferreds, warrants and funds |
| Minimum price | `closeunadj(D) >= $5` | Unadjusted, so it is not distorted by later splits |
| Liquidity | Median(close × volume) over the last 20 sessions ≥ $5M | Unadjusted dollar volume |
| History | ≥ 252 sessions of price history at D | Required for 12-month features |
| Delisted names | Included while they traded | Membership never depends on future survival |

`UniverseRules.eligible()` applies the rules to a per-security snapshot. M2 builds that snapshot from curated data.

## 4. Guarantees tested in M0

- Cutoff conversion is DST-aware (winter UTC-5, summer UTC-4).
- Execution is the next *session*, skipping weekends and holidays absent from the calendar.
- The label window spans exactly `horizon_trading_days` sessions.
- A label is not mature one second before its availability time, nor when its end lies past the known calendar.
- Contracts with same-session execution, a zero horizon, or an unknown fill price are rejected.
- In the synthetic data, a restated fundamental is invisible at cutoffs before its own `available_at`.

## 5. Change log

| Version | Date | Change |
| --- | --- | --- |
| 1 | 2026-10-29 | Initial contract |
