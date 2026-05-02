SHELL := /bin/bash

# ======================
# PROJECT
# ======================

APP_NAME := distributed-churn-prediction

# ======================
# LOCAL MINIKUBE IMAGE
# ======================

LOCAL_IMAGE := dcp-pipeline
LOCAL_TAG := latest
LOCAL_IMAGE_REF := $(LOCAL_IMAGE):$(LOCAL_TAG)

# ======================
# GHCR IMAGE
# ======================

GHCR_OWNER := skerter
GHCR_IMAGE := ghcr.io/$(GHCR_OWNER)/$(APP_NAME)
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)

# Используется для ручной локальной сборки/push в GHCR.
# Основной CI/CD workflow сам публикует branch tag и sha tag.
GHCR_TAG ?= $(GIT_SHA)
GHCR_IMAGE_REF := $(GHCR_IMAGE):$(GHCR_TAG)

# ======================
# KUBERNETES
# ======================

# Основной режим — GHCR.
# Для локального fallback:
# make k8s-recreate-cluster K8S_OVERLAY=minikube-local
# make k8s-run-job K8S_OVERLAY=minikube-local
K8S_OVERLAY ?= ghcr

K8S_BASE_DIR := k8s/base
K8S_CLUSTER_DIR := k8s/overlays/$(K8S_OVERLAY)/cluster
K8S_JOB_DIR := k8s/overlays/$(K8S_OVERLAY)/job

DASK_CLUSTER := dcp-cluster
PIPELINE_JOB := dcp-pipeline-job
PIPELINE_APP_LABEL := app=dcp-pipeline

# ======================
# HELP
# ======================

.PHONY: help
help:
	@echo "Доступные команды:"
	@echo ""
	@echo "Image:"
	@echo "  make minikube-build                  Собрать local image внутри Docker daemon Minikube"
	@echo "  make local-build                     Собрать local image в текущем Docker daemon"
	@echo "  make ghcr-build GHCR_TAG=<tag>       Собрать GHCR image локально"
	@echo "  make ghcr-push GHCR_TAG=<tag>        Push GHCR image вручную"
	@echo ""
	@echo "Kubernetes:"
	@echo "  make k8s-apply-storage               Применить PVC"
	@echo "  make k8s-recreate-cluster            Пересоздать DaskCluster через overlay"
	@echo "  make k8s-run-job                     Перезапустить pipeline Job через overlay"
	@echo "  make k8s-clean-job                   Удалить pipeline Job"
	@echo "  make k8s-status                      Показать pods/services/jobs/pvc"
	@echo ""
	@echo "Logs:"
	@echo "  make k8s-logs                        Смотреть stdout logs pipeline Job"
	@echo "  make k8s-app-log                     Смотреть /mnt/dcp/logs/app.log live"
	@echo "  make k8s-app-log-tail                Последние 200 строк /mnt/dcp/logs/app.log"
	@echo "  make k8s-clear-app-log               Очистить /mnt/dcp/logs/app.log"
	@echo ""
	@echo "Debug:"
	@echo "  make k8s-storage-check               Проверить PVC через scheduler pod"
	@echo "  make k8s-dashboard-forward           Пробросить Dask dashboard 8787"
	@echo "  make k8s-scheduler-forward           Пробросить scheduler 8786 и dashboard 8787"
	@echo "  make k8s-render-cluster              Показать итоговый cluster manifest после kustomize"
	@echo "  make k8s-render-job                  Показать итоговый job manifest после kustomize"
	@echo ""
	@echo "Переменные:"
	@echo "  K8S_OVERLAY=ghcr                     Основной режим через GHCR"
	@echo "  K8S_OVERLAY=minikube-local           Локальный fallback через dcp-pipeline:latest"
	@echo "  GHCR_TAG=<tag>                       Тег для ручной GHCR-сборки/push"
	@echo ""
	@echo "Примеры:"
	@echo "  make k8s-recreate-cluster"
	@echo "  make k8s-run-job"
	@echo "  make minikube-build"
	@echo "  make k8s-recreate-cluster K8S_OVERLAY=minikube-local"
	@echo "  make k8s-run-job K8S_OVERLAY=minikube-local"

# ======================
# IMAGE BUILD
# ======================

.PHONY: minikube-build
minikube-build:
	@echo "Сборка $(LOCAL_IMAGE_REF) внутри Docker daemon Minikube..."
	@eval $$(minikube docker-env) && docker build -t $(LOCAL_IMAGE_REF) .
	@echo "Готово: $(LOCAL_IMAGE_REF)"

.PHONY: local-build
local-build:
	@echo "Сборка $(LOCAL_IMAGE_REF) в текущем Docker daemon..."
	docker build -t $(LOCAL_IMAGE_REF) .

.PHONY: ghcr-build
ghcr-build:
	@echo "Сборка GHCR image: $(GHCR_IMAGE_REF)"
	docker build -t $(GHCR_IMAGE_REF) .

.PHONY: ghcr-push
ghcr-push:
	@echo "Push GHCR image: $(GHCR_IMAGE_REF)"
	docker push $(GHCR_IMAGE_REF)

# ======================
# KUBERNETES APPLY
# ======================

.PHONY: k8s-apply-storage
k8s-apply-storage:
	@echo "Применение PVC..."
	kubectl apply -f $(K8S_BASE_DIR)/cluster/pvc.yaml
	kubectl get pvc

.PHONY: k8s-recreate-cluster
k8s-recreate-cluster:
	@echo "Пересоздание DaskCluster $(DASK_CLUSTER) через overlay=$(K8S_OVERLAY)..."
	@echo "Cluster dir: $(K8S_CLUSTER_DIR)"
	kubectl delete daskcluster $(DASK_CLUSTER) --ignore-not-found=true
	kubectl apply -k $(K8S_CLUSTER_DIR)
	kubectl get pods -l dask.org/cluster-name=$(DASK_CLUSTER) -w

.PHONY: k8s-run-job
k8s-run-job:
	@echo "Перезапуск pipeline Job через overlay=$(K8S_OVERLAY)..."
	@echo "Job dir: $(K8S_JOB_DIR)"
	kubectl delete job $(PIPELINE_JOB) --ignore-not-found=true
	kubectl apply -k $(K8S_JOB_DIR)
	kubectl logs job/$(PIPELINE_JOB) -f

.PHONY: k8s-clean-job
k8s-clean-job:
	@echo "Удаление pipeline Job..."
	kubectl delete job $(PIPELINE_JOB) --ignore-not-found=true

# ======================
# STATUS
# ======================

.PHONY: k8s-status
k8s-status:
	@echo "=== DaskCluster ==="
	kubectl get daskclusters
	@echo ""
	@echo "=== Dask pods ==="
	kubectl get pods -l dask.org/cluster-name=$(DASK_CLUSTER) -o wide
	@echo ""
	@echo "=== Pipeline pods ==="
	kubectl get pods -l $(PIPELINE_APP_LABEL) -o wide
	@echo ""
	@echo "=== Services ==="
	kubectl get svc
	@echo ""
	@echo "=== Jobs ==="
	kubectl get jobs
	@echo ""
	@echo "=== PVC ==="
	kubectl get pvc

# ======================
# LOGS
# ======================

.PHONY: k8s-logs
k8s-logs:
	kubectl logs job/$(PIPELINE_JOB) -f

.PHONY: k8s-app-log
k8s-app-log:
	kubectl exec -it $(DASK_CLUSTER)-scheduler -- tail -f /mnt/dcp/logs/app.log

.PHONY: k8s-app-log-tail
k8s-app-log-tail:
	kubectl exec -it $(DASK_CLUSTER)-scheduler -- tail -n 200 /mnt/dcp/logs/app.log

.PHONY: k8s-clear-app-log
k8s-clear-app-log:
	@echo "Очистка /mnt/dcp/logs/app.log на scheduler pod..."
	kubectl exec -it $(DASK_CLUSTER)-scheduler -- sh -c '> /mnt/dcp/logs/app.log'

# ======================
# DEBUG / DIAGNOSTICS
# ======================

.PHONY: k8s-storage-check
k8s-storage-check:
	kubectl exec -it $(DASK_CLUSTER)-scheduler -- sh -c 'mkdir -p /mnt/dcp/data/source /mnt/dcp/data/processed /mnt/dcp/models /mnt/dcp/logs /mnt/dcp/notebooks && echo storage-ok > /mnt/dcp/storage_check.txt && cat /mnt/dcp/storage_check.txt'
	@echo "Теперь проверь worker вручную:"
	@echo "kubectl get pods -l dask.org/component=worker"
	@echo "kubectl exec -it <worker-pod-name> -- cat /mnt/dcp/storage_check.txt"

.PHONY: k8s-dashboard-forward
k8s-dashboard-forward:
	kubectl port-forward svc/$(DASK_CLUSTER)-service 8787:8787

.PHONY: k8s-scheduler-forward
k8s-scheduler-forward:
	kubectl port-forward svc/$(DASK_CLUSTER)-service 8786:8786 8787:8787

.PHONY: k8s-render-cluster
k8s-render-cluster:
	kubectl kustomize $(K8S_CLUSTER_DIR)

.PHONY: k8s-render-job
k8s-render-job:
	kubectl kustomize $(K8S_JOB_DIR)