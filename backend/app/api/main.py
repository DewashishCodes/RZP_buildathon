from fastapi import FastAPI

from app.api.batches import router as batches_router
from app.api.cases import router as cases_router

app = FastAPI(title="AI Revenue Recovery Agent")
app.include_router(batches_router)
app.include_router(cases_router)


@app.get("/health")
def health():
    return {"status": "ok"}
