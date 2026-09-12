"""FastAPI entry point.

    uvicorn app.main:app --reload --port 8000

Docs at /docs. The dashboard can also run entirely from the exported JSON, so
the API is a convenience for integration rather than a hard dependency.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import refresh_cache, router
from app.config import settings
from app.db.models import init_db

app = FastAPI(
    title="PSX Stock Recommendation Engine",
    version="1.0.0",
    description=(
        "Scores and ranks KSE-100 companies from financial statements, "
        "sector-relative ratios and price data, and returns a plain-language "
        "explanation with every recommendation.\n\n"
        "**Research and educational use only. Not investment advice.**"
    ),
    docs_url="/docs",
    openapi_tags=[
        {"name": "recommendations", "description": "Ranked, explained picks"},
        {"name": "companies", "description": "Per-company dossiers"},
        {"name": "backtest", "description": "Walk-forward evidence vs the KSE-100"},
        {"name": "model", "description": "Model diagnostics"},
        {"name": "market", "description": "Index, sectors and macro"},
        {"name": "system", "description": "Health and configuration"},
    ],
)

# Dev dashboard ports. Next picks the next free port when 3000 is taken, so the
# common fallbacks are allowed too. Override with a comma-separated
# PSX_CORS_ORIGINS when serving the dashboard from anywhere else.
_default_origins = [
    f"http://{host}:{port}"
    for port in (3000, 3001, 3100)
    for host in ("localhost", "127.0.0.1")
]
cors_origins = [
    o.strip()
    for o in os.getenv("PSX_CORS_ORIGINS", ",".join(_default_origins)).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    refresh_cache()


@app.get("/", include_in_schema=False)
def root():
    return JSONResponse({
        "name": "PSX Stock Recommendation Engine",
        "docs": "/docs",
        "health": "/api/health",
        "database": settings.database_url,
    })
