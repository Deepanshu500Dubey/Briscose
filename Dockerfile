FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY tests ./tests

EXPOSE 8000

# Shell form so $PORT expands — Cloud Run injects its own PORT (8080) at
# runtime; local docker-compose.yml doesn't set one, hence the :-8000
# fallback to match its published port mapping.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
