from fastapi import FastAPI

app = FastAPI(title="AI Revenue Recovery Agent")


@app.get("/health")
def health():
    return {"status": "ok"}
