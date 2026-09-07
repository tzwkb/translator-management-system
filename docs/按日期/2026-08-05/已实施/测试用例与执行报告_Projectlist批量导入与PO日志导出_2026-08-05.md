# 测试用例与执行报告：Projectlist 批量导入与 PO 日志导出

> 状态：自动化已通过，部分生产级场景待补\
> 文档日期：2026-08-05\
> 适用版本：Git 提交 `f6f20cd531c902cc236a323136418a6824f15aa1` 及以后\
> 关联开发文档：[Projectlist 批量导入与 PO Log 导出](开发文档_Projectlist批量导入与PO日志导出_2026-08-05.md)

## 1. 测试结论

本次功能的仓库自动化验收通过：

- 后端完整验收：`159/159`；
- PO 导入/导出前端专项：通过；
- 后端验收隔离专项：通过；
- Alembic 升级、降级、旧库和模型一致性：通过；
- 前端全部 13 个 `.mjs` 脚本：通过；
- LQE 评级边界：`13/13`；
- 月度产能阈值：`6/6`，跨月分摊和数据完整性用例通过。

自动化已经证明标准 PO 和 Projectlist 的核心导入、金额规则、防重、来源冲突、日志落库和双工作表导出可用。尚未证明真实业务文件的正式写入、跨实例持久性、超大文件性能和故障注入下的原子回滚；这些不能视为已验收。

## 2. 测试范围

### 2.1 已覆盖

- 标准 PO 导入回归；
- Projectlist 工作表和必要表头识别；
- 翻译、审校、MTPE、LQA、LQE、一口价的数量与金额；
- CNY 正常金额验算和各计价模式的正确金额；
- 已结算/已打款历史跳过；
- 状态筛选；
- 译员精确姓名和别名匹配；
- 结算月和跨年边界；
- 行级幂等、来源冲突和来源键稳定性；
- preview 不写 PO 和日志；
- 正式导入写批次/行级日志；
- `PO_Log.xlsx` 基本结构和追溯字段；
- 前端预览、确认、取消、状态快照和并发锁；
- 数据库迁移和验收数据库隔离。

### 2.2 未覆盖或仅人工核对

- 真实业务 Projectlist 的正式导入；
- 浏览器多内核和完整人工 UI 交互；
- 服务重启、实例替换、备份与恢复后的日志保留；
- 超大文件、并发上传和性能上限；
- 导入中途数据库异常的故障注入；
- PO Log 长期数据量下的内存占用；
- 完全空日志数据库的导出结果；
- CNY 金额容差边界和金额偏差拒绝的专项自动化；
- 数量/费率超过 2 位小数后的重复导入；
- 显式日期或 `YYYY-M` 超出 DDL 两个月窗口的行为；
- 缺目标语言时按原始译员姓名字符串推断，以及正式名/别名不合并的边界；
- 结构性 HTTP 400 的尝试日志；
- 当前 Render 免费实例的跨部署持久性。

## 3. 测试环境与隔离

| 项目 | 配置 |
|---|---|
| 系统 | macOS，本地仓库 |
| 后端 | FastAPI + SQLAlchemy + SQLite |
| Python | 仓库 `backend/.venv` |
| 前端测试 | Node.js VM/静态行为测试 |
| 默认验收数据库 | 临时 SQLite |
| 默认验收服务 | 随机本地端口的临时服务 |
| 迁移目标 | Alembic `20260805_0008` |

`backend/tests/test_acceptance.py` 在未设置 `BASE` 时自动启动隔离服务并使用临时数据库，不写入 `backend/app.db`。只有显式设置 `BASE` 时才会测试外部服务。

真实业务 Excel 只允许 preview；未经明确授权不得发送 `preview=false`。

## 4. 分支规则与测试假设

编写和判断用例时采用以下规则：

1. 先要求 `结算PO` 和 `已打款` 两列都可识别；两者均可识别后，任一为真才按历史跳过，任一未知则先按源数据错误处理；
2. 状态筛选先确定哪些行被选中，未选中行不创建 PO；
3. 翻译/审校/MTPE 的 WWC 是字数，LQA/LQE 的同一列是小时数；
4. 一口价只读 CNY 稿费，不使用 WWC 和费率；
5. Projectlist 只允许精确译员匹配，不能因为相似姓名而导入；
6. preview 必须是零写入；正式导入才允许新增 PO 和日志；
7. 相同来源键、相同内容是重复；相同来源键、不同内容是冲突；
8. 持久批次和行日志把 `source_conflict` 独立计数，不计入 `invalid_count`；API 响应的 `invalid_rows` 仍包含 `source_conflict=true` 的冲突详情，供页面展示；
9. 批次计数必须由逐行最终 outcome 汇总得出；
10. 数据库落表只证明应用级持久化，不自动证明 Render 临时磁盘跨实例保留。

## 5. 自动化用例矩阵

### 5.1 标准 PO 与 Projectlist 核心

| ID | 场景与输入 | 操作 | 预期结果 | 自动化证据 |
|---|---|---|---|---|
| PO-001 | 标准 PO 含有效行、重复 PO 号、不存在译员 | 正式导入 | 1 条导入、1 条重复、1 条错误；`2000 × 180 / 1000 = 360` | `backend/tests/test_acceptance.py:333-351` |
| PO-002 | Projectlist 删除 `结算PO` 或 `已打款` 表头 | 导入 | 两个请求都返回 HTTP `400`；缺列消息和批次不变由代码审查确认，尚无专项断言 | `backend/tests/test_acceptance.py:1548-1578` |
| PO-003 | 含翻译、审校、MTPE、LQA、LQE、一口价、历史行、未知类型、缺 WWC | preview `all` | 6 条 ready；1 条历史跳过；2 条错误；各计价模式和金额正确 | `backend/tests/test_acceptance.py:1487-1619` |
| PO-004 | 同一 Projectlist 分别选择 `checked`、`unchecked` | preview | checked 选中 1 条历史行；unchecked 选中 8 条，其中 6 ready、2 错误 | `backend/tests/test_acceptance.py:1621-1644` |
| PO-005 | PO-003 样本 | 正式导入 | 只新增 6 条；计价模式、数量、费率、金额和 source_key 正确 | `backend/tests/test_acceptance.py:1646-1708` |
| PO-006 | 再次上传 PO-005 的同一文件 | 正式导入 | 0 新增、6 条 `skip_duplicate`，PO 总数不变 | `backend/tests/test_acceptance.py:1710-1727` |
| PO-007 | 同一译员的正式名与别名、相同业务身份两行 | 连续正式导入两次 | 首次生成两个 occurrence/source_key；第二次逐行重复跳过 | `backend/tests/test_acceptance.py:1730-1805` |
| PO-008 | 已导入来源行同时修改数量、费率和币种 | 再次正式导入 | `source_conflict=1`，不新增、不覆盖旧 PO，错误列出差异字段 | `backend/tests/test_acceptance.py:1807-1864` |
| PO-009 | 跨年 1 月、未知状态、已结算但译员缺失、模糊姓名、月份跨度过大 | preview 后正式导入 | 只有跨年行 ready；历史行先跳过；4 条明确错误；正式只写跨年 PO | `backend/tests/test_acceptance.py:1866-1982` |

### 5.2 PO Log

| ID | 场景与输入 | 操作 | 预期结果 | 自动化证据 |
|---|---|---|---|---|
| LOG-001 | 数据库已有前序正式导入日志 | `GET /api/export/po-log` | 返回有效 XLSX，包含“导入批次”“行级明细”和核心列 | `backend/tests/test_acceptance.py:1984-2059` |
| LOG-002 | 标准 PO 和 Projectlist | 分别执行 preview，前后导出日志 | 批次数和明细数完全不变 | `backend/tests/test_acceptance.py:2061-2136` |
| LOG-003 | 标准 PO 3 行 + Projectlist 5 行 | 分别正式导入 | 各新增 1 批次，共 8 条明细；每源行只有一个 outcome | `backend/tests/test_acceptance.py:2138-2252` |
| LOG-004 | Projectlist 五种选中结果 | 正式导入并导出 | 各有 `imported`、`skip_duplicate`、`skip_settled`、`source_conflict`、`invalid`；批次计数一致 | `backend/tests/test_acceptance.py:2138-2252` |
| LOG-005 | 日志包含有效、冲突和错误行 | 导出 | 明细能追溯项目、源行、source_key、译员不存在、字段变化和非法工作类型 | `backend/tests/test_acceptance.py:2253-2284` |

### 5.3 前端

| ID | 场景与输入 | 操作 | 预期结果 | 自动化证据 |
|---|---|---|---|---|
| UI-001 | Projectlist 文件和筛选状态 | 点击导入 | 先 preview；确认后才发送正式请求；两次请求使用同一状态快照 | `frontend/tests/po_import_ui.mjs:37-113` |
| UI-002 | 用户在确认框取消 | 点击取消 | 不发送正式请求，不刷新 PO | `frontend/tests/po_import_ui.mjs:116-130` |
| UI-003 | 第一次导入未完成时再次触发 | 连续触发 | 第二次被页面级锁拦截 | `frontend/tests/po_import_ui.mjs:132-144` |
| UI-004 | preview 返回 `ready=0` | 点击导入 | 不显示确认、不正式写入、不刷新 PO | `frontend/tests/po_import_ui.mjs:145-158` |
| UI-005 | editor/viewer 页面 | 点击或检查按钮 | editor 导出 `/api/export/po-log` 为 `PO_Log.xlsx`；viewer 由 `.edit-only` 隐藏 | `frontend/tests/po_import_ui.mjs:7-35` |

### 5.4 迁移与隔离

| ID | 场景与输入 | 操作 | 预期结果 | 自动化证据 |
|---|---|---|---|---|
| DB-001 | 全新空库 | Alembic upgrade head | 到达 `20260805_0008`，表、列、索引、FK、唯一约束和 action check 存在 | `backend/tests/test_migrations.py:27-159` |
| DB-002 | head 数据库 | downgrade 后再 upgrade | 升降级成功，结构恢复 | `backend/tests/test_migrations.py:324-352` |
| DB-003 | 旧库和既有业务数据 | 执行迁移测试 | 旧数据保留，模型和迁移一致，`alembic check` 无新操作 | `backend/tests/test_migrations.py:354-551` |
| ISO-001 | 未设置 `BASE` | 运行完整验收 | 使用临时 SQLite 和随机端口，不写开发库 | `backend/tests/test_acceptance_isolation.py`、`backend/tests/test_acceptance.py:1-145` |

## 6. 金额专项用例

| ID | 工作类型 | WWC | 源费率 | 源 CNY 稿费 | 预期系统值 |
|---|---|---:|---:|---:|---|
| AMT-001 | 翻译 | 1,200 字 | 0.20/字 | 240.00 | `per_1000`；费率 200；金额 240 |
| AMT-002 | 审校 | 2,000 字 | 0.10/字 | 200.00 | `per_1000`；费率 100；金额 200 |
| AMT-003 | MTPE | 1,500 字 | 0.08/字 | 120.00 | `per_1000`；费率 80；金额 120 |
| AMT-004 | LQA | 3 小时 | 15 USD/小时 | 空 | `per_hour`；数量 3；金额 45 USD |
| AMT-005 | LQE | 2 小时 | 20 USD/小时 | 空 | `per_hour`；数量 2；金额 40 USD |
| AMT-006 | 一口价 | 空 | 空 | 680.00 | `fixed`；数量/费率为空；金额 680 CNY |
| AMT-007 | 翻译 | 20,000 | 0.18 | 3,599.99 | 差额 0.01，在容差内，可导入 |
| AMT-008 | 翻译 | 20,000 | 0.18 | 3,500.00 | 差额 100，`invalid`，不导入 |
| AMT-009 | 一口价 USD | 任意 | 任意 | 任意 | 非 CNY 一口价拒绝 |
| AMT-010 | 未知工作类型 | 100 | 1 | 100 | 不猜数量单位，`invalid` |

AMT-001 至 AMT-006 是 PO-003/PO-005 的实际 fixture 和断言，AMT-010 的未知类型也已覆盖；AMT-007 至 AMT-009 是应补的边界自动化，当前不能列为已执行通过。

## 7. 日志一致性判定

每个正式批次必须满足：

```text
selected_rows = imported
              + skipped_duplicate
              + skipped_settled
              + source_conflicts
              + invalid_count
```

未选中或非 PO 行使用 `ignored`，不计入 selected。每条行日志必须满足：

- `source_row > 0`；
- `(batch_id, sheet, source_row)` 唯一；
- action 属于六种白名单；
- action 为 `ignored` 时 `selected=false`；
- action 为其他值时 `selected=true`；
- 持久批次/行日志中 `source_conflict` 只记冲突数，不计入 `invalid_count`；API 响应的 `invalid_rows` 可同时包含该冲突详情；
- `imported` 行应有 PO ID；
- Projectlist 导入/重复/冲突行应保留 source_key。

注意：导入 API 响应的 `ignored_rows` 只统计三项核心字段全空的非 PO 行；导出批次的 `ignored_rows` 还包含状态筛选排除的所有有效/错误行。测试时应按各自口径核对，不能要求两个字段恒等。

## 8. 人工与补充测试用例

以下用例是发布前测试设计，其中部分只有一次性验证或线上 smoke 证据，尚未全部固化为仓库自动化。

### 8.1 权限接口

前置：准备 editor、viewer 和无 token 三种请求。

步骤：

1. 分别调用 `POST /api/import/po?preview=true`；
2. 分别调用 `GET /api/export/po-log`；
3. 记录状态码和响应体。

预期：editor 可访问；viewer 和无有效 token 返回 `403`。当前只有 PO Log 导出接口做过本地/线上 editor `200`、viewer `403` smoke；导入接口及无 token 组合尚未执行完整矩阵，仓库也没有独立的后端权限断言。

### 8.2 Excel 安全

输入：项目名、译员名或错误消息分别以 `=SUM(1,1)`、`+1`、`-1`、`@cmd` 开头，并包含非法控制字符。

步骤：正式导入测试数据，导出 PO Log，用 openpyxl 检查单元格类型和值。

预期：所有危险文本是字符串且以单引号保护；不存在公式类型单元格；非法控制字符被清理；文件仍可打开。

该场景做过一次性程序化检查并通过，但尚未成为持久测试文件。

### 8.3 响应头和工作簿样式

步骤：下载 PO Log，检查响应头、冻结窗格、自动筛选、日期/数字类型和列宽。

预期：

- `Content-Disposition` 文件名为 `PO_Log.xlsx`；
- `Cache-Control: no-store`；
- `X-Content-Type-Options: nosniff`；
- 两张表均冻结首行并启用自动筛选。

当前双表和核心数据已有自动化；响应头和样式尚无持久自动化断言。

### 8.4 原子回滚

前置：在测试数据库中对行日志写入或最终 commit 注入异常。

步骤：执行包含一个有效 PO 的正式导入。

预期：请求失败后，PO、PO AuditLog、导入批次和行日志都不新增。

代码使用同一 Session，设计上应整体回滚；该故障注入尚未自动化验证。

### 8.5 持久盘、备份和恢复

步骤：

1. 正式导入一个测试批次并导出；
2. 重启服务后再次导出；
3. 备份数据库；
4. 在新实例恢复数据库并再次导出。

预期：三次日志数量和关键字段一致。

该用例只适用于已配置持久盘的环境。当前 Render 免费实例使用临时 SQLite，实例替换后数据可能丢失，不能按此预期验收。

### 8.6 全错误文件的日志边界

输入：结构正确、但所有业务行均 invalid 的文件。

步骤：先走前端导入，再直接调用正式 API。

预期：

- 前端 preview 得到 `ready=0` 后停止，因此不创建批次；
- 直接发送 `preview=false` 时创建一个 0 imported 的批次，并持久化 invalid 行；
- 损坏 Excel 或缺必要表头仍在批次创建前返回 `400`，不会留下日志。

### 8.7 小数精度重复导入

输入：数量或转换后的系统费率超过 2 位小数、其他身份字段不变的 Projectlist 行。

步骤：连续正式导入同一文件两次。

理想预期：第一次 `imported`，第二次 `skip_duplicate`。当前 `po_settlements.word_count/rate` 只保留 2 位小数，而比较容差为 `0.000001`，第二次可能实际得到 `source_conflict`。该场景是已知缺口，修复前不得把任意小数精度下的重复导入描述为完全幂等。

## 9. 真实 Projectlist 验证

验证文件：

```text
docs/按日期/2026-06-30/参考资料/日报_琅科2026.xlsx
```

当前隔离预览结果：

- 识别工作表：`【项目组】Projectlist (V1.0)`；
- 表头行：第 3 行；
- selected_rows：1,049；
- ready：0；
- invalid_rows：912；
- preview 前后批次和行日志均为 0。

`ready=0` 的主要原因是当前隔离开发库没有与源文件对应的精确译员，不代表 Projectlist 工作表或表头无法识别。其余选中行中包含历史跳过等结果，因此 selected_rows 不等于 invalid_rows。

历史隔离记录中，临时补充 117 个来源姓名后曾得到 950 条 ready、99 条错误；这是早期补数验证，不是当前首次运行结果，也没有对真实业务库正式导入。两组数据不得混写为一次测试。

出于业务数据和个人信息保护，真实文件未复制为公开 fixture；当前自动化使用构造的最小工作簿覆盖规则分支。

## 10. 执行记录

### 10.1 正确命令

从仓库根目录：

```bash
backend/.venv/bin/python backend/tests/test_acceptance.py
backend/.venv/bin/python backend/tests/test_acceptance_isolation.py
for f in frontend/tests/*.mjs; do node "$f" || exit 1; done
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_pending_idempotency.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_docker_startup.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_schema_validation.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_quality_rating.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_capacity_thresholds.py
backend/.venv/bin/python -m compileall backend/app backend/tests translator-mgmt-agent
python3 translator-mgmt-agent/test_client_payloads.py
git diff --check
```

迁移测试使用：

```bash
cd backend
PYTHONPATH=. .venv/bin/python tests/test_migrations.py
```

### 10.2 首次运行与重试

2026-08-05 编写本文档时再次复跑：后端完整验收 `159/159`、迁移专项、前端 13 个脚本、验收隔离、质量评级 `13/13`、产能阈值 `6/6` 各命令均一次通过，退出码均为 0。下表另行保留功能开发阶段的首轮执行和命令纠正记录。

| 检查 | 开发阶段首次运行 | 重试/纠正 | 最终结果 |
|---|---|---|---|
| 后端完整验收 | `159/159` | 无 | 通过 |
| PO 前端专项 | pass | 无 | 通过 |
| 验收隔离专项 | pass | 无 | 通过 |
| 迁移专项 | 从仓库根直接运行、未配置模块路径，测试未启动，报 `ModuleNotFoundError` | 切换到 `backend` 并设置 `PYTHONPATH=.` | 通过，输出 `alembic migrations and legacy baseline pass` |
| 前端全部脚本 | 13 个脚本通过 | 无 | 通过 |
| 工作簿公式注入/渲染 | 一次性程序化检查通过 | 无 | 通过，但未固化为自动化文件 |

迁移专项的首次失败是测试命令环境错误，不是产品用例失败。没有产品测试通过“修改预期”来达成，也没有需要单列的产品失败重试数据。

## 11. 线上 smoke 记录

Render 部署版本：`f6f20cd531c902cc236a323136418a6824f15aa1`。

已核对：

- Alembic 从 `20260731_0007` 升级到 `20260805_0008`；
- 页面存在标准 PO 导入、Projectlist 导入和 PO Log 导出入口；
- editor 导出返回 `200` 和有效双工作表；
- viewer 导出返回 `403`。

线上日志为空是因为该实例使用全新 SQLite，迁移后没有执行正式 PO 导入。该结果只证明部署和权限 smoke，不证明跨部署日志持久性。

## 12. 发布判定

当前版本可用于受控的 Projectlist 预览、确认导入和日志导出。发布时必须满足：

- 数据库已迁移到 `20260805_0008`；
- editor/viewer 权限配置正确；
- 对真实文件先 preview，人工核对译员和金额错误；
- 生产环境配置持久数据库、备份和恢复；
- 不把 Render 临时 SQLite 当作永久日志存储；
- 不宣称真实 Projectlist 已正式导入，除非有单独审批和导入批次证据。

建议上线后优先补齐金额容差、小数精度幂等、权限接口、响应头/公式注入、ignored 行、原子回滚、并发竞态、重启恢复和性能测试。
