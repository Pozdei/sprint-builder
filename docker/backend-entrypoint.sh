#!/bin/sh
# Запускается при старте backend-контейнера.
# 1. Ждём, пока Postgres примет соединения.
# 2. Прогоняем alembic upgrade head.
# 3. Запускаем uvicorn (или то, что передано как CMD).

set -e

python - <<'PY'
import os, time
import psycopg
url = os.environ.get("DATABASE_URL", "")
url_pg = url.replace("postgresql+psycopg://", "postgresql://", 1)
deadline = time.time() + 60
last_err = None
while time.time() < deadline:
    try:
        with psycopg.connect(url_pg, connect_timeout=3) as conn:
            pass
        print("[entrypoint] БД доступна.")
        break
    except Exception as e:
        last_err = e
        print(f"[entrypoint] Жду БД: {e}")
        time.sleep(2)
else:
    raise SystemExit(f"БД не ответила за 60 секунд: {last_err}")
PY

echo "[entrypoint] Применяю миграции…"
alembic upgrade head

echo "[entrypoint] Запускаю: $*"
exec "$@"
