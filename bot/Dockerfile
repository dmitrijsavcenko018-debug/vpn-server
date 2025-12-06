FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Устанавливаем системные зависимости для SSL и curl
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    ca-certificates \
    openssl \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Копируем все необходимые файлы бота
COPY api_client.py .
COPY bot_main.py .
COPY keyboards.py .
COPY texts.py .
COPY config.py .
COPY vpn_config_sender.py .
COPY handlers/ ./handlers/

# Обновляем pip и устанавливаем зависимости с обновленными SSL библиотеками
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    aiogram==3.* \
    httpx[cli] \
    python-dotenv \
    aiohttp \
    certifi \
    urllib3

CMD ["python", "bot_main.py"]
