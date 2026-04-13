# Distributed Churn Prediction

Проект по построению и постепенному масштабированию ML-пайплайна для задачи предсказания оттока клиентов.

Сейчас в репозитории есть две основные траектории выполнения:

- **`pandas`** — локальный baseline-пайплайн на одной машине;
- **`dask_local`** — локальный распределённый пайплайн через `Dask LocalCluster`;
- **`dask_k8s`** — **в разработке**. В кодовой базе уже есть заготовки для подключения к внешнему Dask scheduler, но полноценный production-ready K8s pipeline ещё не завершён.

---

## Что делает проект

Проект реализует полный ML workflow:

1. проверяет наличие исходного датасета;
2. при необходимости скачивает его через `kagglehub`;
3. строит признаки и сохраняет обработанные данные в `parquet`;
4. обучает модель XGBoost;
5. оценивает качество модели и сохраняет метрики и графики.

Основная идея проекта — пройти путь от локального baseline-решения к более реалистичной распределённой архитектуре, не теряя управляемость кода, конфигов и точек входа.

---

## Текущий статус

| Профиль | Статус | Комментарий |
|---|---|---|
| `pandas` | Работает | Локальный baseline для feature engineering, training и evaluation |
| `dask_local` | Работает / экспериментально | Распределённая локальная версия через Dask |
| `dask_k8s` | В разработке | Нет завершённого end-to-end pipeline уровня production |

---

## Архитектура проекта

Проект собран вокруг модульной структуры с разделением на уровни приложения:

```text
src/churn/
├── app/
│   ├── bootstrap.py
│   ├── container.py
│   └── settings.py
├── application/
│   ├── dto/
│   ├── services/
│   │   ├── dataset_service.py
│   │   ├── evaluate_service.py
│   │   ├── feature_service.py
│   │   └── train_service.py
│   └── use_cases/
├── infrastructure/
│   ├── config/
│   ├── execution/
│   ├── logging/
│   └── storage/
├── orchestration/
│   └── pipelines/
│       ├── base.py
│       ├── pandas.py
│       └── dask_local.py
└── presentation/
    └── cli/
        ├── main.py
        └── parser.py
```

### Роли слоёв

- **`app/`** — bootstrap, контейнер зависимостей, агрегированные настройки.
- **`application/services/`** — бизнес-логика по данным, признакам, обучению и оценке.
- **`infrastructure/`** — загрузка конфигов, создание Dask client, логирование, файловые пути.
- **`orchestration/pipelines/`** — сценарии выполнения шагов пайплайна.
- **`presentation/cli/`** — CLI-интерфейс.

Такое разделение удобно тем, что локальная и распределённая версии используют один и тот же общий каркас, а различается только реализация конкретных шагов.

---

## Стек

- Python 3.11
- Pandas
- Dask / Distributed
- XGBoost
- Scikit-learn
- PyArrow / Parquet
- YAML-конфиги
- `coloredlogs`
- `kagglehub`

Для Kubernetes направления в окружении уже заложены зависимости, связанные с `dask-kubernetes`, но сам `dask_k8s` pipeline пока не доведён до готового сценария запуска.

---

## Данные

Источник данных: **Expresso Churn Prediction Challenge**.

В конфиге используется slug датасета:

```yaml
data:
  dataset_slug: "hamzaghanmi/expresso-churn-prediction-challenge"
  train_filename: "Train.csv"
  test_filename: "Test.csv"
  target_column: "CHURN"
```

При отсутствии локальных CSV пайплайн может попробовать скачать датасет автоматически.

---

## Конфигурация

Базовые параметры задаются через YAML.

Ключевые секции конфига:

- `paths` — пути к данным, моделям, логам и артефактам;
- `data` — параметры датасета и target-поля;
- `logging` — уровень логирования и файловый вывод;
- `runtime` — режим выполнения;
- `dask` — настройки локального или внешнего scheduler;
- `model`, `preprocessing`, `training`, `evaluation` — параметры ML-пайплайна.

Пример важных параметров:

```yaml
model:
  name: "xgboost"
  version: "local_baseline_v1"
  random_state: 42
  test_size: 0.2
  cv_folds: 5
  early_stopping_rounds: 50

preprocessing:
  fillna_num: "mean"
  fillna_cat: "missing"
  target_encoding: true
  smoothing: 10
  categorical_columns:
    - "REGION"
    - "TENURE"
    - "TOP_PACK"
```

---

## Установка окружения

### Linux / WSL

```bash
conda env create -f environment_linux.yml
conda activate dist-churn-pred-env
```

### Windows

```bash
conda env create -f environment.yml
conda activate dist-churn-pred-env
```

---

## Запуск CLI

Точка входа проекта — CLI.

### Проверка состояния приложения

```bash
python -m src.churn.presentation.cli.main health --profile pandas
```

### Просмотр объединённого конфига

```bash
python -m src.churn.presentation.cli.main show-config --profile pandas
```

### Dry-run пайплайна

```bash
python -m src.churn.presentation.cli.main run-pipeline --profile pandas
```

### Реальный запуск pandas pipeline

```bash
python -m src.churn.presentation.cli.main run-pipeline --profile pandas --execute
```

### Реальный запуск dask_local pipeline

```bash
python -m src.churn.presentation.cli.main run-pipeline --profile dask_local --execute
```

### Запуск с пропуском отдельных шагов

```bash
python -m src.churn.presentation.cli.main run-pipeline --profile pandas --execute --skip-load
python -m src.churn.presentation.cli.main run-pipeline --profile pandas --execute --skip-features
python -m src.churn.presentation.cli.main run-pipeline --profile pandas --execute --skip-train
python -m src.churn.presentation.cli.main run-pipeline --profile pandas --execute --skip-eval
```

Это полезно, когда часть артефактов уже существует и не нужно пересчитывать весь граф заново.

---

## Что создаётся в ходе работы

### Исходные данные

- `data/source/Train.csv`
- `data/source/Test.csv`

### Обработанные данные

- `data/processed/train_processed.parquet`
- `data/processed/test_processed.parquet`
- `data/processed/target_encoding_maps.json`

### Модели

- pandas-режим: `models/xgboost_<version>.pkl`
- dask_local-режим: `models/xgboost_<version>.json`

### Метрики и графики

- `models/*_eval_metrics.json`
- `notebooks/eval_plots/confusion_matrix.png`
- `notebooks/eval_plots/roc_curve.png`
- `notebooks/eval_plots/pr_curve.png`

---

## Особенности профилей

### `pandas`

Подходит для:

- baseline-реализации;
- локальной отладки логики признаков;
- проверки корректности оркестрации шагов;
- быстрой итерации над кодом без Dask-кластера.

### `dask_local`

Подходит для:

- проверки перехода с локального DataFrame на распределённый DataFrame;
- тестирования поведения шагов на Dask API;
- локального эксперимента с распределённым обучением через `xgboost.dask`.

### `dask_k8s`

Это направление пока не следует считать завершённым.

На текущем этапе:

- есть идея и конфигурационный задел;
- есть поддержка подключения к внешнему scheduler;
- нет завершённой end-to-end реализации, которую можно называть стабильной Kubernetes-версией проекта.

Именно поэтому в документации ниже и во всём репозитории `dask_k8s` следует воспринимать как **WIP**.

---

## Ограничения текущей версии

На данный момент важно учитывать несколько практических ограничений:

1. **`dask_k8s` не завершён** — проект ещё не дошёл до стабильного распределённого запуска в Kubernetes.
2. **Локальные baseline-метрики не стоит считать финальными production-метриками** — пайплайн ещё требует более строгой схемы валидации.
3. **Часть артефактов сейчас генерируется прямо внутри репозитория** — для production-версии лучше вынести их в отдельное хранилище или каталоги, не попадающие в git.
4. **Окружение очень чувствительно к версиям библиотек** — особенно в связке `dask`, `distributed`, `xgboost`, `pandas` и `dask-kubernetes`.

---

## Что стоит улучшить дальше

Приоритетный roadmap проекта:

1. убрать leakage в feature engineering и evaluation;
2. разделить train/validation/test более строго;
3. добавить автоматические тесты;
4. стабилизировать `dask_local`;
5. довести до конца `dask_k8s` профиль;
6. вынести артефакты и тяжёлые файлы из git;
7. добавить CI-проверки и smoke tests для CLI.

---

## Кому будет полезен проект

Этот репозиторий полезен как учебный и инженерный проект, если хочется понять:

- как спроектировать ML-пайплайн с несколькими backend-профилями;
- как плавно перейти от `pandas` к `dask`;
- как организовать код вокруг конфигов, orchestration и CLI;
- как подготовить архитектурную базу под дальнейший запуск в Kubernetes.

---

## Важное замечание

`dask_k8s` версия **ещё в разработке**. Если нужен стабильный сценарий запуска прямо сейчас, ориентироваться стоит на `pandas` и `dask_local`.
