#!/usr/bin/env bash
set -euo pipefail

log() {
    printf '[*] %s\n' "$*"
}

fail() {
    printf '[!] %s\n' "$*" >&2
    exit 1
}

log "Проверка расположения проекта"
for required in docker-compose.yml .env.example; do
    if [[ ! -f "$required" ]]; then
        fail "Файл '$required' не найден. Запустите скрипт из корня репозитория."
    fi
done

log "Проверка наличия docker"
if ! command -v docker >/dev/null 2>&1; then
    fail "Команда 'docker' не найдена. Установите Docker."
fi

log "Проверка наличия docker compose"
if ! docker compose version >/dev/null 2>&1; then
    fail "Команда 'docker compose' недоступна. Убедитесь, что используете современную версию Docker."
fi

log "Подготовка .env"
if [[ ! -f .env ]]; then
    cp .env.example .env
    log ".env создан из .env.example. Обновите значения перед запуском."
else
    log ".env уже существует — пропускаем копирование."
fi
