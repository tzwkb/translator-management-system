# 译员管理系统 Docker Demo 交付记录

> 日期：2026-07-20｜状态：Render 免费 Demo 已上线

## 交付物

- Docker 镜像：`translator-management-system:demo-20260720`
- Demo 地址：<https://translator-management-system.onrender.com>
- 云平台：Render Free Web Service
- 镜像 ID：`sha256:d7556cc8aa47631c32e105c3900d19819d256488d2c933da5d08a15295c3ffef`
- 镜像大小：66,287,904 bytes
- 开发分支：`codex/docker-cloud-demo`
- 最终提交：`b85ba479522ac608452afe9f83af156aa39c5223`

## Docker 启动配置

- 必填：`JWT_SECRET`、`AES_KEY`（64 位十六进制）。缺少任一项时容器非零退出。
- 默认：`DB_URL=sqlite:////data/app.db`、`TOKEN_TTL=28800`。
- 持久目录：宿主目录挂载至容器 `/data`。
- 启动顺序：密钥检查 → `alembic upgrade head` → Uvicorn `0.0.0.0:8000`。
- 当前 Alembic 版本：`20260717_0001`。

## 验证结果

- Docker 镜像真实构建成功。
- 空数据目录首次启动成功，Alembic 自动创建数据库。
- 首页 HTTP 200；FastAPI 外部验收 71/71 通过。
- Render 云端首页 HTTP 200，页面为原 `frontend/index.html` UI。
- 云端资源端登录 HTTP 200，角色为 `editor`；页面示例数据加载正常。
- 容器删除后使用同一数据目录重建，测试译员记录仍存在。
- 缺密钥时容器退出码 1，应用未启动。

## 安全与已知限制

- 应用内免密码角色 token 仅适合受控 Demo，不是正式权限系统。
- 免费云实例使用临时文件系统，重启或重新部署后 SQLite 数据可能丢失。
- Demo 使用示例数据，不应录入真实付款或个人敏感信息。
- 未执行浏览器视觉回归；已完成 HTTP、Docker 构建和业务流程验证。
- 正式账号、备份、监控、PostgreSQL、多实例、自定义域名仍属于后续生产化范围。
