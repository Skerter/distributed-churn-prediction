def get_backend(config, logger) -> str:
    mode = config["dask"]["mode"]

    if mode == "pandas":
        return "pandas"
    elif mode in ("dask_local", "k8s"):
        return "dask"
    else:
        logger.error("Неизвестный режим в config.yaml: %s", mode)
        raise ValueError(f"Неизвестный режим: {mode}")