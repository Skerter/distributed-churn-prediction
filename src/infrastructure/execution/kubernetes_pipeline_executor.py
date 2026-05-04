from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.application.dto.requests import CreatePipelineRunRequest
from src.app.settings import Settings
from src.infrastructure.pipeline_runs.file_store import FilePipelineRunStore
from src.shared.enums import PipelineRunStatus


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_run_id(profile: str) -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:8]
    return f"{timestamp}-{profile.replace('_', '-')}-{suffix}"


class KubernetesJobPipelineExecutor:
    """Создаёт Kubernetes Job для запуска pipeline."""

    def __init__(
        self,
        *,
        settings: Settings,
        store: FilePipelineRunStore,
        logger,
        max_concurrent_runs: int = 1,
    ) -> None:
        self.settings = settings
        self.store = store
        self.logger = logger
        self.max_concurrent_runs = max_concurrent_runs

    def submit(self, request: CreatePipelineRunRequest) -> dict:
        if self.max_concurrent_runs <= 1 and self.store.has_active_runs():
            raise RuntimeError("Уже есть активный pipeline run")

        run_id = _new_run_id(self.settings.api.kubernetes.pipeline_profile)
        job_name = f"{self.settings.api.kubernetes.job_name_prefix}-{run_id}"

        now = _utc_now_iso()
        payload = {
            "run_id": run_id,
            "status": PipelineRunStatus.QUEUED.value,
            "profile": self.settings.api.kubernetes.pipeline_profile,
            "executor": "kubernetes_job",
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "request": {
                "execute": request.execute,
                "skip_load": request.skip_load,
                "skip_features": request.skip_features,
                "skip_train": request.skip_train,
                "skip_eval": request.skip_eval,
            },
            "result": None,
            "error": None,
            "metadata": {
                "kubernetes_job_name": job_name,
                "namespace": self.settings.api.kubernetes.namespace,
            },
        }

        self.store.create(payload)
        self._create_job(job_name=job_name, run_id=run_id, request=request)

        self.store.update_metadata(
            run_id,
            {
                "kubernetes_job_created": True,
            },
        )

        self.logger.info(
            "Kubernetes pipeline Job создан: run_id=%s job=%s",
            run_id,
            job_name,
        )

        return self.store.mark_running(run_id)

    def refresh(self, run_id: str) -> dict:
        payload = self.store.get(run_id)

        job_name = payload.get("metadata", {}).get("kubernetes_job_name")
        if not job_name:
            return payload

        status = self._read_job_status(job_name)

        if status == PipelineRunStatus.SUCCEEDED.value:
            return self.store.mark_succeeded(run_id)

        if status == PipelineRunStatus.FAILED.value:
            return self.store.mark_failed(run_id, error="Kubernetes Job failed")

        return payload

    def _load_kubernetes_config(self) -> None:
        from kubernetes import config
        from kubernetes.config.config_exception import ConfigException

        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()

    def _create_job(
        self,
        *,
        job_name: str,
        run_id: str,
        request: CreatePipelineRunRequest,
    ) -> None:
        self._load_kubernetes_config()

        from kubernetes import client

        k8s = self.settings.api.kubernetes

        args = [
            "python",
            "-m",
            "src.presentation.cli.main",
            "run-pipeline",
            "--profile",
            k8s.pipeline_profile,
        ]

        if request.execute:
            args.append("--execute")

        if request.skip_load:
            args.append("--skip-load")
        if request.skip_features:
            args.append("--skip-features")
        if request.skip_train:
            args.append("--skip-train")
        if request.skip_eval:
            args.append("--skip-eval")

        container = client.V1Container(
            name="dcp-pipeline",
            image=k8s.job_image,
            image_pull_policy=k8s.image_pull_policy,
            args=args,
            env=[
                client.V1EnvVar(name="PYTHONUNBUFFERED", value="1"),
                client.V1EnvVar(name="PYTHONPATH", value="/app"),
                client.V1EnvVar(name="DCP_RUN_ID", value=run_id),
            ],
            volume_mounts=[
                client.V1VolumeMount(
                    name="dcp-storage",
                    mount_path=k8s.storage_mount_path,
                ),
            ],
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "app": "dcp-pipeline",
                    "component": "pipeline-job",
                    "dcp.run_id": run_id,
                },
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                volumes=[
                    client.V1Volume(
                        name="dcp-storage",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=k8s.storage_pvc_name,
                        ),
                    ),
                ],
            ),
        )

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name=job_name),
            spec=client.V1JobSpec(
                backoff_limit=0,
                template=template,
            ),
        )

        batch_api = client.BatchV1Api()
        batch_api.create_namespaced_job(
            namespace=k8s.namespace,
            body=job,
        )

    def _read_job_status(self, job_name: str) -> str:
        self._load_kubernetes_config()

        from kubernetes import client

        batch_api = client.BatchV1Api()

        job = batch_api.read_namespaced_job_status(
            name=job_name,
            namespace=self.settings.api.kubernetes.namespace,
        )

        conditions = job.status.conditions or []

        for condition in conditions:
            if condition.type == "Complete" and condition.status == "True":
                return PipelineRunStatus.SUCCEEDED.value

            if condition.type == "Failed" and condition.status == "True":
                return PipelineRunStatus.FAILED.value

        return PipelineRunStatus.RUNNING.value