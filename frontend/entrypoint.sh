#!/bin/sh
set -e

# Каждый старт восстанавливаем исходный JS-шаблон, чтобы новые env применялись
# даже после обычного restart существующего контейнера.
cp /opt/frontend/app.js.template /usr/share/nginx/html/app.js

# Подставляем публичные URL сервисов. Локальные адреса остаются fallback'ами
# для запуска frontend напрямую, без Docker.
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
MLFLOW_URL="${MLFLOW_URL:-http://127.0.0.1:5000}"
sed -i "s|__API_BASE_URL__|${BACKEND_URL}|g" /usr/share/nginx/html/app.js
sed -i "s|__MLFLOW_URL__|${MLFLOW_URL}|g" /usr/share/nginx/html/app.js

# envsubst подставляет $PORT в nginx.conf
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec "$@"
