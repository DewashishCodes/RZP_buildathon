from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.batches import router as batches_router
from app.api.cases import router as cases_router

app = FastAPI(title="AI Revenue Recovery Agent")

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


@app.get("/health")
def health():
    return {"status": "ok"}
