from dask.distributed import Client, LocalCluster


def create_client(config, logger) -> Client | None:
    mode = config["dask"]["mode"]

    if mode == "dask_local":
        logger.info("Запуск локального Dask кластера с %d воркерами", config["dask"]["n_workers"])

        cluster = LocalCluster(
            n_workers=config["dask"]["n_workers"]
        )
        return Client(cluster)

    elif mode == "k8s":
        addr = config["dask"]["scheduler_address"]

        logger.info(f"Подключение к Dask планировщику: {addr}")

        return Client(addr)

    else:
        logger.info("Режим Pandas: клиент Dask отсутствует")
        return None