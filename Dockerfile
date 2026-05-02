FROM mambaorg/micromamba:1.5.10

WORKDIR /app

COPY environment_linux.yml /tmp/environment_linux.yml

RUN micromamba env create -f /tmp/environment_linux.yml && \
    micromamba clean --all --yes

COPY src /app/src
COPY configs /app/configs

ENV MAMBA_DOCKERFILE_ACTIVATE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PATH=/opt/conda/envs/dist-churn-pred-env/bin:$PATH

SHELL ["micromamba", "run", "-n", "dist-churn-pred-env", "/bin/bash", "-c"]

# Проверка, что все библиотеки импортируются без ошибок
# RUN python -c "import dask, distributed, pandas, pyarrow, xgboost, coloredlogs, kagglehub; print('k8s env ok')"

ENTRYPOINT ["micromamba", "run", "-n", "dist-churn-pred-env"]
CMD ["python", "-m", "src.presentation.cli.main", "health", "--profile", "pandas"]