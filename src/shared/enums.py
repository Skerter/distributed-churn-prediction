from enum import Enum


class RuntimeMode(str, Enum):
    PANDAS = "pandas"
    DASK_LOCAL = "dask_local"
    DASK_K8S = "dask_k8s"


class BackendKind(str, Enum):
    LOCAL = "local"
    DASK = "dask"


class PipelineExecutorKind(str, Enum):
    CLI = "cli"
    WEB = "web"
    BOT = "bot"
    KUBERNETES_JOB = "kubernetes_job"


class PipelineRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"