from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.batches import router as batches_router
from app.api.cases import router as cases_router
from app.api.jobs import router as jobs_router
from app.api.merchants import router as merchants_router
from app.api.tickets import router as tickets_router
from app.db.session import SessionLocal
from app.simulation.merchants import seed_merchants


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


app = FastAPI(title="AI Revenue Recovery Agent", lifespan=lifespan)

# Local-dev-only CORS: the Next.js dashboard runs on a different origin
# (localhost:3000) than this API (localhost:8000). No auth/cookies in this
# project, so a permissive localhost allowlist is fine - not for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batches_router)
app.include_router(cases_router)
app.include_router(merchants_router)
app.include_router(tickets_router)
app.include_router(jobs_router)


@app.get("/health")
def health():
    return {"status": "ok"}
