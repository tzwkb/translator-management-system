"""配置。密钥/数据库走环境变量，开发时有本地默认。"""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent       # backend/app
BASE_DIR = APP_DIR.parent                         # backend
PROJECT_DIR = BASE_DIR.parent                     # 译员管理系统
FRONTEND_DIR = PROJECT_DIR / "frontend"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads")).resolve()
UPLOAD_MAX_BYTES = int(os.getenv("UPLOAD_MAX_BYTES", 100 * 1024 * 1024))

# 上线用环境变量；不设则用本地默认（仅开发）
DB_URL = os.getenv("DB_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
JWT_SECRET = os.getenv("JWT_SECRET")              # 不设则运行时随机
AES_KEY_HEX = os.getenv("AES_KEY")                # 64 位 hex(=32字节)；不设则用 .key 文件
KEYFILE = BASE_DIR / ".key"
TOKEN_TTL = int(os.getenv("TOKEN_TTL", 8 * 3600))   # token 有效期(秒)，默认 8 小时
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "0").lower() in {"1", "true", "yes"}
