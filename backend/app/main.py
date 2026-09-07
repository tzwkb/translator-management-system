"""应用入口：写种子、挂路由、发前端页面。

启动：backend/ 目录下 `uvicorn app.main:app --port 8000`，或 `python -m app.main`。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import config
from .routers import router
from .seed import seed
from .intake.admin import router as intake_admin_router
from .intake.public import router as intake_public_router
from .intake.http import configure_public_http


@asynccontextmanager
async def lifespan(_app):
    seed()
    yield


app = FastAPI(title="译员管理系统", lifespan=lifespan)
app.include_router(router)
app.include_router(intake_admin_router)
app.include_router(intake_public_router)
configure_public_http(app)


@app.get("/intake-admin.js", include_in_schema=False)
def intake_admin_script():
    return FileResponse(config.FRONTEND_DIR / "intake" / "admin.js",
                        media_type="text/javascript", headers={"Cache-Control": "no-store"})


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html",
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
