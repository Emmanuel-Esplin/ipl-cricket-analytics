# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

IPL cricket lakehouse built on Cricsheet's free ball-by-ball data (every IPL match since 2008):
wins and losses per team, strike rate per game, batting and bowling stats, strike rate by
phase and batter-v-bowler matchups. Metric definitions are in `docs/metrics.md`; read it before
changing any scoring rule or mart.

## Commands

All targets run through the Makefile, which uses `.venv/bin/python` and sets `PYTHONPATH`.

```bash
make install        # venv in .venv.nosync (symlinked to .venv), data.nosync symlinked to data
make lint           # ruff check + ruff format --check (line length 100)
make test           # pytest -q (builds invented matches end to end through dbt)
make ingest         # download Cricsheet's IPL zip (~5 MB) into bronze; only new/revised matches
make silver         # rebuild every silver table from bronze (~2 seconds)
make gold           # silver, then `dbt build` on DuckDB -> data/gold/warehouse.duckdb
make dashboard      # Streamlit on 127.0.0.1:8501 (reads the DuckDB warehouse)
make schemas        # regenerate infra/silver_schemas.json from processing/silver.py
make tf-check       # terraform fmt/validate/test; no AWS credentials needed (mocked provider)
```

Don't run any AWS target (`tf-plan`, `tf-apply`, `image-push`, `bronze-upload`,
`pipeline-run`, `dbt-athena`) unless asked; show a Terraform plan before applying it.

## Environment quirks

- The repo path contains a space ("Data Engineer"); quote paths in shell commands.
- The repo lives in an iCloud-synced Desktop. Anything large or hot (venv, data, Terraform
  providers, plan files) goes in a `*.nosync` path. `TF_DATA_DIR` is `.terraform.nosync`.

## Architecture

```
Cricsheet ipl_json.zip -> bronze (raw JSON per match) -> silver (Parquet) -> dbt -> marts -> Streamlit
```

The same Python code runs locally and in AWS Lambda; only `IPL_DATA_DIR` changes
(`data` or `s3://<bucket>`).

- **Ingestion** (`ingestion/cricsheet.py`): downloads the zip and writes
  `bronze/cricsheet/matches/season=YYYY/match_id=N.json`. A sha256 manifest
  (`bronze/cricsheet/_manifest.json`) skips unchanged matches.
- **Silver** (`processing/silver.py`): `SCHEMAS` and `TABLES` are the single source of truth
  for matches, innings, deliveries, wickets and players. After changing a schema run
  `make schemas`; a test fails if Glue's copy drifts.
- **dbt** (`transform/`): staging (views, where the cricket rules live) -> intermediate ->
  marts. SQL must run on DuckDB and Athena/Trino: no `QUALIFY`, `arg_max`, `any_value`.
  `silver()` and `ratio()` macros are in `macros/silver.sql`. The `reconcile` test only passes
  on real data, so the pytest build excludes it.
- **Dashboard** (`dashboard/app.py`): Streamlit + Altair; season marts keep raw sums so "All
  seasons" recomputes rates. Dependencies in `dashboard/requirements.txt`, kept out of the lock.
- **AWS** (`infra/`, `Dockerfile`, `ingestion/lambda_handler.py`): one arm64 Lambda image with
  three handlers, Step Functions runs ingest -> silver -> dbt (Athena) daily via EventBridge
  Scheduler; S3 + Glue (partition projection) + Athena workgroup with a 1 GB scan cap; budget
  alert; SNS email on failure.
