"""公开收集入口。仅将此应用端口暴露给公网，管理端保持内网。"""
from fastapi import FastAPI

from .intake.http import configure_public_http
from .intake.public import router

app = FastAPI(title="Langlobal · Translator profile", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)
configure_public_http(app)
