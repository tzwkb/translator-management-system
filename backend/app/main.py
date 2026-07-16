"""应用入口：建表、写种子、挂路由、发前端页面。

启动：backend/ 目录下 `uvicorn app.main:app --port 8000`，或 `python -m app.main`。
"""
from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import config
from . import models  # noqa: F401  确保模型注册到 Base
from .db import Base, engine, ensure_schema
from .routers import router
from .seed import seed

Base.metadata.create_all(engine)
ensure_schema()
seed()

app = FastAPI(title="译员管理系统")
app.include_router(router)


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html",
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
