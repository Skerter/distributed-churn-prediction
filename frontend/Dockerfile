FROM nginx:alpine

# Копируем статику (пути от корня репозитория — Railway строит из root)
COPY frontend/index.html /usr/share/nginx/html/
COPY frontend/style.css  /usr/share/nginx/html/
COPY frontend/app.js     /usr/share/nginx/html/

# Шаблон nginx — PORT будет подставлен envsubst
COPY frontend/nginx.conf /etc/nginx/templates/default.conf.template

# Скрипт запуска
COPY frontend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
