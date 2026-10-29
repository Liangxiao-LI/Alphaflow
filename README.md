# AlphaFlow

**A batch-first, end-to-end equity machine learning and MLOps platform powered by Nasdaq Data Link.**

AlphaFlow transforms daily equity prices and company fundamentals into **point-in-time features**, reproducible model experiments, versioned cross-sectional stock rankings, and monitored predictions. It is a portfolio engineering project focused on **data reliability, ML lifecycle management, cloud deployment, and model governance**—not an automated trading product or a promise of investment returns.

> **Project status:** Planned / under construction. Checkboxes below represent work to complete, **not** implemented features.
>
> **Data access:** Actual Nasdaq Data Link dataset entitlements, fields, historical coverage, and redistribution rights must be verified before implementation. Never commit licensed raw data or API credentials.

## Goals

- Ingest subscribed Nasdaq Data Link **daily OHLCV** and **fundamentals** reliably and incrementally.
- Build **point-in-time** training and inference datasets with explicit information-availability cutoffs.
- Predict and rank equities by **20-trading-day forward excess return** using a reproducible baseline and LightGBM challenger.
- Schedule **daily batch inference** separately from periodic model retraining.
- Deploy a containerised **prediction API** that serves stored snapshots instead of training on requests.
- Track experiments, model versions, lineage, data quality, drift, delayed-label performance, and safe model promotion.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams, data contracts, workflows, AWS deployment choices, security, and model governance.

**Core flow:** Nasdaq Data Link → ingestion → S3/Parquet data lake → point-in-time features → MLflow training/registry → daily batch scoring → prediction snapshots/PostgreSQL → FastAPI → monitoring.

**Target stack:** Python, Nasdaq Data Link SDK/Tables API, Pandera, Parquet, DuckDB, scikit-learn, LightGBM, MLflow, pytest, Ruff, FastAPI, Pydantic, Docker, GitHub Actions, AWS S3/ECR/ECS Fargate/EventBridge/Step Functions/CloudWatch/Secrets Manager/IAM. PostgreSQL is an optional serving index; add it only when needed. The initial implementation runs locally before moving to AWS.

## Milestone roadmap

Suggested duration: **8 weeks at roughly 10–15 focused hours/week**, depending on data access and AWS experience. Milestones are defined by demonstrable outcomes, not calendar deadlines. **M0 is a mandatory gate** before relying on financial results.

### M0 — Repository and data access contract (prerequisite)

- Initialise the Python package, `pyproject.toml`, `.gitignore`, `.env.example`, Makefile or task runner, and `src/` layout.
- Confirm subscribed Nasdaq dataset codes, available columns, refresh times, historical coverage, quotas, and permitted uses.
- Verify whether fundamentals have **filing/availability timestamps** and whether revisions and delisted securities are accessible.
- Record dataset licensing restrictions; exclude market-data payloads from the public repository.
- Define the prediction cutoff (for example, after close), next actionable execution time, 20-trading-day horizon, and universe construction rules.
- Add CI skeleton: Ruff, pytest, and a smoke test with **synthetic** fixtures.

**Done when:** `pytest` and lint checks pass locally/in CI; a documented entitlement matrix identifies supported datasets and any point-in-time limitations; no secrets or licensed market data are committed.

**M0 deliverables:**

- Package scaffold: `pyproject.toml`, `src/alphaflow/`, `Makefile`, `.env.example`, `.gitignore`, and CI in `.github/workflows/ci.yml` (Ruff lint and format, pytest on Python 3.11/3.12).
- [docs/DATA_ACCESS.md](docs/DATA_ACCESS.md): the entitlement matrix, API limits, point-in-time limitations and licensing rules. `make entitlements` probes account access without storing any data rows.
- [docs/PREDICTION_CONTRACT.md](docs/PREDICTION_CONTRACT.md) and `configs/prediction_contract.yaml`: the signal cutoff, next-session execution, the 20-day excess-return label and universe rules. These are implemented in `alphaflow.contracts`.
- Synthetic fixtures (`alphaflow.data.synthetic`) and tests, including repository-hygiene checks for secrets and data files.
- **Outstanding:** run `make entitlements` with a real key and record the results in the matrix. Until then every dataset is marked *UNVERIFIED*.

### M1 — Reliable daily data ingestion (Week 1)

- Implement a Nasdaq client with API-key environment configuration, pagination, rate-limit handling, exponential backoff, and timeouts.
- Implement incremental OHLCV and fundamentals extraction using persistent watermarks, with an overlap window for corrections.
- Save original extracts in immutable/run-scoped `raw/` storage; normalise to partitioned Parquet in `curated/`.
- Validate schema, types, uniqueness, nulls, price/volume constraints, and expected trading-date coverage.
- Record ingestion run IDs, source dataset, extraction timestamp, row counts, checksums, status, and failures.
- Test idempotent reruns, pagination, duplicates, partial failures, missing days, and API throttling using mock data.

**Done when:** Replaying the same batch twice produces no duplicate curated records; a failed run can be retried without overwriting the last valid snapshot; tests pass without live API access.

### M2 — Point-in-time feature pipeline (Week 2)

- Define stable security identifiers, ticker mapping rules, adjustment policy, and historical universe criteria.
- Build technical features (momentum, realised volatility, volume/liquidity) using only data available by the signal cutoff.
- Build fundamental features (value, quality, growth) using **availability-aware joins**, not financial period-end dates alone.
- Version feature definitions and persist `features/` snapshots with an explicit `as_of_date`, `available_at`, and `feature_set_version`.
- Define the 20-trading-day forward **excess-return label** using a consistent total-return/adjustment convention.
- Test no future fundamental values, no use of future labels, and correct behavior around missing filings, revisions, corporate actions, and delistings where data permits.

**Done when:** A historical replay produces the same feature values for a past cutoff; intentionally late-reported financial data fails leakage checks. **If true point-in-time fundamentals are unavailable, disclose the limitation and do not describe the evaluation as fully point-in-time.**

### M3 — Reproducible model training and evaluation (Week 3)

- Implement a naive ranking benchmark and a Ridge regression baseline.
- Train a LightGBM ranker/regressor on the same frozen historical feature snapshot.
- Use chronological walk-forward evaluation with appropriate purge/embargo for overlapping 20-day targets and security-universe controls.
- Compute Spearman rank IC, IC by period, coverage, and calibration/quantile diagnostics where applicable.
- Track parameters, dataset snapshot IDs, feature version, Git commit, dependencies, artifacts, and metrics in MLflow.
- Register candidate models without automatically replacing the champion.

**Done when:** A documented command reproduces the training/evaluation pipeline from a frozen data snapshot and creates a traceable MLflow run plus candidate model; results are compared against baselines.

### M4 — Investment-aware evaluation (Week 4)

- Convert rankings into a clearly specified long-only or long/short **paper** portfolio rule.
- Use next-session execution assumptions and account for tradability, trading costs, turnover, and rebalancing.
- Calculate gross/net returns, drawdown, Sharpe, turnover, exposure, and benchmark comparison.
- Add robustness checks across market regimes and across time; include delisted names if historical data supports them.
- Document survivorship bias, publication timing, adjusted-prices assumptions, and all known data limitations.

**Done when:** An independently rerunnable evaluation report separates model-quality metrics from investment-backtest metrics and states its assumptions clearly. Strong backtested returns are **not** a prerequisite.

### M5 — Batch scoring and prediction API (Week 5)

- Implement a daily scoring job loading the approved model by immutable version/artifact reference.
- Produce an immutable snapshot of scores, ranks, `as_of_date`, model version, data snapshot, feature version, and run ID.
- Publish the new snapshot atomically only after validation; retain the prior snapshot on failure.
- Implement FastAPI endpoints: `GET /health`, `GET /model`, `GET /predictions?as_of_date=...`.
- Add request validation, pagination, sensible errors, authentication for any internet-accessible deployment, and API tests.
- Containerise the service and batch entrypoints; run locally via Docker Compose or equivalent.

**Done when:** Local containers serve a known prediction snapshot; tests validate schemas and failure responses; the API remains usable when Nasdaq is unavailable.

### M6 — Cloud deployment and CI/CD (Week 6)

- Build and test containers in GitHub Actions; publish images to Amazon ECR using short-lived AWS credentials (OIDC).
- Store raw/curated/features/predictions in private S3 buckets/prefixes with scoped IAM access.
- Run ingestion, feature generation, and scoring as scheduled or on-demand ECS Fargate tasks.
- Use EventBridge Scheduler for start times and Step Functions for dependent steps, retries, and explicit failure paths.
- Deploy the read-only API on ECS **only if** a live hosted demo is worthwhile; otherwise document a local API and scheduled cloud pipeline.
- Configure secrets, structured logs, artifact retention, cost alerts, and least-privilege networking/permissions.

**Done when:** A reproducible CI run builds and deploys an image, and an AWS workflow processes one batch without a laptop. Capture the deployment commit, execution logs, and cost estimate.

### M7 — Observability, model governance, and safe retraining (Week 7)

- Monitor data arrival/freshness, ingestion failures, null rates, feature distribution shifts, batch duration, API errors, and model/feature version usage.
- Evaluate realised 20-day predictions **only after labels mature**; report rank IC and quality changes by evaluation period.
- Add alert thresholds with runbook links; classify data drift separately from proven performance degradation.
- Automate periodic challenger training and benchmark/champion comparison, but require explicit promotion criteria.
- Demonstrate model promotion, smoke test, failed-challenger rejection, and rollback to the prior known-good version.
- Replay simulated failures: missing data, duplicate batch, future-dated filing, and underperforming challenger.

**Done when:** A replayed failure raises a visible alert or fails a gate, preserves the last good production output, and produces an auditable event log.

### M8 — Portfolio presentation and evidence (Week 8)

- Publish architecture and sequence diagrams with final implemented components clearly identified.
- Add a small optional dashboard for model/operational metrics and historical *paper* rankings.
- Record a 3–5 minute demo: ingest → validate → train → register → score → serve → detect failure → recover.
- Document setup commands, tests, expected resource usage, cost considerations, limitations, and data-license-safe synthetic examples.
- Add final measured evidence: stocks scored, execution time, test results, API latency, pipeline success rate, and evaluation metrics.
- Write CV bullets reflecting **only built and verified features**, with measured results rather than invented performance claims.

**Done when:** A reviewer can clone the public repository, run tests and a synthetic-data demo without Nasdaq credentials, and understand the production design from the docs.

## Milestone tracker

| Milestone | Deliverable                                      | Dependencies        | Status        |
| --------- | ------------------------------------------------ | ------------------- | ------------- |
| M0        | Repo, contracts, permissions, synthetic fixtures | None                | 🟨 Scaffolded — entitlement probe pending |
| M1        | Resilient incremental ingestion                  | M0                  | ⬜ Not started |
| M2        | Point-in-time feature snapshots                  | M1                  | ⬜ Not started |
| M3        | Reproducible training and MLflow lineage         | M2                  | ⬜ Not started |
| M4        | Cost-aware evaluation report                     | M3                  | ⬜ Not started |
| M5        | Versioned batch predictions and API              | M3 (M4 recommended) | ⬜ Not started |
| M6        | AWS workload and CI/CD                           | M1, M5              | ⬜ Not started |
| M7        | Monitoring, promotion, rollback                  | M3, M5, M6          | ⬜ Not started |
| M8        | Demo, documentation and CV evidence              | M0–M7               | ⬜ Not started |

## Getting started (planned)

The setup, lint, test and entitlement commands work as of M0. The pipeline entrypoints further down are **planned** and do not exist yet.

```
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'    # or: make install
cp .env.example .env       # Add a personal key locally; never commit .env
make check                 # ruff check + ruff format --check + pytest (synthetic data only)
make entitlements          # Probe Nasdaq table access (needs NASDAQ_API_KEY)

# Example future entrypoints (not implemented yet):
python -m alphaflow.ingestion.run --date 2026-10-27
python -m alphaflow.models.train --config configs/train.yaml
python -m alphaflow.inference.daily_scoring --date 2026-10-27
uvicorn alphaflow.api.main:app --reload
```

## Planned repository layout

```
alphaflow/
├── src/alphaflow/
│   ├── ingestion/       # Nasdaq client, incremental loading, metadata
│   ├── data/            # Storage, contracts, validation
│   ├── features/        # PIT joins, technical/fundamental signals
│   ├── models/          # Baselines, training, evaluation, registry
│   ├── inference/       # Daily scoring and immutable publication
│   ├── monitoring/      # Quality, drift, delayed-label metrics
│   ├── api/             # Read-only prediction API
│   └── workflows/       # Daily and periodic orchestration
├── tests/               # Synthetic fixtures + unit/integration tests
├── configs/             # Versioned runtime/training configuration
├── infra/               # Cloud definitions (Terraform, later)
├── .github/workflows/   # CI/CD
├── ARCHITECTURE.md
├── README.md
├── pyproject.toml
└── Dockerfile
```

## Non-goals (for the first release)

- Live execution, brokerage integration, personalised investment advice, or production trading.
- Real-time tick ingestion, Kafka, Kubernetes, and distributed Spark solely for appearance.
- Hosting or republishing licensed Nasdaq data in the public repo.
- Claims that historical backtests imply future investment performance.

## Portfolio success criteria

The finished repo should prove: **idempotent ingestion; no look-ahead leakage (to the extent the available datasets support); versioned features and models; repeatable training; safe deployment; monitoring with delayed labels; and recoverable failure handling.**

**Disclaimer:** AlphaFlow is an educational engineering project. Model outputs are not investment advice. Nasdaq Data Link and dataset-provider licensing terms apply.
