"""把各模块的子路由合成一个 router 供 main 挂载。"""
from fastapi import APIRouter

from . import admin, core, po, translators

router = APIRouter()
for _m in (core, translators, po, admin):
    router.include_router(_m.router)
