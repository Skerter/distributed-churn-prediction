# Используем официальный Miniconda3 образ
FROM continuumio/miniconda3:latest

# Рабочая директория в контейнере
WORKDIR /app

# Копируем environment.yml в контейнер
COPY environment.yml .

# Создаём окружение conda и чистим кеш
RUN conda env create -f environment_linux.yml && \
    conda clean -afy

# Сделаем conda-окружение активным по умолчанию для всех следующих команд
SHELL ["conda", "run", "-n", "dist-churn-pred-env", "/bin/bash", "-c"]

# Копируем весь проект в контейнер
COPY . .

# Устанавливаем PYTHONPATH для проекта
ENV PYTHONPATH=/app

# Команда по умолчанию (замени src/main.py на реальный файл запуска)
CMD ["python", "main.py"]