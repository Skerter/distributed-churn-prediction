FROM python:3.11-slim

RUN pip install --no-cache-dir mlflow==2.19.0 psycopg2-binary

EXPOSE 5000

CMD ["sh", "-c", "mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri $DATABASE_URL --default-artifact-root /tmp/mlflow-artifacts"]
