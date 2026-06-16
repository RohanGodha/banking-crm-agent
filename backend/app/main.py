"""FastAPI entrypoint."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_router
from app.api import chat as chat_router
from app.api import customers as customers_router
from app.api import health as health_router
from app.api import meta as meta_router
from app.api import outreach as outreach_router
from app.api import sessions as sessions_router
from app.api import tools as tools_router
from app.api import trace as trace_router
from app.db.sqlite_engine import bootstrap
from app.infrastructure.rag import init_retriever_async
from app.observability import configure_logging, get_logger
from app.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(
    title="banking-crm-agent",
    version="0.1.0",
    description="Agentic AI Copilot for Banking RMs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(sessions_router.router)
app.include_router(chat_router.router)
app.include_router(customers_router.router)
app.include_router(trace_router.router)
app.include_router(tools_router.router)
app.include_router(outreach_router.router)
app.include_router(meta_router.router)


@app.on_event("startup")
async def _startup() -> None:
    logger.info("Booting %s …", settings.app_name)
    bootstrap()  # DB + seed if empty
    # Register tools eagerly
    from app.application.tool_registry import get_registry  # noqa: PLC0415

    registry = get_registry()
    logger.info("Tools registered: %s", list(registry.keys()))
    # Kick off RAG init in the background so first request is fast
    asyncio.create_task(init_retriever_async())
    # Self-ping keep-alive (Render free tier)
    if settings.self_ping_url:
        asyncio.create_task(_self_ping_loop(settings.self_ping_url, settings.self_ping_interval_seconds))


async def _self_ping_loop(url: str, interval: int) -> None:
    import httpx

    while True:
        try:
            async with httpx.AsyncClient(timeout=5.0) as cli:
                await cli.get(url)
            logger.debug("self-ping ok → %s", url)
        except Exception as e:  # noqa: BLE001
            logger.warning("self-ping failed: %s", e)
        await asyncio.sleep(interval)


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "version": app.version,
        "docs": "/docs",
        "healthz": "/healthz",
    }
