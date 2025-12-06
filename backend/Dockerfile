FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wireguard-tools \
    openssh-client \
    sshpass \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    "sqlalchemy[asyncio]" \
    asyncpg \
    psycopg2-binary \
    alembic \
    pydantic \
    pydantic-settings \
    python-dotenv \
    httpx

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
