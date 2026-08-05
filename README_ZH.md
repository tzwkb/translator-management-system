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

- 译员主表与分组详情页，支持性别、个人/供应商类型。
- 一个译员可维护多条当前或过往项目经历，区分我司与外部合作。
- 语言对独立费率：固定语言代码选项，每一边可自由组合，支持 ZH→KO、EN→JA 等。
- 翻译、审校、一口价和自定义“其他”项目价格，以及报价变更、质量记分、合同、客诉和产能台账；质量等级按累计 LQE 均分生成，并允许记录原因的人工例外评级。
- 月度产能可选具体月份，当前项目剩余字数按剩余排期中的周一至周五分摊；月产能为翻译日产能 × 20，默认 2000 字/日；状态为 `<50%` 空闲、`50%–<80%` 健康、`80%–100%` 饱和、`>100%` 警告。人工修正按月记录状态与原因，不再存在手填占用百分比台账。
- 译员主表和 PO 表统一使用 Excel 式表头筛选：值搜索、多选、空白值、文本/数值/日期条件、升降序、AND 叠加、筛选标签及一键清除。
- “更多字段”覆盖未展示的译员主表、业务子表和 PO 来源字段，最多组合 20 条条件；价格可按精确值、上下限或区间筛选。
- PO 支持最新项目价格自动匹配、按千字、按小时、一口价和手工金额、完整人工修正、未结算明细，以及当月与跨月累计未付。
- Projectlist 已开放只读映射预览及“结算PO”已勾选/未勾选筛选；已勾选行标记为历史记录。PO 数量真实性规则确认前，财务写入保持硬关闭。
- 译员通过稳定 ID 关联持久名称映射；Excel 携带已有译员 ID 时覆盖原记录，并自动把旧姓名保存为名称映射。
- 微信、支付宝、个人银行卡、对公人民币、对公美元多支付账户；不设默认账户，各字段可空但至少填写一项，敏感字段加密脱敏并支持收款码。
- 资质附件受控上传、登录下载、删除、元数据和文件签名校验。
- 字段格式验证：真实日期、真实月份、枚举、邮箱、非负数、百分比范围等。
- Excel 译员导入导出：按邮箱去重，支持性别、主体类型及独立“项目经历”工作表，非法行返回明细。
- 标准 PO / 结算 Excel 导入：支持重复 PO 跳过、错误行报告、语言对自动取价。
- LQE 导入、加密脱敏、RBAC、agent 钱相关待审护栏。
- Agent 写入安全：支持 dry-run、幂等键和活动待审内容防重。

## 本地启动

```bash
cd "/Users/spellbook/Desktop/Langlobal/译员管理系统/backend"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m alembic -c alembic.ini upgrade head
./run.sh
```

浏览器打开：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

应先执行 `alembic upgrade head`，迁移成功后再启动服务。首次启动库为空时会写入示例数据。加密 key 默认生成到 `backend/.key`，生产环境应改用固定 `AES_KEY` 环境变量。

## Docker 本地启动

Docker 将持久化宿主机目录 `./data` 挂载为容器内的 `/data`。先在本地创建 `data/.env`；该文件已被 Git 和 Docker 构建上下文忽略：

```bash
mkdir -p data
JWT_SECRET="$(openssl rand -hex 32)"
AES_KEY="$(openssl rand -hex 32)"
printf 'JWT_SECRET=%s\nAES_KEY=%s\nTOKEN_TTL=28800\n' "$JWT_SECRET" "$AES_KEY" > data/.env
docker compose up --build
```

浏览器打开：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)。容器会先执行 `alembic upgrade head`，迁移失败即退出，不会启动 Uvicorn。SQLite 默认地址为 `sqlite:////data/app.db`；迁移或备份时请保留整个 `data/` 目录。

`JWT_SECRET`、`AES_KEY` 为必填项（`AES_KEY` 是 64 位十六进制 AES-256 密钥）；`TOKEN_TTL` 可选，默认 `28800` 秒。镜像不内置密钥；不得提交 `data/.env`、数据库或 key 文件。该方案仅用于单实例 Demo，不提供正式认证、备份、监控、HTTPS、PostgreSQL 或多实例协调。

## 数据库版本管理

数据库结构由 Alembic 迁移统一管理；应用启动不再自动建表或修改表结构。修改 SQLAlchemy 模型后：

```bash
cd backend
.venv/bin/python -m alembic -c alembic.ini revision --autogenerate -m "描述变更"
.venv/bin/python -m alembic -c alembic.ini upgrade head
```

自动生成的迁移必须人工审查，并与模型、业务代码和测试一起发布。

对已有业务数据、但尚无 Alembic 版本号的旧库：先备份并完成恢复演练，在数据库副本上执行：

```bash
cd backend
DB_URL=sqlite:////absolute/path/to/copy.db \
  .venv/bin/python -m app.db_baseline --backup-confirmed
```

该命令会执行一次性历史整理、比对当前模型，只有完全一致时才记录初始基线。不要对真实生产库直接试跑。

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

当前验收基线：`146/146`；LQE 评级边界 `13/13`；月度产能阈值 `6/6` 并通过跨月分摊、字数守恒和数据完整性用例；前端静态测试 13 个脚本。

## 后续重点

- 准备线上部署：常驻进程、HTTPS、固定密钥和备份恢复演练。
- 完善真登录、财务权限和到期提醒。
