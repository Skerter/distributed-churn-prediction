from enum import Enum


class RuntimeMode(str, Enum):
    PANDAS = "pandas"
    DASK_LOCAL = "dask_local"
    DASK_K8S = "dask_k8s"


class BackendKind(str, Enum):
    LOCAL = "local"
    DASK = "dask"