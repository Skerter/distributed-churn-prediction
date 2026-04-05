# Используем официальный Miniconda3 образ
FROM continuumio/miniconda3:latest

# Рабочая директория в контейнере
WORKDIR /app

# Копируем environment.yml в контейнер
COPY environment_linux.yml .

# Создаём окружение conda и чистим кеш
RUN conda env create -f environment_linux.yml && \
    conda clean -afy

# Копируем весь проект в контейнер
COPY . .

# Устанавливаем PYTHONPATH для проекта
ENV PYTHONPATH=/app

# Указываем shell для всех последующих команд, чтобы conda environment использовалось
SHELL ["conda", "run", "-n", "dist-churn-pred-env", "/bin/bash", "-c"]

# ENTRYPOINT теперь активирует conda environment
ENTRYPOINT ["conda", "run", "-n", "dist-churn-pred-env"]

# CMD оставляем пустым — Kubernetes задаёт args: dask-scheduler / dask-worker
CMD []