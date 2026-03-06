import dask
from dask.distributed import Client, progress
import coloredlogs
import logging

# Логи с coloredlogs (из config.yaml: use_coloredlogs=true)
coloredlogs.install(level='INFO', fmt='%(asctime)s %(levelname)s %(message)s')

def setup_dask_client(n_workers=4):
    client = Client(n_workers=n_workers, threads_per_worker=1, memory_limit='4GB')  # Adjust по твоей машине
    logging.info(f"Dask Client initialized: {client}")
    return client

if __name__ == "__main__":
    client = setup_dask_client()
    # Здесь добавим код предобработки/feature eng