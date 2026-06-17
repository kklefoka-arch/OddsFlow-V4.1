"""OddsFlow V4 — FastAPI application entry point."""
# reload-bump 2026-06-09: force uvicorn --reload to restart the worker and
# release any stale DB lock held by a wedged request.

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.database import init_db
from app.settings import settings
from app.api.routes_health import router as health_router
from app.api.routes_foundation import router as foundation_router
from app.api.routes_fixtures import router as fixtures_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_picks import router as picks_router
from app.api.routes_upcoming import router as upcoming_router
from app.api.routes_reports import router as reports_router
from app.api.routes_inspector import router as inspector_router
from app.api.routes_diagnostics import router as diagnostics_router
from app.api.routes_results import router as results_router
from app.api.routes_webhooks import router as webhooks_router

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "frontend" / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _livescores_loop(interval_s: int = 300) -> None:
    """In-process livescores poller (added 2026-06-17).

    Replaces the fragile ``OddsFlow_LivescoresPoller`` scheduled task, which
    repeatedly stopped firing across PC sleep / off-days. This runs for as long
    as the (already auto-restarting, boot-launched) uvicorn server runs, so the
    poller's uptime now equals the server's uptime — no Task Scheduler, no admin.

    Mirrors scripts/livescores_poller.py exactly: calls the in-process
    ``get_livescores()`` (which proxies Sportmonks inplay + auto-settles finished
    fixtures) and writes the same ``livescores_poller`` heartbeat to system_health.
    """
    import sqlite3
    import time
    from datetime import datetime, timezone

    time.sleep(15)  # let the app finish coming up before the first poll
    while True:
        now_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        try:
            from app.api.routes_results import get_livescores
            body = get_livescores()
            err = body.get("error")
            if err:
                msg = f"error: livescores upstream {err} ts={now_ts}"
            else:
                msg = (
                    f"ok: livescores={body.get('count', 0)} "
                    f"auto_written={body.get('auto_written', 0)} "
                    f"auto_settled={body.get('auto_settled', 0)} ts={now_ts}"
                )
        except Exception as exc:  # noqa: BLE001 - heartbeat must never crash the loop
            msg = f"error: {exc} ts={now_ts}"
        try:
            conn = sqlite3.connect(settings.sqlite_path)
            conn.execute(
                "INSERT INTO system_health (metric, value) VALUES (?, ?)",
                ("livescores_poller", msg),
            )
            conn.commit()
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(interval_s)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("OddsFlow V4 starting")
    init_db(settings.sqlite_path)
    import threading
    threading.Thread(target=_livescores_loop, name="livescores-poller",
                     daemon=True).start()
    logger.info("livescores poller thread started (in-process, 5 min)")
    yield


app = FastAPI(
    title="OddsFlow V4",
    version="4.0.0",
    description="Football betting analytics engine — operator portal.",
    lifespan=lifespan,
)

# ---- API routers ----
app.include_router(health_router)
app.include_router(picks_router)
app.include_router(upcoming_router)
app.include_router(foundation_router)
app.include_router(fixtures_router)
app.include_router(ingest_router)
app.include_router(reports_router)
app.include_router(inspector_router)
app.include_router(diagnostics_router)
app.include_router(results_router)
app.include_router(webhooks_router)


# ---- /healthz/deep (wired separately so the SPA health badge works) ----
@app.get("/healthz/deep", include_in_schema=False)
async def healthz_deep() -> dict:
    from app.api.routes_diagnostics import _healthz_deep_impl
    return _healthz_deep_impl()


# ---- SPA: serve engine_view.html at "/" and "/engine" ----
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/engine", response_class=HTMLResponse, include_in_schema=False)
async def spa(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse("engine_view.html", {"request": request})


# ---- /board removed — operator view at / serves all purposes ----


# ---- Static files ----
_static_dir = Path(__file__).parent / "frontend" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
