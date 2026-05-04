# Distributed Churn Prediction

`distributed-churn-prediction` — учебно-инженерный ML/MLOps-проект для задачи предсказания оттока клиентов.

Проект показывает один и тот же ML workflow в трёх режимах выполнения:

```text
pandas
→ dask_local
→ dask_k8s
```

Цель — наглядно пройти путь от обычного локального пайплайна к распределённой системе: сначала всё выполняется на одной машине, затем через локальный Dask-кластер, затем через Dask scheduler/workers внутри Kubernetes.

---

## Коротко о проекте

Проект реализует полный ML pipeline:

1. проверка и загрузка исходного датасета;
2. feature engineering;
3. сохранение обработанных данных в Parquet;
4. обучение XGBoost-модели;
5. оценка модели;
6. сохранение модели, метрик, графиков и логов.

Источник данных:

```text
hamzaghanmi/expresso-churn-prediction-challenge
```

Основные рабочие интерфейсы сейчас — CLI и Web API:

```bash
python -m src.presentation.cli.main <command> --profile <profile>
```

```bash
python -m uvicorn src.presentation.api.app:app --host 127.0.0.1 --port 8000 --reload
```

---

## Навигация

- [Distributed Churn Prediction](#distributed-churn-prediction)
  - [Коротко о проекте](#коротко-о-проекте)
  - [Навигация](#навигация)
- [Быстрый старт](#быстрый-старт)
  - [1. Активировать окружение](#1-активировать-окружение)
  - [2. Проверить локальный `pandas`-режим](#2-проверить-локальный-pandas-режим)
  - [3. Проверить локальный `dask_local`-режим](#3-проверить-локальный-dask_local-режим)
  - [4. Запустить `dask_k8s` через GHCR image](#4-запустить-dask_k8s-через-ghcr-image)
  - [5. Запустить `dask_k8s` через локальный image в Minikube](#5-запустить-dask_k8s-через-локальный-image-в-minikube)
- [Установка с нуля](#установка-с-нуля)
  - [Системные инструменты](#системные-инструменты)
  - [Клонирование репозитория](#клонирование-репозитория)
- [Установка окружения](#установка-окружения)
  - [Linux / WSL](#linux--wsl)
  - [Windows](#windows)
  - [Проверка Python-зависимостей](#проверка-python-зависимостей)
  - [Основные библиотеки](#основные-библиотеки)
- [Runtime-профили](#runtime-профили)
  - [Зачем нужны все три режима](#зачем-нужны-все-три-режима)
- [CLI](#cli)
  - [Health-check](#health-check)
  - [Посмотреть итоговый конфиг](#посмотреть-итоговый-конфиг)
  - [Dry-run](#dry-run)
  - [Полный запуск](#полный-запуск)
  - [Skip-флаги](#skip-флаги)
- [Web API](#web-api)
  - [Запуск локально](#запуск-локально)
  - [Основные endpoints](#основные-endpoints)
  - [Запуск pipeline через run\_id](#запуск-pipeline-через-run_id)
- [Dask Kubernetes](#dask-kubernetes)
  - [Общая схема](#общая-схема)
  - [1. Запуск Minikube](#1-запуск-minikube)
  - [2. Установка Dask Operator](#2-установка-dask-operator)
  - [3. Проверить image](#3-проверить-image)
  - [4. Применить PVC](#4-применить-pvc)
  - [5. Запустить DaskCluster](#5-запустить-daskcluster)
  - [6. Запустить pipeline Job](#6-запустить-pipeline-job)
  - [7. Локальный fallback через Minikube image](#7-локальный-fallback-через-minikube-image)
- [Docker image и GitHub Container Registry](#docker-image-и-github-container-registry)
  - [Dockerfile](#dockerfile)
  - [GHCR](#ghcr)
  - [GitHub Actions](#github-actions)
- [Kubernetes manifests и overlays](#kubernetes-manifests-и-overlays)
  - [Структура](#структура)
  - [Base](#base)
  - [`ghcr` overlay](#ghcr-overlay)
  - [`minikube-local` overlay](#minikube-local-overlay)
  - [Проверить итоговые manifests](#проверить-итоговые-manifests)
- [Makefile](#makefile)
  - [Основные команды](#основные-команды)
  - [Выбор overlay](#выбор-overlay)
- [Логи и отладка](#логи-и-отладка)
  - [Job logs](#job-logs)
  - [Application log](#application-log)
  - [Dashboard](#dashboard)
  - [Scheduler port-forward](#scheduler-port-forward)
  - [PVC check](#pvc-check)
- [Конфигурация](#конфигурация)
  - [Kubernetes config](#kubernetes-config)
- [Данные и артефакты](#данные-и-артефакты)
  - [Локальные режимы](#локальные-режимы)
  - [Kubernetes-режим](#kubernetes-режим)
- [Структура проекта](#структура-проекта)
- [Архитектура приложения](#архитектура-приложения)
  - [`presentation`](#presentation)
  - [`application`](#application)
  - [`orchestration`](#orchestration)
  - [`infrastructure`](#infrastructure)
  - [`app`](#app)
- [Типовые проблемы](#типовые-проблемы)
  - [Pod долго висит в `ContainerCreating`](#pod-долго-висит-в-containercreating)
  - [`ImagePullBackOff` или `ErrImagePull`](#imagepullbackoff-или-errimagepull)
  - [`DaskCluster` не создаёт scheduler/workers](#daskcluster-не-создаёт-schedulerworkers)
  - [Job не может подключиться к scheduler](#job-не-может-подключиться-к-scheduler)
  - [PVC не монтируется](#pvc-не-монтируется)
  - [Kubernetes не видит локальный image](#kubernetes-не-видит-локальный-image)
- [Интерфейсы проекта](#интерфейсы-проекта)

---

# Быстрый старт

## 1. Активировать окружение

Linux / WSL:

```bash
conda activate dist-churn-pred-env
```

Windows:

```powershell
conda activate dist-churn-pred-env
```

Если окружение ещё не создано, см. раздел [Установка окружения](#установка-окружения).

---

## 2. Проверить локальный `pandas`-режим

```bash
python -m src.presentation.cli.main health --profile pandas
python -m src.presentation.cli.main run-pipeline --profile pandas --execute
```

---

## 3. Проверить локальный `dask_local`-режим

```bash
python -m src.presentation.cli.main health --profile dask_local
python -m src.presentation.cli.main run-pipeline --profile dask_local --execute
```

---

## 4. Запустить `dask_k8s` через GHCR image

Основной Kubernetes-вариант предполагает, что Docker image уже опубликован в GitHub Container Registry и доступен Kubernetes-кластеру.

```bash
make k8s-apply-storage
make k8s-recreate-cluster
make k8s-run-job
```

По умолчанию используется overlay:

```text
K8S_OVERLAY=ghcr
```

Он берёт image из GitHub Container Registry.

Перед первым запуском проверь, что Kubernetes может скачать image:

```bash
docker pull ghcr.io/skerter/distributed-churn-prediction:<release-tag>
```

Пример:

```bash
docker pull ghcr.io/skerter/distributed-churn-prediction:v0.1.0
```

Если image приватный и pull завершается ошибкой `unauthorized`, нужно либо сделать package публичным, либо настроить `imagePullSecret`.

---

## 5. Запустить `dask_k8s` через локальный image в Minikube

Это запасной режим для быстрой отладки, когда не хочется ждать сборку и публикацию image через GitHub Actions.

Важно: для локального Kubernetes-запуска недостаточно выполнить обычный `docker build` в Docker Desktop. Image должен быть доступен именно внутри Docker daemon Minikube.

Собрать image прямо внутрь Minikube:

```bash
make minikube-build
```

Эта команда выполняет примерно следующее:

```bash
eval $(minikube docker-env)
docker build -t dcp-pipeline:latest .
```

После этого можно запускать локальный overlay:

```bash
make k8s-apply-storage
make k8s-recreate-cluster K8S_OVERLAY=minikube-local
make k8s-run-job K8S_OVERLAY=minikube-local
```

Когда закончишь работу с Minikube Docker daemon и захочешь вернуть обычный Docker daemon:

```bash
eval $(minikube docker-env -u)
```

---

# Установка с нуля

Ниже описан полный набор инструментов, который нужен для всех режимов проекта.

## Системные инструменты

| Инструмент | Для чего нужен |
|---|---|
| Git | Клонирование репозитория и работа с ветками |
| Conda / Miniconda / Mambaforge | Python-окружение проекта |
| Docker Desktop / Docker Engine | Сборка и запуск container images |
| WSL Ubuntu | Linux-среда на Windows |
| Minikube | Локальный Kubernetes-кластер |
| kubectl | Управление Kubernetes |
| Helm 3 | Установка Kubernetes charts |
| make | Автоматизация команд проекта |
| curl, ca-certificates | Скачивание файлов и TLS |

Ubuntu / WSL:

```bash
sudo apt update
sudo apt install -y git make curl ca-certificates
```

Проверить инструменты:

```bash
git --version
make --version
docker --version
kubectl version --client
minikube version
helm version
```

---

## Клонирование репозитория

```bash
git clone https://github.com/Skerter/distributed-churn-prediction.git
cd distributed-churn-prediction
```

---

# Установка окружения

## Linux / WSL

```bash
conda env create -f environment_linux.yml
conda activate dist-churn-pred-env
```

## Windows

```powershell
conda env create -f environment.yml
conda activate dist-churn-pred-env
```

## Проверка Python-зависимостей

```bash
python -c "import pandas, dask, distributed, xgboost, pyarrow, kagglehub, coloredlogs; print('env ok')"
```

## Основные библиотеки

Полный список зависимостей находится в `environment.yml` и `environment_linux.yml`.

Ключевые библиотеки:

| Библиотека | Назначение |
|---|---|
| `pandas` | Локальная обработка данных |
| `dask` | Распределённые вычисления |
| `distributed` | Dask scheduler/client/workers |
| `dask-kubernetes` | Интеграция Dask и Kubernetes |
| `xgboost` | ML-модель и distributed training |
| `scikit-learn` | Метрики, split, вспомогательные ML-инструменты |
| `pyarrow` | Parquet |
| `kagglehub` | Загрузка Kaggle-датасета |
| `coloredlogs` | Цветное логирование |
| `pyyaml` | YAML-конфиги |
| `matplotlib`, `seaborn` | Графики |
| `kubernetes`, `kopf`, `kr8s` | Kubernetes tooling |

---

# Runtime-профили

Все три режима выполняют один и тот же смысловой pipeline: загрузка данных, обработка признаков, обучение и оценка модели. Разница в том, где и как выполняются вычисления.

| Профиль | Где выполняется | Что показывает |
|---|---|---|
| `pandas` | Один Python-процесс на одной машине | Базовая локальная реализация без распределённых вычислений |
| `dask_local` | Локальный Dask `LocalCluster` | Переход от обычного DataFrame к распределённой обработке на одной машине |
| `dask_k8s` | Dask scheduler/workers в Kubernetes + pipeline Job | Production-like подход: отдельные pod'ы, registry image, shared storage, Kubernetes orchestration |

## Зачем нужны все три режима

Проект специально сохраняет все режимы, чтобы было видно преимущество распределённой архитектуры.

`pandas` даёт простую точку отсчёта:

```text
один процесс
одна машина
простая отладка
минимум инфраструктуры
```

`dask_local` показывает первый шаг к распределённости:

```text
локальный scheduler
локальные workers
Dask DataFrame
распределённое обучение через xgboost.dask
```

`dask_k8s` показывает более зрелую схему:

```text
Docker image
GitHub Container Registry
Kubernetes DaskCluster
scheduler pod
worker pods
pipeline Job
PVC storage
```

Так можно сравнивать не только ML-качество, но и инженерные свойства:

- воспроизводимость;
- масштабируемость;
- изоляция окружения;
- управление ресурсами;
- удобство деплоя;
- переносимость между окружениями.

---

# CLI

CLI поддерживает три команды:

```text
health
show-config
run-pipeline
```

## Health-check

```bash
python -m src.presentation.cli.main health --profile pandas
python -m src.presentation.cli.main health --profile dask_local
python -m src.presentation.cli.main health --profile dask_k8s
```

Для `dask_k8s` health-check требует доступный Dask scheduler, потому что профиль подключается к внешнему scheduler по адресу из конфига.

## Посмотреть итоговый конфиг

```bash
python -m src.presentation.cli.main show-config --profile pandas
python -m src.presentation.cli.main show-config --profile dask_local
python -m src.presentation.cli.main show-config --profile dask_k8s
```

## Dry-run

```bash
python -m src.presentation.cli.main run-pipeline --profile pandas
python -m src.presentation.cli.main run-pipeline --profile dask_local
```

Для `dask_k8s` dry-run может попытаться подключиться к scheduler на этапе bootstrap, поэтому для проверки без Kubernetes лучше использовать `pandas` или `dask_local`.

## Полный запуск

```bash
python -m src.presentation.cli.main run-pipeline --profile pandas --execute
python -m src.presentation.cli.main run-pipeline --profile dask_local --execute
```

Kubernetes-режим обычно запускается через Kubernetes Job:

```bash
make k8s-run-job
```

## Skip-флаги

```bash
python -m src.presentation.cli.main run-pipeline --profile pandas --execute --skip-load
python -m src.presentation.cli.main run-pipeline --profile pandas --execute --skip-features
python -m src.presentation.cli.main run-pipeline --profile pandas --execute --skip-train
python -m src.presentation.cli.main run-pipeline --profile pandas --execute --skip-eval
```

Пример комбинированного запуска:

```bash
python -m src.presentation.cli.main run-pipeline \
  --profile dask_local \
  --execute \
  --skip-load \
  --skip-features
```

---

# Web API

API — это тонкий presentation layer над тем же core, что и CLI:

```text
HTTP request
→ FastAPI route
→ AppContainer
→ use case
→ pipeline executor
```

Активный runtime-профиль выбирается через переменную окружения `DCP_PROFILE`.

## Запуск локально

Windows cmd:

```cmd
cd C:\vs_code_projects\distributed-churn-prediction
conda activate dist-churn-pred-env
set DCP_PROFILE=pandas
python -m uvicorn src.presentation.api.app:app --host 127.0.0.1 --port 8000 --reload
```

PowerShell:

```powershell
cd C:\vs_code_projects\distributed-churn-prediction
conda activate dist-churn-pred-env
$env:DCP_PROFILE="pandas"
python -m uvicorn src.presentation.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Основные endpoints

| Endpoint | Метод | Назначение |
|---|---:|---|
| `/health` | GET | Проверить состояние приложения |
| `/profiles` | GET | Посмотреть доступные runtime-профили |
| `/config/summary` | GET | Посмотреть безопасную сводку конфигурации |
| `/model/info` | GET | Проверить наличие модели и метрик |
| `/pipeline/runs` | POST | Создать запуск pipeline и получить `run_id` |
| `/pipeline/runs/{run_id}` | GET | Проверить состояние запуска |

## Запуск pipeline через run_id

В Web API pipeline запускается не через долгий блокирующий HTTP-запрос, а через `run_id`.

Схема:

```text
POST /pipeline/runs
→ API создаёт run_id
→ pipeline запускается в background executor
→ GET /pipeline/runs/{run_id} показывает статус
```

Создать dry-run через Swagger UI:

```json
{
  "execute": false,
  "skip_load": false,
  "skip_features": false,
  "skip_train": false,
  "skip_eval": false
}
```

Создать реальный запуск:

```json
{
  "execute": true,
  "skip_load": false,
  "skip_features": false,
  "skip_train": false,
  "skip_eval": false
}
```

Ответ содержит `run_id`:

```json
{
  "run_id": "20260504-153012-pandas-a1b2c3d4",
  "status": "queued",
  "profile": "pandas",
  "executor": "web"
}
```

Проверить статус:

```text
http://127.0.0.1:8000/pipeline/runs/<run_id>
```

Файлы состояния запусков сохраняются в:

```text
logs/pipeline_runs
```

Типовые статусы:

| Статус | Значение |
|---|---|
| `queued` | Запуск создан |
| `running` | Pipeline выполняется |
| `succeeded` | Pipeline завершился успешно |
| `failed` | Pipeline завершился ошибкой |

---

# Dask Kubernetes

## Общая схема

```text
Docker image
→ GitHub Container Registry
→ Kubernetes
→ Dask Operator
→ DaskCluster
→ scheduler pod
→ worker pods
→ scheduler service
→ pipeline Job
→ shared PVC /mnt/dcp
```

В Kubernetes участвуют следующие сущности:

| Сущность | Назначение |
|---|---|
| `DaskCluster` | Custom Resource, описывающий Dask scheduler и workers |
| Dask Operator | Следит за `DaskCluster` и создаёт реальные Kubernetes pod'ы/service |
| Scheduler pod | Центральный Dask scheduler |
| Worker pods | Исполнители Dask-задач |
| Scheduler service | Kubernetes service для подключения Job/client к scheduler |
| PVC `dcp-storage` | Общее хранилище данных, моделей и логов |
| Pipeline Job | Одноразовый запуск ML pipeline внутри Kubernetes |

---

## 1. Запуск Minikube

Рекомендуемый старт:

```bash
minikube start --driver=docker --cpus=4 --memory=8192
```

Проверка:

```bash
minikube status
kubectl get nodes
kubectl get pods
```

---

## 2. Установка Dask Operator

Dask Operator нужен, чтобы Kubernetes понимал ресурс:

```yaml
kind: DaskCluster
```

Без Dask Operator команда `kubectl apply` для `DaskCluster` не создаст scheduler/workers.

Стандартный путь установки Dask Operator — через Helm chart `dask-kubernetes-operator`.

Добавить Helm repo:

```bash
helm repo add dask https://helm.dask.org
helm repo update
```

Установить operator:

```bash
helm install dask-operator dask/dask-kubernetes-operator
```

Проверить установку:

```bash
kubectl get pods | grep -i dask
kubectl get crd | grep -i dask
kubectl api-resources | grep -i dask
kubectl explain daskcluster
```

Ожидается, что в кластере появились:

```text
DaskCluster CRD
RBAC permissions
ServiceAccount
Dask Operator Deployment
Dask Operator Pod
```

Проверка operator pod:

```bash
kubectl get pods
kubectl logs deployment/dask-operator --tail=200
```

Если `deployment/dask-operator` не найден, посмотри точное имя deployment:

```bash
kubectl get deploy
```

---

## 3. Проверить image

Основной Kubernetes-режим рассчитан на image из GHCR.

Проверить pull:

```bash
docker pull ghcr.io/skerter/distributed-churn-prediction:<release-tag>
```

Пример:

```bash
docker pull ghcr.io/skerter/distributed-churn-prediction:v0.1.0
```

Если package публичный, Kubernetes сможет скачать image без `imagePullSecret`.

Если package приватный, нужно создать secret:

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<github_username> \
  --docker-password=<github_pat> \
  --docker-email=<email>
```

После этого secret нужно добавить в pod spec scheduler/workers/job через `imagePullSecrets`.

---

## 4. Применить PVC

```bash
make k8s-apply-storage
```

Вручную:

```bash
kubectl apply -f k8s/base/cluster/pvc.yaml
kubectl get pvc
```

Ожидаемый статус:

```text
dcp-storage   Bound
```

---

## 5. Запустить DaskCluster

Основной GHCR-режим:

```bash
make k8s-recreate-cluster
```

Вручную:

```bash
kubectl delete daskcluster dcp-cluster --ignore-not-found=true
kubectl apply -k k8s/overlays/ghcr/cluster
kubectl get pods -l dask.org/cluster-name=dcp-cluster -w
```

Ожидаемые pod'ы:

```text
dcp-cluster-scheduler                                1/1 Running
dcp-cluster-default-worker-group-worker-...          1/1 Running
dcp-cluster-default-worker-group-worker-...          1/1 Running
```

Первый pull image может занимать несколько минут. Это нормально для тяжёлого Python/conda image.

---

## 6. Запустить pipeline Job

```bash
make k8s-run-job
```

Вручную:

```bash
kubectl delete job dcp-pipeline-job --ignore-not-found=true
kubectl apply -k k8s/overlays/ghcr/job
kubectl logs job/dcp-pipeline-job -f
```

Job запускает:

```bash
python -m src.presentation.cli.main run-pipeline --profile dask_k8s --execute
```

---

## 7. Локальный fallback через Minikube image

Если нужно быстро проверить локальные изменения без GHCR:

```bash
make minikube-build
make k8s-recreate-cluster K8S_OVERLAY=minikube-local
make k8s-run-job K8S_OVERLAY=minikube-local
```

Что важно:

```text
make minikube-build
```

собирает image именно внутри Docker daemon Minikube. Если собрать image обычным `docker build` без `eval $(minikube docker-env)`, Kubernetes внутри Minikube может его не увидеть.
Загрузка образа из обычного Docker в Docker daemon Minikube очень долгая, не рекомендуется. 

Проверить image внутри Minikube:

```bash
eval $(minikube docker-env)
docker images | grep dcp-pipeline
```

Вернуться к обычному Docker daemon:

```bash
eval $(minikube docker-env -u)
```

---

# Docker image и GitHub Container Registry

## Dockerfile

`Dockerfile` описывает runtime image проекта.

Внутри image:

```text
/app/src
/app/configs
conda env: dist-churn-pred-env
PYTHONPATH=/app
```

Один и тот же image используется для:

```text
Dask scheduler
Dask workers
pipeline Job
```

Это важно: scheduler, workers и pipeline Job должны иметь одинаковые версии `dask`, `distributed`, `xgboost`, `pandas`, `pyarrow` и проектного кода.

---

## GHCR

Docker images публикуются в GitHub Container Registry:

```text
ghcr.io/skerter/distributed-churn-prediction
```

Для стабильных запусков рекомендуется использовать release-tag:

```text
ghcr.io/skerter/distributed-churn-prediction:v0.1.0
```

Именно release-tag должен использоваться в Kubernetes manifests, когда нужна воспроизводимость.

## GitHub Actions

Workflow:

```text
.github/workflows/docker-ghcr.yml
```

Он автоматизирует сборку и публикацию image.

Общая логика:

```text
push / manual workflow run
→ checkout
→ docker login ghcr.io
→ docker build
→ smoke test
→ docker push
```

Для обычного рабочего запуска Kubernetes должен ссылаться на заранее выбранный release-tag. Если release-tag меняется, обнови image в GHCR overlay.

---

# Kubernetes manifests и overlays

Проект использует Kustomize. Он встроен в `kubectl`, поэтому отдельная установка обычно не нужна.

## Структура

```text
k8s/
├── base/
│   ├── cluster/
│   │   ├── dask-cluster.yaml
│   │   ├── pvc.yaml
│   │   └── kustomization.yaml
│   └── job/
│       ├── pipeline-job.yaml
│       └── kustomization.yaml
└── overlays/
    ├── ghcr/
    │   ├── cluster/
    │   │   └── kustomization.yaml
    │   └── job/
    │       └── kustomization.yaml
    └── minikube-local/
        ├── cluster/
        │   └── kustomization.yaml
        └── job/
            └── kustomization.yaml
```

## Base

Base содержит общий Kubernetes spec:

```text
PVC
DaskCluster
Pipeline Job
volumeMounts
ports
args
service
```

В base используется placeholder-image:

```yaml
image: dcp-pipeline:base
imagePullPolicy: IfNotPresent
```

Base напрямую обычно не запускается. Конкретный image выбирает overlay.

## `ghcr` overlay

Используется для запуска из registry.

```bash
kubectl apply -k k8s/overlays/ghcr/cluster
kubectl apply -k k8s/overlays/ghcr/job
```

## `minikube-local` overlay

Используется для локального image:

```bash
kubectl apply -k k8s/overlays/minikube-local/cluster
kubectl apply -k k8s/overlays/minikube-local/job
```

Перед этим нужно выполнить:

```bash
make minikube-build
```

## Проверить итоговые manifests

GHCR:

```bash
make k8s-render-cluster
make k8s-render-job
```

Локальный fallback:

```bash
make k8s-render-cluster K8S_OVERLAY=minikube-local
make k8s-render-job K8S_OVERLAY=minikube-local
```

---

# Makefile

`Makefile` — основной интерфейс для повторяющихся команд.

## Основные команды

| Команда | Что делает |
|---|---|
| `make minikube-build` | Собирает `dcp-pipeline:latest` внутри Minikube Docker daemon |
| `make local-build` | Собирает image в текущем Docker daemon |
| `make k8s-apply-storage` | Применяет PVC |
| `make k8s-recreate-cluster` | Пересоздаёт DaskCluster через выбранный overlay |
| `make k8s-run-job` | Перезапускает pipeline Job через выбранный overlay |
| `make k8s-clean-job` | Удаляет pipeline Job |
| `make k8s-status` | Показывает состояние DaskCluster, pods, services, jobs, PVC |
| `make k8s-render-cluster` | Показывает итоговый cluster manifest после Kustomize |
| `make k8s-render-job` | Показывает итоговый job manifest после Kustomize |

## Выбор overlay

Основной режим:

```bash
make k8s-recreate-cluster
make k8s-run-job
```

Локальный fallback:

```bash
make minikube-build
make k8s-recreate-cluster K8S_OVERLAY=minikube-local
make k8s-run-job K8S_OVERLAY=minikube-local
```

---

# Логи и отладка

## Job logs

Основная команда для просмотра stdout pipeline Job:

```bash
make k8s-logs
```

Вручную:

```bash
kubectl logs job/dcp-pipeline-job -f
```

## Application log

Основной файловый лог внутри Kubernetes:

```text
/mnt/dcp/logs/app.log
```

Команды:

```bash
make k8s-app-log-tail
make k8s-app-log
make k8s-clear-app-log
```

`k8s-app-log-tail` показывает последние строки, `k8s-app-log` следит за логом в live-режиме, `k8s-clear-app-log` очищает файл.

## Dashboard

```bash
make k8s-dashboard-forward
```

Открыть:

```text
http://localhost:8787
```

## Scheduler port-forward

```bash
make k8s-scheduler-forward
```

После этого локальный клиент может подключиться к:

```text
tcp://localhost:8786
```

## PVC check

```bash
make k8s-storage-check
```

Эта команда создаёт тестовый файл в `/mnt/dcp` через scheduler pod. Затем можно проверить его из worker pod.

---

# Конфигурация

Базовый конфиг:

```text
configs/base.yaml
```

Профильные конфиги:

```text
configs/pandas.yaml
configs/dask_local.yaml
configs/dask_k8s.yaml
```

## Kubernetes config

`configs/dask_k8s.yaml` использует абсолютные пути внутри pod'ов:

```yaml
paths:
  data_source: "/mnt/dcp/data/source"
  data_processed: "/mnt/dcp/data/processed"
  models: "/mnt/dcp/models"
  logs: "/mnt/dcp/logs"
  notebooks: "/mnt/dcp/notebooks"

dask:
  scheduler_address: "tcp://dcp-cluster-service:8786"
```

Внутри Kubernetes нельзя использовать:

```text
tcp://localhost:8786
```

Потому что `localhost` внутри Job pod означает сам Job pod, а не Dask scheduler.

---

# Данные и артефакты

## Локальные режимы

Обычно артефакты пишутся в:

```text
data/source
data/processed
models
logs
notebooks
```

## Kubernetes-режим

Артефакты пишутся в PVC:

```text
/mnt/dcp/data/source
/mnt/dcp/data/processed
/mnt/dcp/models
/mnt/dcp/logs
/mnt/dcp/notebooks
```

Это позволяет pipeline Job, scheduler и workers видеть одни и те же данные.

---

# Структура проекта

```text
distributed-churn-prediction/
├── configs/
│   ├── base.yaml
│   ├── pandas.yaml
│   ├── dask_local.yaml
│   └── dask_k8s.yaml
├── k8s/
│   ├── base/
│   │   ├── cluster/
│   │   └── job/
│   ├── overlays/
│   │   ├── ghcr/
│   │   └── minikube-local/
│   └── operator/
├── src/
│   ├── app/
│   ├── application/
│   ├── infrastructure/
│   ├── orchestration/
│   └── presentation/
├── Dockerfile
├── Makefile
├── environment.yml
├── environment_linux.yml
└── README.md
```

---

# Архитектура приложения

Проект использует layered architecture.

```text
presentation
→ application
→ orchestration
→ infrastructure
→ app/bootstrap
```

## `presentation`

Точки входа в приложение:

```text
src/presentation/cli
src/presentation/api
```

CLI:

1. читает аргументы;
2. вызывает bootstrap;
3. запускает use case;
4. печатает JSON-ответ.

Web API:

1. принимает HTTP-запрос;
2. использует `AppContainer`, созданный при старте приложения;
3. вызывает application use cases;
4. возвращает JSON-ответ.

Для запуска pipeline в Web API используется workflow с `run_id`: API создаёт запуск, возвращает идентификатор, а состояние проверяется отдельным GET-запросом.

## `application`

Прикладной слой:

```text
src/application
```

Содержит:

- DTO;
- use cases;
- services для dataset, features, train, evaluate.

## `orchestration`

Слой pipeline-сценариев:

```text
src/orchestration/pipelines
```

Содержит:

- pandas pipeline;
- dask local pipeline;
- dask k8s pipeline.

## `infrastructure`

Технический слой:

- загрузка конфигов;
- Dask client;
- логирование;
- storage/path utils.

## `app`

Композиционный слой:

- `bootstrap()`;
- container;
- typed settings.

---

# Типовые проблемы

## Pod долго висит в `ContainerCreating`

Посмотреть events:

```bash
kubectl describe pod dcp-cluster-scheduler
```

Если видно только:

```text
Pulling image ...
```

и ошибок нет, image просто скачивается. Первый pull может занимать несколько минут.

## `ImagePullBackOff` или `ErrImagePull`

Проверить pull:

```bash
docker pull ghcr.io/skerter/distributed-churn-prediction:<release-tag>
```

Если ошибка `unauthorized`, image приватный. Сделай package public или настрой `imagePullSecret`.

## `DaskCluster` не создаёт scheduler/workers

Проверить operator:

```bash
kubectl get crd | grep -i dask
kubectl get pods | grep -i operator
kubectl logs deployment/dask-operator --tail=200
```

Проверить events:

```bash
kubectl describe daskcluster dcp-cluster
kubectl get events --sort-by='.lastTimestamp' | tail -50
```

## Job не может подключиться к scheduler

Проверь `configs/dask_k8s.yaml`:

```yaml
dask:
  scheduler_address: "tcp://dcp-cluster-service:8786"
```

Если там `localhost`, Job будет пытаться подключиться к самому себе.

## PVC не монтируется

Проверить PVC:

```bash
kubectl get pvc
kubectl describe pvc dcp-storage
```

Ожидается:

```text
Bound
```

## Kubernetes не видит локальный image

Если используешь `K8S_OVERLAY=minikube-local`, image должен быть собран внутри Minikube:

```bash
make minikube-build
```

Проверка:

```bash
eval $(minikube docker-env)
docker images | grep dcp-pipeline
```

---

# Интерфейсы проекта

Сейчас в проекте есть несколько интерфейсных направлений:

| Интерфейс | Статус | Назначение |
|---|---|---|
| CLI | Реализован | Локальный запуск и отладка pipeline |
| Web API | Реализован | HTTP-интерфейс для health-check, конфигурации, модели и запуска pipeline через `run_id` |
| Telegram Bot | Планируется | Пользовательский интерфейс поверх application layer |

CLI и Web API используют один и тот же core: `bootstrap`, `AppContainer`, application use cases и pipeline'ы.
