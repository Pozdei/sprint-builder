#!/bin/bash
# Перенос БД из локального Postgres (brew/host) в Docker Postgres.
#
# Использование:
#   ./scripts/migrate-from-local.sh
#
# Параметры:
#   LOCAL_DB    — имя локальной БД (по умолчанию: sprint_builder)
#   LOCAL_USER  — юзер локальной БД (по умолчанию: sprint_app)
#   LOCAL_HOST  — хост (по умолчанию: localhost)
#   LOCAL_PORT  — порт (по умолчанию: 5432)
#
# Скрипт:
#   1. Делает дамп локальной БД через pg_dump.
#   2. Поднимает Docker (docker compose up -d postgres).
#   3. Ждёт, пока БД примет соединения.
#   4. Загружает дамп в Docker-Postgres.

set -e

LOCAL_DB="${LOCAL_DB:-sprint_builder}"
LOCAL_USER="${LOCAL_USER:-sprint_app}"
LOCAL_HOST="${LOCAL_HOST:-localhost}"
LOCAL_PORT="${LOCAL_PORT:-5432}"

DUMP_FILE="$(mktemp -t sprint_builder_dump.XXXXXX.sql)"

# Останавливаем локальный сервис?
# НЕТ — мы только читаем. Локальный Postgres продолжает работать.

echo "[migrate] Делаю дамп локальной БД: $LOCAL_USER@$LOCAL_HOST:$LOCAL_PORT/$LOCAL_DB"
pg_dump \
    -U "$LOCAL_USER" \
    -h "$LOCAL_HOST" \
    -p "$LOCAL_PORT" \
    -d "$LOCAL_DB" \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    > "$DUMP_FILE"

echo "[migrate] Дамп: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# Поднимаем Docker postgres
echo "[migrate] Запускаю Docker postgres…"
docker compose up -d postgres

# Ждём готовности
echo "[migrate] Жду готовности БД…"
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-sprint_app}" \
        -d "${POSTGRES_DB:-sprint_builder}" >/dev/null 2>&1; then
        echo "[migrate] БД готова."
        break
    fi
    sleep 1
done

# Загружаем дамп
echo "[migrate] Загружаю дамп в Docker-Postgres…"
docker compose exec -T postgres psql \
    -U "${POSTGRES_USER:-sprint_app}" \
    -d "${POSTGRES_DB:-sprint_builder}" \
    < "$DUMP_FILE"

echo "[migrate] Готово."
echo "[migrate] Дамп можно удалить: rm $DUMP_FILE"
echo
echo "Дальше:"
echo "  docker compose up -d --build"
echo "  открой http://localhost"
