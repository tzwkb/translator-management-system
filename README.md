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
- Translation, review, fixed-price, and custom project prices, plus rate-change, quality, contract, complaint, and capacity records; quality ratings use cumulative LQE scores with an auditable manual override.
- Monthly capacity is selected by month and calculated from current-project remaining words, distributed across the remaining Monday–Friday schedule; it uses translation output × 20, defaults to 2,000 units/day, supports reasoned month-specific status overrides, and has no manual occupancy-percentage ledger.
- Translator and PO grids use one Excel-style filtering workflow with value search, multi-select, blank values, typed text/number/date conditions, cross-column AND filtering, sorting, active-filter chips, and one-click clearing.
- A searchable “More fields” header covers non-visible translator, related-business, and PO source fields with up to 20 combined conditions, including exact and ranged price filters.
- PO settlement supports latest project-price matching, per-1k, hourly, fixed, and manual pricing, full manual correction, unpaid detail, and monthly/cumulative summaries.
- Projectlist supports preview-and-confirm batch import with `结算PO` filtering. Translation, review, and MTPE use `译员WWC字数` with per-1k pricing; LQA/LQE use that column as hours; fixed-price CNY rows use the source fee. CNY totals are verified before import, settled/paid rows are skipped as history, and exact translator matching plus source keys prevent duplicates.
- Formal standard-PO and Projectlist imports persist batch-level and row-level outcomes. Editors can export `PO_Log.xlsx` with separate import-batch and row-detail sheets; previews and structural HTTP 400 failures do not create import logs.
- Translator names use stable IDs with persistent aliases. Excel rows carrying an existing translator ID overwrite that record and preserve the previous name as an alias.
- Multiple encrypted payment accounts for WeChat, Alipay, personal bank, corporate CNY, and corporate USD; no default account is assigned, at least one information field is required, and QR codes are supported.
- Controlled qualification-attachment upload, authenticated download, deletion, metadata, and signature checks.
- Strict request validation for dates, months, enums, email, non-negative values, and percentage ranges.
- Translator Excel import/export with a downloadable blank template for profiles, project experience, aliases, and instructions. The template includes required gender; import selects the named profile sheet regardless of the active sheet and reports duplicates and validation errors.
- Translator intake links: email-bound invitations, a bilingual mobile form, revision requests, staff review and explicit duplicate merging. Approval writes profiles transactionally; rates require separate confirmation. The public ASGI entry exposes only intake routes. See the [intake guide](docs/按日期/2026-09-07/已实施/译员自填链接使用说明.md).
- Standard PO/settlement Excel import with duplicate-PO skipping, invalid-row reporting, and language-pair rate lookup.
- LQE import, audit log, role-based access control, payment masking/encryption, and agent pending-review workflow.
- Safe agent writes with dry-run previews, idempotency keys, and active-pending content deduplication.

## Run Locally

```bash
cd "/Users/spellbook/Desktop/Langlobal/译员管理系统/backend"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m alembic -c alembic.ini upgrade head
./run.sh
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

Run the migrations before starting the application. Empty databases stay empty by default; set `SEED_DEMO_DATA=1` only when you explicitly want demo records. The encryption key file is generated at `backend/.key` unless `AES_KEY` is provided.

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

Current acceptance baseline: `159/159`; translator-intake checks `33/33`; template checks `7/7`; LQE-rating boundaries `13/13`; monthly-capacity thresholds `6/6` plus cross-month allocation and data-integrity cases; thirteen frontend static test scripts.

## Remaining Work

- Prepare production deployment: persistent process, HTTPS, fixed secrets, backup, and migration strategy.
- Finalize real login, finance-specific permissions, and reminders.
