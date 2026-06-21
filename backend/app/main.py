# -*- coding: utf-8 -*-
"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .logging_conf import setup_logging
from .routers import auth, dashboard, projects, providers, users
from .seed import init_db

# 尽早初始化日志，确保启动阶段与各模块日志按 LOG_LEVEL 输出
setup_logging()

app = FastAPI(title="智能体运营中心看板 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境放开；生产环境请收敛为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(providers.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
