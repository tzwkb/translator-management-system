# 译员管理系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-framework-009688.svg)](https://fastapi.tiangolo.com/)

[English](README.md) | 中文

面向本地化资源管理的译员全生命周期、能力、费率、结算和风险管理系统。后端 FastAPI + SQLite，前端单文件 HTML，配套 Codex/Hermes 自动化 skill。

## 目录

- `backend/`：后端代码、数据模型、schema 校验、业务服务、API 路由、测试和启动脚本。
- `frontend/`：单文件前端 `index.html`。
- `translator-mgmt-agent/`：自动化 skill，从微信/企微线索写入系统；钱相关动作进入待审。
- `archive/`：早期单文件原型，仅留作参考。

## 当前能力

- 译员主表与分组详情页。
- 语言对独立费率：固定语言代码选项，每一边可自由组合，支持 ZH→KO、EN→JA 等。
- 报价变更、质量记分、合同、支付信息、客诉、产能、PO、待审、审计日志。
- PO 结算按实际字数入库，金额口径为 `字数 / 1000 * 单价`。
- 字段格式验证：真实日期、真实月份、枚举、邮箱、非负数、百分比范围等。
- Excel 译员导入：按邮箱去重，非法行跳过并返回 `invalid_rows`。
- 标准 PO / 结算 Excel 导入：支持重复 PO 跳过、错误行报告、语言对自动取价。
- LQE 导入、加密脱敏、RBAC、agent 钱相关待审护栏。
- Agent 写入安全：支持 dry-run、幂等键和活动待审内容防重。

## 本地启动

```bash
cd "/Users/spellbook/Desktop/Langlobal/译员管理系统/backend"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

浏览器打开：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

首次启动库为空时会自动写入示例数据。加密 key 默认生成到 `backend/.key`，生产环境应改用固定 `AES_KEY` 环境变量。

## 验证

后端验收默认会启动临时服务和临时 SQLite，不会写入开发库：

```bash
cd "/Users/spellbook/Desktop/Langlobal/译员管理系统"
backend/.venv/bin/python backend/tests/test_acceptance.py
```

如果要打已经运行的外部服务，可以显式传 `BASE`：

```bash
BASE=http://127.0.0.1:8000 backend/.venv/bin/python backend/tests/test_acceptance.py
```

其他本地检查：

```bash
backend/.venv/bin/python backend/tests/test_acceptance_isolation.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_pending_idempotency.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_schema_validation.py
for f in frontend/tests/*.mjs; do node "$f" || exit 1; done
backend/.venv/bin/python -m compileall backend/app backend/tests translator-mgmt-agent
python3 translator-mgmt-agent/test_client_payloads.py
git diff --check
```

当前验收基线：`71/71`。

## 后续重点

- 准备线上部署：常驻进程、HTTPS、固定密钥、备份、迁移策略。
- 完善真登录、财务权限和到期提醒。
