#!/bin/sh
set -eu

cd "$(dirname "$0")"
APP_DIR="$(pwd)"
PROJECT_DIR="$(cd .. && pwd)"
DATA_DIR="$PROJECT_DIR/data"

mkdir -p "$DATA_DIR"

ENV_FILE="${ENV_FILE:-$DATA_DIR/.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi

if [ -z "${JWT_SECRET:-}" ] || [ -z "${AES_KEY:-}" ]; then
    echo "缺少 JWT_SECRET 或 AES_KEY。请先写入 $ENV_FILE：" >&2
    echo "  printf 'JWT_SECRET=%s\\n' \"\$(openssl rand -hex 32)\" >> $ENV_FILE" >&2
    echo "  printf 'AES_KEY=%s\\n' \"\$(openssl rand -hex 32)\" >> $ENV_FILE" >&2
    exit 1
fi

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ] && [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
fi
if [ -z "$PYTHON" ] && [ -x "$APP_DIR/.venv/bin/python" ]; then
    PYTHON="$APP_DIR/.venv/bin/python"
fi
if [ -z "$PYTHON" ]; then
    PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ]; then
    echo "未找到可用的 python3，请设置 PYTHON 指向项目 venv 的解释器" >&2
    exit 1
fi

REQ_FILE="$APP_DIR/requirements.txt"
STAMP_FILE="$DATA_DIR/.requirements.sha256"
if [ -f "$REQ_FILE" ]; then
    if command -v shasum >/dev/null 2>&1; then
        NEW_STAMP="$(shasum -a 256 "$REQ_FILE" | cut -d' ' -f1)"
    else
        NEW_STAMP="$(sha256sum "$REQ_FILE" | cut -d' ' -f1)"
    fi
    OLD_STAMP="$(cat "$STAMP_FILE" 2>/dev/null || echo none)"
    if [ "$NEW_STAMP" != "$OLD_STAMP" ]; then
        echo "安装依赖：$PYTHON"
        "$PYTHON" -m pip install -r "$REQ_FILE"
        printf '%s\n' "$NEW_STAMP" > "$STAMP_FILE"
    fi
fi

echo "执行数据库迁移…"
"$PYTHON" -m alembic -c alembic.ini upgrade head

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-9020}"
ROOT_PATH="${ROOT_PATH:-}"
echo "启动 uvicorn：${HOST}:${PORT}${ROOT_PATH:+ root_path=${ROOT_PATH}}"

if [ -n "$ROOT_PATH" ]; then
    "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --root-path "$ROOT_PATH" &
else
    "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" &
fi
CHILD=$!
trap 'kill -TERM "$CHILD" 2>/dev/null' TERM INT

set +e
wait "$CHILD"
STATUS=$?
set -e
exit "$STATUS"
