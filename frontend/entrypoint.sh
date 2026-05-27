#!/bin/sh
set -e

# Подставляем URL бэкенда из env-переменной BACKEND_URL
# Локально fallback на 127.0.0.1:8000
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
sed -i "s|__API_BASE_URL__|${BACKEND_URL}|g" /usr/share/nginx/html/app.js

# envsubst подставляет $PORT в nginx.conf
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec "$@"
