# Translator Management System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-framework-009688.svg)](https://fastapi.tiangolo.com/)

English | [中文](README_ZH.md)

Translator lifecycle, capability, rate, settlement, and risk management system for localization operations.

## Structure

- `backend/`: FastAPI backend, SQLite database, API routers, schemas, services, tests, and `run.sh`.
- `frontend/`: single-file HTML frontend.
- `translator-mgmt-agent/`: Codex/Hermes skill and API client for controlled automation from WeChat/WeCom signals.
- `archive/`: earlier single-file prototype kept for reference.

## Current Capabilities

- Translator master records with grouped detail UI, gender, and individual/vendor type.
- Multiple current or past project experiences per translator, with internal/external cooperation source.
- Per-language-pair rates with fixed language-code options and free source/target combination.
- Fixed-price and custom project prices, plus rate-change, quality, contract, complaint, and capacity records; quality ratings use cumulative LQE scores with an auditable manual override.
- Monthly capacity uses translation output × 20 workdays, defaults to 2,000 units/day, and reports idle/healthy/saturated/warning thresholds.
- Metadata-driven AND filters cover the translator record and all related business records, including typed currency-aware price ranges.
- Translator and PO grids provide Excel-style column menus with value search, multi-select, blank values, cross-column AND filtering, sorting, active-filter chips, and one-click clearing.
- PO settlement supports latest project-price matching, per-1k, hourly, fixed, and manual pricing, full manual correction, unpaid detail, and monthly/cumulative summaries.
- Projectlist supports read-only mapping preview plus checked/unchecked `结算PO` filtering; checked rows are marked as historical. Financial writes remain hard-disabled until the PO quantity rule is confirmed.
- Translator names use stable IDs with persistent aliases. Excel rows carrying an existing translator ID overwrite that record and preserve the previous name as an alias.
- Multiple encrypted payment accounts for WeChat, Alipay, personal bank, corporate CNY, and corporate USD; no default account is assigned, at least one information field is required, and QR codes are supported.
- Controlled qualification-attachment upload, authenticated download, deletion, metadata, and signature checks.
- Strict request validation for dates, months, enums, email, non-negative values, and percentage ranges.
- Translator Excel import/export with gender, entity type, and a separate project-experience sheet; duplicate rows and validation errors are reported.
- Standard PO/settlement Excel import with duplicate-PO skipping, invalid-row reporting, and language-pair rate lookup.
- LQE import, audit log, role-based access control, payment masking/encryption, and agent pending-review workflow.
- Safe agent writes with dry-run previews, idempotency keys, and active-pending content deduplication.

## Run Locally

```bash
cd "/Users/spellbook/Desktop/Langlobal/译员管理系统/backend"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

The local demo database is created automatically when empty. The encryption key file is generated at `backend/.key` unless `AES_KEY` is provided.

## Run with Docker

Docker mounts the persistent host directory `./data` at `/data`. Create `data/.env` locally; it is ignored by Git and the Docker build context:

```bash
mkdir -p data
JWT_SECRET="$(openssl rand -hex 32)"
AES_KEY="$(openssl rand -hex 32)"
printf 'JWT_SECRET=%s\nAES_KEY=%s\nTOKEN_TTL=28800\n' "$JWT_SECRET" "$AES_KEY" > data/.env
docker compose up --build
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). The container runs `alembic upgrade head` before Uvicorn; migration failure stops the container. SQLite defaults to `sqlite:////data/app.db`, so preserve the whole `data/` directory for migration or backup.

`JWT_SECRET` and `AES_KEY` are required (`AES_KEY` is a 64-character hexadecimal AES-256 key). `TOKEN_TTL` is optional and defaults to `28800` seconds. No secrets are baked into the image: never commit `data/.env`, databases, or key files. This is a single-instance demo; production authentication, backups, monitoring, HTTPS, PostgreSQL, and multi-instance coordination are out of scope.

## Verification

Backend acceptance tests start an isolated temporary server and SQLite database by default:

```bash
cd "/Users/spellbook/Desktop/Langlobal/译员管理系统"
backend/.venv/bin/python backend/tests/test_acceptance.py
```

To test an already running external server, pass `BASE`, for example:

```bash
BASE=http://127.0.0.1:8000 backend/.venv/bin/python backend/tests/test_acceptance.py
```

Other local checks:

```bash
backend/.venv/bin/python backend/tests/test_acceptance_isolation.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_pending_idempotency.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_migrations.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_docker_startup.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_schema_validation.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_quality_rating.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_capacity_thresholds.py
for f in frontend/tests/*.mjs; do node "$f" || exit 1; done
backend/.venv/bin/python -m compileall backend/app backend/tests translator-mgmt-agent
python3 translator-mgmt-agent/test_client_payloads.py
git diff --check
```

Current acceptance baseline: `142/142`; LQE-rating boundaries `13/13`; monthly-capacity thresholds `6/6`; twelve frontend static test scripts.

## Remaining Work

- Prepare production deployment: persistent process, HTTPS, fixed secrets, backup, and migration strategy.
- Finalize real login, finance-specific permissions, and reminders.
