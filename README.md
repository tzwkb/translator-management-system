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

- Translator master records with grouped detail UI.
- Per-language-pair rates with fixed language-code options and free source/target combination.
- Rate-change records, quality scores, contracts, payment info, complaints, and capacity records.
- PO settlement with actual-character count, per-1k-character rate, status flow, summary, and pending-review guardrails.
- Strict request validation for dates, months, enums, email, non-negative values, and percentage ranges.
- Excel translator import with duplicate-email handling and invalid-row reporting.
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
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_schema_validation.py
for f in frontend/tests/*.mjs; do node "$f" || exit 1; done
backend/.venv/bin/python -m compileall backend/app backend/tests translator-mgmt-agent
python3 translator-mgmt-agent/test_client_payloads.py
git diff --check
```

Current acceptance baseline: `71/71`.

## Remaining Work

- Prepare production deployment: persistent process, HTTPS, fixed secrets, backup, and migration strategy.
- Finalize real login, finance-specific permissions, and reminders.
