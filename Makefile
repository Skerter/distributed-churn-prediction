SHELL := /bin/bash

APP_NAME := distributed-churn-prediction
LOCAL_IMAGE := dcp-pipeline
LOCAL_TAG := latest
LOCAL_IMAGE_REF := $(LOCAL_IMAGE):$(LOCAL_TAG)

GHCR_OWNER := skerter
GHCR_IMAGE := ghcr.io/$(GHCR_OWNER)/$(APP_NAME)
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
GHCR_TAG ?= $(GIT_SHA)
GHCR_IMAGE_REF := $(GHCR_IMAGE):$(GHCR_TAG)

K8S_DIR := k8s/base
DASK_CLUSTER := dcp-cluster
PIPELINE_JOB := dcp-pipeline-job
PIPELINE_APP_LABEL := app=dcp-pipeline

.PHONY: help
help:
	@echo "Доступные команды:"
	@echo "  make minikube-build          Собрать local image внутри Docker daemon Minikube"
	@echo "  make local-build             Собрать image в текущем Docker daemon"
	@echo "  make k8s-apply-storage       Применить PVC"
	@echo "  make k8s-recreate-cluster    Пересоздать DaskCluster"
	@echo "  make k8s-status              Показать pods/services/jobs/pvc"
	@echo "  make k8s-run-job             Перезапустить pipeline Job"
	@echo "  make k8s-logs                Смотреть stdout logs pipeline Job"
	@echo "  make k8s-app-log             Смотреть /mnt/dcp/logs/app.log через scheduler pod"
	@echo "  make k8s-clean-job           Удалить pipeline Job"
	@echo "  make k8s-clear-app-log       Очистить /mnt/dcp/logs/app.log на scheduler pod"
	@echo "  make ghcr-build              Собрать image с GHCR-тегом локально"
	@echo "  make ghcr-push               Push image в GHCR"
	@echo ""
	@echo "Переменные:"
	@echo "  GHCR_TAG=<tag>               Тег для GHCR image, по умолчанию git short sha"

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

.PHONY: k8s-apply-storage
k8s-apply-storage:
	kubectl apply -f $(K8S_DIR)/pvc.yaml
	kubectl get pvc

.PHONY: k8s-recreate-cluster
k8s-recreate-cluster:
	@echo "Пересоздание DaskCluster $(DASK_CLUSTER)..."
	kubectl delete daskcluster $(DASK_CLUSTER) --ignore-not-found=true
	kubectl apply -f $(K8S_DIR)/dask-cluster.yaml
	kubectl get pods -l dask.org/cluster-name=$(DASK_CLUSTER) -w

.PHONY: k8s-status
k8s-status:
	@echo "=== DaskCluster ==="
	kubectl get daskclusters
	@echo ""
	@echo "=== Pods ==="
	kubectl get pods
	@echo ""
	@echo "=== Services ==="
	kubectl get svc
	@echo ""
	@echo "=== Jobs ==="
	kubectl get jobs
	@echo ""
	@echo "=== PVC ==="
	kubectl get pvc

.PHONY: k8s-run-job
k8s-run-job:
	@echo "Перезапуск pipeline Job..."
	kubectl delete job $(PIPELINE_JOB) --ignore-not-found=true
	kubectl apply -f $(K8S_DIR)/pipeline-job.yaml
	kubectl logs job/$(PIPELINE_JOB) -f

.PHONY: k8s-clean-job
k8s-clean-job:
	@echo "Удаление pipeline Job..."
	kubectl delete job $(PIPELINE_JOB) --ignore-not-found=true

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