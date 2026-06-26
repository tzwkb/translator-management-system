"""配置。密钥/数据库走环境变量，开发时有本地默认。"""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent       # backend/app
BASE_DIR = APP_DIR.parent                         # backend
PROJECT_DIR = BASE_DIR.parent                     # 译员管理系统
FRONTEND_DIR = PROJECT_DIR / "frontend"

# 上线用环境变量；不设则用本地默认（仅开发）
DB_URL = os.getenv("DB_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
JWT_SECRET = os.getenv("JWT_SECRET")              # 不设则运行时随机
AES_KEY_HEX = os.getenv("AES_KEY")                # 64 位 hex(=32字节)；不设则用 .key 文件
KEYFILE = BASE_DIR / ".key"
TOKEN_TTL = int(os.getenv("TOKEN_TTL", 8 * 3600))   # token 有效期(秒)，默认 8 小时
