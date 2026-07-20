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

## 审查修复（TOKEN_TTL 与 AES_KEY 覆盖）

### RED

新增 `check_missing_aes_key_stops_before_migration`，验证 `JWT_SECRET` 存在但 `AES_KEY` 缺失时，入口会在 Alembic 迁移前以 `AES_KEY must be set` 失败。该行为已由既有入口实现满足；本轮配置回归的 RED 命令为：

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_docker_startup.py
```

输出：退出码 `1`，`assert "TOKEN_TTL:" not in compose` 失败。失败原因是 Compose 的 `environment.TOKEN_TTL=${TOKEN_TTL:-28800}` 覆盖了 `env_file: ./data/.env` 内的同名设置。

### GREEN

最小修改：删除 Compose 的 `TOKEN_TTL` 环境项，保留 Dockerfile 的 `ENV TOKEN_TTL=28800` 作为未设置时的镜像默认值。

命令与输出：

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/tests/test_docker_startup.py
docker compose config --quiet
docker compose config | rg -C 2 'TOKEN_TTL|DB_URL'
git diff --check
```

输出：`docker startup tests pass`；Compose 配置检查通过，使用临时 `data/.env` 的解析结果为 `TOKEN_TTL: "1234"`，证明该值不再被覆盖；空白检查通过。临时验证环境文件已删除。

修复提交：`829a2cc3ccd7bbb9db9ff8a5a91f038600fe573f`（`fix: preserve compose token TTL override`）。
