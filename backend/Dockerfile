FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Applies migrations before serving so a fresh container is immediately
# usable against a bare Postgres - matches the documented manual sequence
# (alembic upgrade head, then uvicorn) in CLAUDE.md.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]
