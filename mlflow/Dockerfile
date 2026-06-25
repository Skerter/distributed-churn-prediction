FROM python:3.11-slim

RUN pip install --no-cache-dir mlflow==2.19.0 psycopg2-binary

EXPOSE 5000

# --default-artifact-root указывает на /mlflow-artifacts — это общий named volume,
# смонтированный также в backend/bot (MLflow-клиенты пишут артефакты сами).
# Без общего тома UI показал бы метрики/параметры, но не файлы модели.
CMD ["sh", "-c", "mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri $DATABASE_URL --default-artifact-root /mlflow-artifacts"]
