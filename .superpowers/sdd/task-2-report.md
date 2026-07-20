# Task 2 Docker 打包与启动链路报告

## RED

命令：

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_docker_startup.py
```

预期失败：退出码 `1`，`check_missing_secret_stops_before_migration` 断言失败。此时 `backend/docker-entrypoint.sh` 尚不存在，入口无法输出预期的 `JWT_SECRET must be set`，证明新测试覆盖的是缺失的启动行为。

## GREEN

命令与输出摘要：

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_docker_startup.py
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_migrations.py
```

输出：`docker startup tests pass`、`alembic migrations and legacy baseline pass`。

额外验证：

```bash
docker compose config --quiet
backend/.venv/bin/python backend/tests/test_acceptance.py
sh -n backend/docker-entrypoint.sh
backend/.venv/bin/python -m compileall -q backend/app backend/tests
git diff --check
```

Compose 配置有效；验收测试为 `71/71` 通过；Shell 语法、Python 编译和空白检查均通过。

## 改动文件

- `.dockerignore`
- `Dockerfile`
- `docker-compose.yml`
- `backend/docker-entrypoint.sh`
- `backend/tests/test_docker_startup.py`
- `README.md`
- `README_ZH.md`

## 提交 SHA

实现提交：`0d2217cf55e004a06bd330f3743ce62cb2e476f0`（`feat: add secure Docker startup flow`）。

## 自审与关注点

- Docker 镜像复制 Alembic 配置、迁移、后端和前端；入口先校验两个密钥，再迁移，最后以 `0.0.0.0:8000` 启动 Uvicorn。
- Docker 默认 SQLite 地址为 `sqlite:////data/app.db`，Compose 挂载整个 `./data:/data` 目录。
- Dockerfile 未写入 `JWT_SECRET` 或 `AES_KEY`；`.dockerignore` 排除密钥、数据库、环境文件、虚拟环境、Git、worktree、内部文档及测试/归档材料。
- 已尝试 `docker build -t translator-management-system:task-2-test .`，但本机 Docker 守护进程未运行（`/Users/spellbook/.docker/run/docker.sock` 不存在），因此无法完成真实镜像构建和容器启动验证；其余无 Docker 守护进程依赖的验证已通过。
