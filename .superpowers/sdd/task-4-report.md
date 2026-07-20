# Task 4 Codex Sites Demo 适配报告

执行日期：2026-07-20（Asia/Shanghai）
工作目录：`/Users/spellbook/Desktop/Langlobal/译员管理系统/.worktrees/docker-cloud-demo`
Sites 应用：`sites-demo/`

## 初始化与路径

- 完整读取 `sites-building` 技能、D1 存储与认证参考、Task 4 brief。
- 使用插件根目录 `scripts/init-site.sh` 在 `sites-demo/` 只初始化一次；安装完成。
- 初始化器创建的嵌套 `.git/` 已移出项目，`sites-demo/` 由父仓库按普通目录跟踪。
- 按后台委派约束未打开浏览器预览，未调用 Sites 创建或部署接口。

## RED → GREEN

### 核心领域、D1、健康检查与 Excel

RED：

```bash
npm run test:unit
```

输出：`0 pass / 4 fail`，分别因 `lib/roles`、`lib/excel`、`app/api/health/route`、`db/mappers` 尚不存在而失败，证明测试覆盖的是新增行为。

GREEN：

```bash
npm run test:unit
```

首轮实现后 `10/10` 通过。其中金额测试最初把 `12,345 × 0.1285` 误写为 `158,648` 分；核算后更正测试期望为四舍五入的 `158,633` 分，未改变金额规则。

### D1 幂等初始化与原子审批

RED：

```bash
npx tsx --test tests/repository.test.ts
```

输出：`0 pass / 1 fail`，原因为 `db/repository` 尚不存在。

GREEN：

```bash
npx tsx --test tests/repository.test.ts
```

输出：`3/3` 通过；覆盖幂等表/种子初始化、单语句 `prepare()`、费率提案批准的两语句 `batch()` 和驳回时只更新审核记录。

### 中文工作台与社交元数据

RED：

```bash
npx tsx --test tests/ui-contract.test.ts
```

输出：`0 pass / 1 fail`，`app/workbench.tsx` 尚不存在。工作台完成后用同一命令得到 `1/1` 通过。

社交图接入前在该测试增加 `${origin}/og.png` 断言，看到 `0/1` 预期失败；在 Open Graph/X 元数据使用请求 host 构造绝对地址后转为 GREEN。

### 待审 payload 校验

RED：

```bash
npx tsx --test tests/domain.test.ts
```

输出：因 `validateApprovalPayload` 未导出而失败。

GREEN：

```bash
npx tsx --test tests/domain.test.ts
```

输出：`6/6` 通过；不完整费率或 PO payload 在进入队列前返回校验错误。

## 最终验证

```bash
npm test
npx tsc --noEmit
npm run lint
npm run db:generate
git diff --check
```

结果：

- `npm test`：15 项 TypeScript 单测全部通过；内含的 `npm run build` 成功；2 项构建产物测试全部通过。
- TypeScript 检查和 ESLint 均退出码 `0`。
- Drizzle 检查识别 4 张表，输出 `No schema changes, nothing to migrate`；已保留 `drizzle/0000_slim_kitty_pryde.sql` 及 snapshot/journal。
- 产物结构检查通过：`dist/server/index.js`、`dist/.openai/hosting.json`、`dist/.openai/drizzle/0000_slim_kitty_pryde.sql` 和 `dist/client/og.png` 均存在；构建产物未提交。
- 暂存后 `git diff --cached --check` 通过，未暂存凭据、`node_modules`、`dist`、`.wrangler`、`.vinext` 或 `tsconfig.tsbuildinfo`。

本地 Worker HTTP 验证（未打开浏览器）：

```text
GET /api/health                         200  {"status":"ok","service":"lingua-control-demo"}
GET /api/workspace                      200  3 译员 / 2 费率 / 2 PO / 1 待审
POST /api/translators (viewer)          403
POST /api/approvals (agent)             201
PATCH /api/approvals/:id (boss approve) 200
GET /api/workspace                      200  approval=approved, rateMicros=139000
GET /api/export                         200  Microsoft Excel 2007+; unzip -t 无错误
GET /                                   200  中文标题、受控 Demo 标识与 og:image 存在
```

开发服务器已在验证后停止。

## 迁移与数据

- D1 逻辑绑定：`DB`；R2：`null`。
- Drizzle 模型：`translators`、`rates`、`purchase_orders`、`approvals`。
- 运行时建表、索引和种子均使用一次一条的 parameterized prepared statement；多语句通过 `batch()` 执行。
- 种子数据使用 `INSERT OR IGNORE`，名称和提交人均标记“示例”，邮箱使用 `.test` 域。

## 改动摘要

- 新增 D1 数据层、Drizzle schema/迁移、幂等初始化、安全示例数据与指标汇总。
- 新增译员列表/搜索/新增/编辑、费率查看/更改、PO 列表/新增/状态变更、agent 提案和 boss 原子审批 API。
- 新增服务端 Demo 角色权限；boss/editor/viewer/agent 与界面可用性一致，界面与 README 明示该机制不是生产安全方案。
- 使用 OpenXML + ZIP 生成包含当前译员与 PO 的真实 `.xlsx`，不依赖有已知高危漏洞的 `xlsx` 包。
- 替换 starter skeleton 为专业、紧凑、响应式的中文工作台；补加加载/空/成功/错误状态、可见标签、键盘焦点和 reduced-motion 处理。
- 移除 starter skeleton、无用图标、预览元数据、`react-loading-skeleton` 和未使用的认证/示例代码。
- 仅发起一次 imagegen；生成 `1732×908` PNG，人工核对 `Lingua Control`、`译员运营台`、`译员 · 费率 · PO · 审核`、`受控 Demo` 文字正确后保存为 `public/og.png`，并接入基于请求 host 的 Open Graph/X 元数据。

## 提交 SHA

实现提交：`89dc0c09989ef7fc1f783ec6ca7164b8d78108f3`（`feat: add Codex Sites translator demo`）。

## 自审与关注点

- brief 中的 D1、译员、费率、PO、审核、Excel、健康检查、种子、角色、中文工作台、响应式/可访问性、产物和元数据要求均已对照。
- 未引入自建登录、真实个人/付款数据、上传、监控或 FastAPI 改动。
- 按明确约束未做浏览器截图/DOM/点击/缩放视觉 QA；响应式与可访问性通过实现、静态检查和 HTTP 输出验证，这是剩余的主要非阻塞关注点。
- vinext 构建输出 Node `module.register()` 废弃警告和对 `/` 的“Unknown”静态分类提示，但构建退出码为 `0`，API 路由和本地 Worker HTTP 验证均成功。
- `npm install` 报告 starter 依赖树存在 14 项 audit 发现（1 low / 7 moderate / 6 high）；本任务没有使用破坏性 `npm audit fix --force`，新增的 `fflate` 未增加该计数。

## 审查修复（2026-07-20）

本节覆盖上文中已变更的测试数量、审批实现和迁移文件名。

### RED 证据

- 新增共享规范化、safe integer/业务上限和领域错误测试后，因 `lib/errors.ts` 与 `lib/validation.ts` 不存在而失败；原金额实现也未拒绝 unsafe integer。
- 新增按币种汇总、PO 审批完整摘要和表单失败不关闭测试后，因相应实现缺失而失败。
- 新增真实 SQLite 迁移约束测试后 `0/2` 通过：非法状态可写入，状态索引不存在。
- 将并发批准/驳回回归测试加入 repository 测试，旧实现无唯一审核令牌和 CAS 结果检查，不满足断言。

### GREEN 实现

- 审批改为同一 D1 `batch()` 内的唯一 `review_token` CAS；业务写入以该令牌和 pending 状态为条件，检查 claim 恰好更新 1 行，败者返回 409。批准前重新验证已存 payload。
- 直写和提案共用译员/费率/PO 规范化 schema；新 PO 及 PO 提案不允许 `paid`，非法枚举返回 400。更新不存在资源返回 404，已处理审批和唯一键冲突返回 409，损坏提案返回 422，未知异常仅对客户端返回通用 500。
- 整数输入使用 `Number.isSafeInteger`、明确业务上限和 `BigInt` 金额计算；待付金额按币种分开汇总展示。
- PO 审批卡片展示 PO 号、译员、月份、语言对、字数、单价/币种、服务端金额和状态；译员表单仅保存成功后关闭。
- Drizzle schema 增加显式 CHECK/index/唯一审核令牌，基线迁移重建为 `drizzle/0000_tiny_mariko_yashida.sql`，snapshot/journal 同步更新；真实 SQLite 测试确认非法枚举/数值被拒绝且索引存在。

### 修复后验证

```bash
npm test
npx tsc --noEmit
npm run lint
npm run db:generate
git diff --check
```

- `npm test`：`25/25` TypeScript 单测通过，包含并发审批和 `node:sqlite` 迁移约束测试；build 成功，`2/2` 构建产物测试通过。
- TypeScript、ESLint、Drizzle generate 和 `git diff --check` 均通过；Drizzle generate 返回 `No schema changes, nothing to migrate`。
- 新鲜本地 D1 Worker 冒烟：非法状态 `400`、更新不存在资源 `404`、重复邮箱 `409`、`paid` PO 提案 `400`、损坏 JSON `400`。对同一审批并发 approve/reject 得到 `200/409`，最终仅 1 次业务写入。
- 添加 USD PO 后 workspace 返回 CNY/USD 两个独立待付汇总；Excel 仍被识别为 Microsoft Excel 2007+ 且 `unzip -t` 无错误；首页、健康检查和受控 Demo 元数据均返回 200。验证后已停止开发服务器。

### 保留关注点

- `npm audit --omit=dev` 仍报告 2 项 moderate，均来自 Next 内嵌的 PostCSS `<8.5.10`。唯一自动修复建议是 `npm audit fix --force`，会降级至 Next 9.3.3 并破坏当前 vinext/Worker 栈，因此遵循审查要求未执行。
- 本轮仍按明确约束未打开浏览器做视觉 QA；HTTP/静态契约、构建产物和响应式 CSS 检查已通过。
