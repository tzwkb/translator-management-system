# 译员管理系统

<!-- bilingual-readme:start -->

## 双语说明 / Bilingual Documentation

> 本节提供整篇 README 的中英双语维护说明；下方保留原始详细说明、命令、路径和配置示例。
> This section provides bilingual maintenance notes for the full README; the original detailed notes, commands, paths, and configuration examples are preserved below.

### 中文

**概览**：译员全生命周期与结算管理系统，后端为 FastAPI + SQLite，前端为单文件 HTML，并配套自动化 agent skill。

**主要能力**：
- 管理译员信息、项目、费率和结算。
- 提供轻量后端和单文件前端。
- 配套自动化 skill 处理常见操作。

**使用方式**：按 README 的后端/前端启动说明配置数据库并运行服务。

**状态**：该仓库仍按当前 README 的说明维护或使用。

**注意事项**：本仓库面向业务管理流程，数据字段应与实际译员管理口径保持一致。

### English

**Overview**: Translator lifecycle and settlement management system with a FastAPI + SQLite backend, single-file HTML frontend, and companion automation agent skill.

**Key capabilities**:
- Manages translator records, projects, rates, and settlement.
- Provides a lightweight backend and single-file frontend.
- Includes an automation skill for common operations.

**Usage**: Configure the database and run the backend/frontend according to the README startup notes.

**Status**: This repository is maintained or used according to the current README notes.

**Notes**: The repository targets business management workflows; data fields should match the actual translator-management policy.

<!-- bilingual-readme:end -->

译员全生命周期 + 结算管理系统。后端 FastAPI + SQLite，前端单文件 HTML，配套一个自动化 skill。

## 目录

- `backend/` —— 后端，分层：`app/`（config · db · security · models · schemas · services · routers · main）、`tests/`、`run.sh`、`requirements.txt`
- `frontend/` —— 单文件前端 `index.html`
- `translator-mgmt-agent/` —— 自动化 skill：从微信/企微抓译员动态写进系统（`SKILL.md` + `client.py`）
- `archive/` —— demo 单文件原型，已被 backend+frontend 取代，留存参考

## 跑起来

    cd backend
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # 首次
    ./run.sh                                                              # 启动

浏览器开 http://127.0.0.1:8000。首次需先建 `.venv` 并装依赖（见上），之后直接 `./run.sh`。
首次启动库空时自动写入示例数据（见 `app/seed.py`）。加密用的 `.key` 不入库，首启自动生成（或用环境变量 `AES_KEY`）。
顶栏右上「视角」可切 资源端 / 财务 / 资源端Agent / boss。

## 测试

    cd backend
    ./run.sh &
    .venv/bin/python tests/test_acceptance.py     # 27 项验收（RBAC / 边界 / PRD 硬规则 / 安全 / agent 护栏）

## 上线还差

真密码登录、日报自动汇 PO、到期定时提醒、Docker 部署、agent 全量 service 层与 NL 大脑（由 skill 承担）。