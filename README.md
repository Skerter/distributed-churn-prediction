# Distributed Churn Prediction

![Tests](https://github.com/Skerter/distributed-churn-prediction/actions/workflows/tests.yml/badge.svg)
![Build](https://github.com/Skerter/distributed-churn-prediction/actions/workflows/build.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

`distributed-churn-prediction` — учебно-инженерный ML/MLOps-проект для задачи предсказания оттока клиентов.

Проект показывает один и тот же ML workflow в трёх режимах выполнения:

```text
pandas
dask_local
dask_k8s
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

Четыре рабочих интерфейса поверх одного core:

| Интерфейс | Назначение |
|---|---|
| CLI | Локальный запуск и отладка pipeline |
| Web API | HTTP-интерфейс: health-check, конфигурация, модель, запуск pipeline через `run_id` |
| [Frontend Dashboard](https://dcp.135.106.161.48.nip.io/) | Статический веб-дашборд поверх Web API: запуск пайплайна, мониторинг, история, статистика |
| Telegram Bot | Push-driven интерфейс для запуска и мониторинга pipeline из чата (на РФ-проде отключён — см. ниже) |

>**Live demo:** [churn.skerter.dev](https://churn.skerter.dev) (Selectel VDS за общим Traefik)
>
>API: [api.churn.skerter.dev](https://api.churn.skerter.dev/docs)
>
>MLflow UI: [mlflow.churn.skerter.dev](https://mlflow.churn.skerter.dev)
>
> Бот в Telegram на текущем VDS **отключён** (`api.telegram.org` недоступен с датацентра в РФ).

Дополнительно:

- **MLflow tracking** — параметры и метрики каждого обучения логируются в эксперимент `churn-prediction`
- **Pytest** — smoke / unit / integration тесты с маркерами для быстрых проверок

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
  - [Pip (альтернатива conda)](#pip-альтернатива-conda)
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
- [Frontend Dashboard](#frontend-dashboard)
  - [Возможности](#возможности)
  - [Запуск локально](#запуск-локально-1)
- [Telegram Bot](#telegram-bot)
  - [Команды](#команды)
  - [Жизненный цикл pipeline run](#жизненный-цикл-pipeline-run)
  - [Настройки бота](#настройки-бота)
- [Тесты](#тесты)
  - [Структура тестов](#структура-тестов)
  - [Маркеры pytest](#маркеры-pytest)
  - [Запуск тестов](#запуск-тестов)
- [MLflow Tracking](#mlflow-tracking)
  - [Что логируется](#что-логируется)
  - [MLflow UI локально](#mlflow-ui-локально)
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
- [Live Demo на Selectel VDS (docker compose + Traefik)](#live-demo-на-selectel-vds-docker-compose--traefik)
  - [Состав стека](#состав-стека)
  - [Развёртывание](#развёртывание)
  - [Важные нюансы (грабли, на которые уже наступили)](#важные-нюансы-грабли-на-которые-уже-наступили)
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
docker pull ghcr.io/skerter/distributed-churn-prediction:v0.4.0
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
conda env create -f docker/environment.linux.yml
conda activate dist-churn-pred-env
```

## Windows

```powershell
conda env create -f environment.windows.yml
conda activate dist-churn-pred-env
```

## Pip (альтернатива conda)

Если conda недоступна, прямые зависимости можно поставить через pip:

```bash
python -m venv .venv
source .venv/bin/activate          # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` содержит только прямые зависимости приложения (без Jupyter и dev-инструментов) и синхронизирован с pinned-версиями из `docker/environment.linux.yml`. Для разработки и работы с notebook'ами рекомендуется conda — она ставит полный набор инструментов и аккуратнее решает конфликты бинарных wheel'ов для `xgboost`, `pyarrow` и MKL-backed `numpy`.

## Основные библиотеки

Полный список зависимостей находится в `environment.windows.yml` (Windows) и `docker/environment.linux.yml` (Linux/Docker).

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
FastAPI route
AppContainer
use case
pipeline executor
```

Активный runtime-профиль выбирается через переменную окружения `DCP_PROFILE`.

## Запуск локально

Windows cmd:

```cmd
cd C:\vs_code_projects\distributed-churn-prediction
conda activate dist-churn-pred-env
set DCP_PROFILE=pandas
python -m uvicorn src.presentation.web.app:app --host 127.0.0.1 --port 8000 --reload
```

PowerShell:

```powershell
cd C:\vs_code_projects\distributed-churn-prediction
conda activate dist-churn-pred-env
$env:DCP_PROFILE="pandas"
python -m uvicorn src.presentation.web.app:app --host 127.0.0.1 --port 8000 --reload
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

# Frontend Dashboard

> 🌐 **Live:** [https://churn.skerter.dev](https://churn.skerter.dev) (Selectel VDS)

`frontend/` — статический веб-дашборд для управления Web API из браузера. Чистый HTML/CSS/Vanilla JS, без сборщиков и npm-зависимостей.

Дашборд — это удобная альтернатива Swagger UI и curl-командам: запустил один сервер с фронтом, открыл вкладку в браузере — и управляешь пайплайном кликами.

## Возможности

| Блок | Назначение |
|---|---|
| Health Check | Проверка статуса API одной кнопкой, индикатор подключения в шапке |
| Запуск ML Pipeline | Запуск с чекбоксами `execute`, `skip_load`, `skip_features`, `skip_train`, `skip_eval` и пресетами (Полный прогон / Только обучение / Dry-run / Сброс) |
| Статус пайплайна | Мониторинг текущего запуска по `run_id`: бейдж статуса, прогресс-бар по этапам (Loading → Features → Training → Eval → Done), таймер длительности, автополлинг каждые 3 секунды |
| История запусков | Последние 10 пайплайнов текущей сессии — сохраняется в `localStorage`, переживает перезагрузку страницы |
| Статистика | Живые счётчики: всего запусков, успешные, ошибки, среднее время выполнения |
| Темы | Светлая / тёмная тема с автоопределением системной и сохранением выбора |
| Горячие клавиши | `H` — health, `R` — run, `S` — status, `T` — тема, `C` — копировать `run_id`, `?` — подсказка в консоли |
| Уведомления | Toast-сообщения об успехе/ошибке запросов в правом нижнем углу |

## Запуск локально

Сначала подними Web API (см. раздел [Web API](#web-api)), затем запусти статический сервер для фронтенда:

```bash
python -m http.server 3000 --directory frontend
```

Открой в браузере:

```text
http://localhost:3000
```

Альтернативно — расширение **Live Server** для VS Code (правый клик по `frontend/index.html` → *Open with Live Server*).

По умолчанию фронтенд обращается к `http://127.0.0.1:8000`. Текущий API-URL виден в шапке справа.

---

# Telegram Bot

> 💬 **Бот в Telegram:** [@dcp_pipeline_bot](https://t.me/dcp_pipeline_bot)
>
> ⚠️ На текущем РФ-VDS (Selectel) бот **отключён** (`profiles: ["bot"]` в `deploy/selectel/compose.yaml`): `api.telegram.org` недоступен.

Telegram-бот — третий presentation layer над тем же core, что и CLI/Web API. Бот работает в режиме long-polling и общается с приложением через `AppContainer`:

```text
Telegram update
aiogram Router / FSM
AppContainer
use case
pipeline executor
```

В отличие от Web API, бот не блокируется на ответе: pipeline запускается в отдельном треде, а пользователь получает push-уведомление после завершения. Это естественная модель для долгих запусков (`dask_k8s` может идти десятки минут) и не требует от клиента поллить статус вручную.

## Команды

| Команда | Назначение |
|---|---|
| `/start`, `/help` | Приветствие и список доступных команд |
| `/health` | Состояние приложения: имя, версия, профиль |
| `/profiles` | Список runtime-профилей с пометкой профиля по умолчанию |
| `/run` | Запуск pipeline с выбором профиля через inline-клавиатуру |
| `/stop` | Остановка активного pipeline run |
| `/status` | Интерактивный диалог: спрашивает `run_id` и возвращает payload |
| `/model` | Метаданные модели и метрики последнего запуска |
| `/cancel` | Выход из текущего FSM-диалога |

## Жизненный цикл pipeline run

После нажатия кнопки в `/run` бот запускает pipeline в отдельном треде и сразу возвращает `run_id`:

```text
/run -> выбор профиля
BotPipelineExecutor.submit()
pipeline thread started
ответ боту: run_id
watch_and_notify (async background task)
push-уведомление по завершению
```

Статусы переходов идентичны Web API: `queued → running → succeeded | failed`. Файлы запусков лежат в общем `logs/pipeline_runs`, поэтому `/status` доступен по любому `run_id` — в том числе по другим запускам, инициированным через CLI или HTTP.

Если pipeline не успевает завершиться за `bot.pipeline_timeout_seconds`, `watch_and_notify` выставляет `cancel_event`, помечает run как FAILED и присылает уведомление о таймауте. Команда `/stop` использует тот же механизм, но по инициативе пользователя — благодаря тому, что `BotPipelineExecutor` живёт всё время работы бота и хранит реестр `cancel_event` по `run_id`.

При старте бот вызывает `_recover_stale_runs`: все запуски, оставшиеся в статусе `queued/running` после рестарта процесса, помечаются FAILED — чтобы не зависели от треда из предыдущего процесса.

## Настройки бота

Параметры лежат в `configs/base.yaml`:

```yaml
bot:
  admin_chat_ids: []
  pipeline_timeout_seconds: 7200
```

| Поле | Значение |
|---|---|
| `admin_chat_ids` | Список разрешённых Telegram `user_id`. Пустой список — доступ открыт всем. Непустой — `AuthMiddleware` отклоняет чужих пользователей и пишет WARNING в лог |
| `pipeline_timeout_seconds` | Жёсткий лимит на один pipeline run в секундах. По умолчанию 7200 (2 часа) |

---

# Тесты

Проект использует `pytest`. Тесты разделены по слоям и помечены маркерами — это позволяет запускать только нужное подмножество (например, быстрые smoke-тесты перед коммитом).

Тесты также запускаются автоматически в CI (`.github/workflows/tests.yml`) на каждый push и pull request в `main`.

## Структура тестов

```text
tests/
├── smoke/         # быстрые проверки импортов и сборки модулей
├── unit/          # изолированные тесты Settings, AppContainer
└── integration/   # интеграционные проверки сборки pipeline-модулей
```

## Маркеры pytest

| Маркер | Что покрывает |
|---|---|
| `smoke` | Минимальные проверки, что приложение собирается и ключевые модули импортируются |
| `unit` | Изолированные тесты компонентов (`Settings`, `AppContainer`) с подставленными зависимостями |
| `integration` | Проверки, требующие нескольких слоёв вместе (например, импорт pipeline-сценария) |

## Запуск тестов

Все тесты:

```bash
pytest
```

Только быстрые smoke-тесты:

```bash
pytest -m smoke
```

Только unit или integration:

```bash
pytest -m unit
pytest -m integration
```

Конкретный файл или тест:

```bash
pytest tests/unit/test_settings_unit.py
pytest tests/unit/test_settings_unit.py::test_settings_creation
```

Конфиг лежит в `pyproject.toml` (секция `[tool.pytest.ini_options]`) — корень проекта уже добавлен в `pythonpath`, поэтому импорты вида `from src.app...` работают из коробки.

---

# MLflow Tracking

Проект логирует параметры обучения и метрики через **MLflow**. Логирование встроено в `train_service` и работает в обоих локальных режимах (`pandas` и `dask_local`). Если MLflow по какой-то причине недоступен, pipeline не падает — пишется WARNING в лог.

## Что логируется

Все запуски пишутся в эксперимент `churn-prediction`. Для каждого запуска:

**Параметры:**

- `runtime_mode` — `pandas` или `dask_local`
- `model_name`, `model_version`
- XGBoost-гиперпараметры: `objective`, `eval_metric`, `max_depth`, `learning_rate`, `n_estimators`, `subsample`, `colsample_bytree`, `random_state`, `n_jobs`

**Метрики:**

- `train_rows`, `val_rows` — размеры выборок
- `train_target_rate`, `val_target_rate` — доля положительного класса
- `best_iteration` — лучшая итерация бустинга (если доступна)

Это позволяет сравнивать запуски между runtime-профилями, отслеживать влияние гиперпараметров и не терять историю экспериментов.

## MLflow UI локально

По умолчанию runs пишутся в `mlflow/mlruns/`. Открыть веб-интерфейс с фильтрами, графиками и сравнением запусков:

```bash
mlflow ui --backend-store-uri ./mlflow/mlruns --port 5000
```

Открой в браузере:

```text
http://127.0.0.1:5000
```

---

# Dask Kubernetes

## Общая схема

```text
Docker image
GitHub Container Registry
Kubernetes
Dask Operator
DaskCluster
scheduler pod
worker pods
scheduler service
pipeline Job
shared PVC /mnt/dcp
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
docker pull ghcr.io/skerter/distributed-churn-prediction:v0.4.0
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
ghcr.io/skerter/distributed-churn-prediction:v0.4.0
```

Именно release-tag должен использоваться в Kubernetes manifests, когда нужна воспроизводимость.

## GitHub Actions

Проект использует два workflow:

```text
.github/workflows/build.yml
.github/workflows/tests.yml
```

`build.yml` автоматизирует сборку и публикацию Docker image в GHCR.

Общая логика:

```text
push / manual workflow run
checkout
docker login ghcr.io
docker build
smoke test
docker push
```

`tests.yml` запускает `pytest` на каждый push и pull request в `main`:

```text
push / pull_request / manual workflow run
checkout
setup-python 3.11
pip install -r requirements.txt
pytest -q
```

Для обычного рабочего запуска Kubernetes должен ссылаться на заранее выбранный release-tag. Если release-tag меняется, обнови image в GHCR overlay.

---

# Live Demo на Selectel VDS (docker compose + Traefik)

Live-демо хостится на **Selectel VDS** рядом с другими проектами за общим reverse-proxy **Traefik** (маршрутизация по docker-labels `Host(...)` + Let's Encrypt). Оркестрация — **docker compose** (не k8s: для одного VDS с демо это оверинжиниринг). Конфиг — `deploy/selectel/`.

> Railway-конфиги (`deploy/railway/`) — мертвы, оставлены как референс команд старта сервисов.

## Состав стека

| Сервис | Источник образа | Назначение | Домен |
|---|---|---|---|
| `backend` | GHCR (`:main`+) | Web API (FastAPI), pipeline in-process | `api.dcp.<IP>.nip.io` |
| `frontend` | build на сервере | статический дашборд (nginx) | `dcp.<IP>.nip.io` |
| `mlflow` | build на сервере | MLflow UI поверх Postgres | `mlflow.dcp.<IP>.nip.io` |
| `db` | `postgres:16-alpine` | backend-store для MLflow | — (internal) |
| `bot` | GHCR (тот же образ) | Telegram (за `profiles: ["bot"]`, **отключён**) | — |

`backend` и `bot` — **один образ**, различаются только `command` (см. `deploy/railway/*.toml`). `frontend`/`mlflow` собираются на сервере (`build:`), в GHCR их нет — CI публикует только backend-образ.

## Развёртывание

```bash
cd /opt/distributed-churn-prediction/deploy/selectel
cp .env.example .env          # вписать секреты
docker login ghcr.io          # backend-образ приватный, предварительно залогиниться
docker compose up -d --build  # mlflow+frontend собираются, backend тянется из GHCR
docker compose ps             # все Up; backend/bot НЕ Restarting
```

Проверка: `https://churn.skerter.dev/` → Health (зелёный) → Run Pipeline → `succeeded`. MLflow UI на `mlflow.churn.skerter.dev`.

## Важные нюансы (грабли, на которые уже наступили)

- **Тег образа обязан включать CORS.** Тег `v0.4.0` сделан до коммита add-CORS — backend из него не отдаёт `access-control-allow-origin`, фронт падает с `Failed to fetch` (хотя `/health` снаружи отвечает 200). Используй `:main` или новее. В `.env` — `IMAGE_TAG`.
- **frontend запекает API-URL в `app.js` при старте** (`BACKEND_URL`) — это публичный `https://${API_DOMAIN}` (браузер ходит на API напрямую). CORS на API расширяется `ALLOWED_ORIGINS=https://${SITE_DOMAIN}`.
- **Права на volumes:** named volumes создаются под root, контейнер — под mambauser → возможен `PermissionError /app/data/source` при старте. Лечится `chown` тома под UID образа.
- **backend и bot — РАЗНЫЕ тома логов** (`dcp_logs` vs `dcp_bot_logs`): иначе рестарт одного через `_recover_stale_runs()` помечает FAILED активный run другого.
- **⚠️ Общий compose-проект с соседними сервисами:** `docker compose down -v` и `--remove-orphans` в этой папке снесут чужие контейнеры/тома. Работать адресно (`up -d backend`, `restart backend`).
- **Telegram-бот отключён** на РФ-VDS (`api.telegram.org` недоступен). Поднять с прокси: `docker compose --profile bot up -d bot`.

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
├── deploy/
│   ├── selectel/            # Live Demo на Selectel VDS за общим Traefik (docker compose)
│   │   ├── compose.yaml     # backend + frontend + mlflow + db (+ bot за profile)
│   │   └── .env.example
│   └── railway/             # Railway-конфиги (мертвы, оставлены как референс команд старта)
│       ├── railway.bot.toml
│       ├── railway.backend.toml
│       ├── railway.frontend.toml
        └── railway.mlflow.toml
├── docker/                  # Docker/контейнерные файлы
│   ├── Dockerfile
│   ├── environment.linux.yml
│   └── start-web.sh
├── frontend/                # статический веб-дашборд (HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── k8s/
│   ├── base/
│   │   ├── cluster/
│   │   └── job/
│   ├── overlays/
│   │   ├── ghcr/
│   │   └── minikube-local/
│   └── operator/
├── mlflow/                  # MLflow tracking: runs и UI
│   └── mlruns/
├── notebooks/
│   └── eval_plots/          # графики оценки модели
├── src/
│   ├── app/
│   ├── application/
│   ├── infrastructure/
│   ├── orchestration/
│   └── presentation/
│       ├── cli/
│       ├── web/
│       └── bot/
├── tests/                   # smoke / unit / integration тесты
│   ├── smoke/
│   ├── unit/
│   └── integration/
├── environment.windows.yml
├── requirements.txt
├── pyproject.toml
├── Makefile
└── README.md
```

---

# Архитектура приложения

Проект использует layered architecture.

```text
presentation
application
orchestration
infrastructure
app/bootstrap
```

## `presentation`

Точки входа в приложение:

```text
src/presentation/cli
src/presentation/web
src/presentation/bot
```

CLI:

1. принимает аргументы;
2. вызывает bootstrap;
3. запускает use case;
4. возвращает JSON-ответ.

Web API:

1. принимает HTTP-запрос;
2. использует `AppContainer`, созданный при старте приложения;
3. запускает use cases;
4. возвращает JSON-ответ.

Telegram Bot:

1. принимает Telegram update через long-polling;
2. использует `AppContainer` и долгоживущий `BotPipelineExecutor`, созданные при старте бота;
3. вызывает use cases в обработчиках команд;
4. запускает pipeline в отдельном треде и отправляет push-уведомление по завершению.

И Web API, и бот используют одинаковый workflow с `run_id` поверх `FilePipelineRunStore`: запуск создаётся отдельно, статус доступен по идентификатору. Это позволяет одному и тому же `run_id`, созданному через HTTP, проверять через `/status` в Telegram — и наоборот.

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
