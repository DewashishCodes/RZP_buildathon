from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.batches import router as batches_router
from app.api.cases import router as cases_router
from app.api.jobs import router as jobs_router
from app.api.merchants import router as merchants_router
from app.api.tickets import router as tickets_router
from app.api.webhooks import router as webhooks_router
from app.config import settings
from app.db.session import SessionLocal, get_db
from app.logging_config import configure_logging, new_request_id, request_id_ctx
from app.simulation.merchants import seed_merchants

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # So GET /merchants always has data without a manual seeding step -
    # no auth in this build, so there's no signup flow that would
    # otherwise create a tenant.
    db = SessionLocal()
    try:
        seed_merchants(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Janus — AI Revenue Recovery Agent", lifespan=lifespan)

# Local-dev-only CORS: the Next.js dashboard runs on a different origin
# (localhost:3000) than this API (localhost:8000). No auth/cookies in this
# project, so a permissive localhost allowlist is fine - not for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Every log line emitted while handling a request carries this id
    (JsonFormatter reads it off the contextvar), and it's echoed back on
    the response so a client/log aggregator can correlate the two sides.
    Reuses an inbound X-Request-ID if the caller (or a load balancer)
    already set one, rather than always minting a new one.
    """
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response

app.include_router(batches_router)
app.include_router(cases_router)
app.include_router(merchants_router)
app.include_router(tickets_router)
app.include_router(jobs_router)
app.include_router(webhooks_router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Not a static dict: pings Postgres and reports LLM config presence, so
    a misconfigured environment surfaces here instead of as an opaque
    mid-batch failure right before a demo."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health must report, not raise
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "up" if db_ok else "down",
        "gemini_configured": bool(settings.gemini_api_key),
    }
