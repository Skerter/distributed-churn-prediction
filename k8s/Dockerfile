FROM mambaorg/micromamba:1.5.8

WORKDIR /app

COPY --chown=$MAMBA_USER:$MAMBA_USER environment_linux.yml .

RUN micromamba create -y -f environment_linux.yml && \
   micromamba clean --all --yes

ENV PATH=/opt/conda/envs/dist-churn-pred-env/bin:$PATH

COPY --chown=$MAMBA_USER:$MAMBA_USER . .

CMD ["python"]