# Lingua Control · Sites Demo

Cloudflare Worker 兼容的译员运营受控 Demo，用于演示译员、费率、PO、审核和 Excel 导出的核心流程。它不替代仓库中的 FastAPI 正式后端。

## 数据与安全边界

- 结构化业务数据以 Sites D1 逻辑绑定 `DB` 为唯一权威来源；未使用浏览器存储代替持久化。
- 首次访问会幂等创建表和带“示例”标记的最小数据，不含真实个人、付款或凭据信息。
- 站点应由 Codex Sites 以 owner-only 私有方式发布。页面内的免密码角色切换和 `x-demo-role` 头只是演示机制，不是生产身份认证或授权方案。
- 服务端演示权限：`boss` 可编辑和审批；`editor` 可编辑业务数据但不可审批；`viewer` 只读；`agent` 只能提交费率或 PO 待审提案。
- Boss 批准提案时，业务写入与审核状态更新在同一 D1 `batch()` 中完成。

## 本地验证

需要 Node.js `>=22.13.0`。

```bash
npm install
npm run test:unit
npm run db:generate
npm run build
npm run dev
```

关键端点：

- `GET /api/health`：机器可判定的健康状态。
- `GET /api/workspace`：幂等初始化 D1 并返回工作台当前数据。
- `/api/translators`、`/api/rates`、`/api/pos`：受 Demo 角色限制的业务写入。
- `/api/approvals`：提案与 Boss 审批。
- `GET /api/export`：导出包含当前译员和 PO 的 `.xlsx`。

迁移位于 `drizzle/`；`.openai/hosting.json` 声明 D1 绑定 `DB` 且不使用 R2。
