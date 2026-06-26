"""数据库引擎与 ORM 基类。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from .config import DB_URL

engine = create_engine(DB_URL)


class Base(DeclarativeBase):
    pass
