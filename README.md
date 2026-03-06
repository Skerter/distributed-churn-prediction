# Distributed Churn Prediction Portfolio Project

End-to-end ML-пайплайн для предсказания оттока клиентов (churn) на больших данных, фокус на scalability и MLOps. Демонстрирует переход от локального прототипа (Pandas/XGBoost) к распределённым вычислениям (Dask + Kubernetes) для обработки 2M+ строк.

## Датасет
- [Expresso Churn Prediction Challenge](https://kaggle.com/datasets/hamzaghanmi/expresso-churn-prediction-challenge) (2M строк train, дисбаланс CHURN ~5%).
- Скачивание: Via kagglehub в `src/data/load_data.py`.

## Стек
- Локальный: Python 3.11, Pandas 3.0.1, XGBoost 3.2.0, Scikit-learn 1.8.0.
- Distributed: Dask (DataFrame/Array/ML), dask-xgboost, Docker (образы scheduler/workers), Kubernetes (minikube + Dask Operator для autoscaling).
- Логи: coloredlogs.
- Config: YAML для reproducibility.

## Структура проекта
📦distributed-churn-prediction
 ┣ 📂configs
 ┃ ┗ 📜config.yaml
 ┣ 📂data
 ┃ ┣ 📂processed
 ┃ ┗ 📂source
 ┣ 📂logs
 ┣ 📂models
 ┣ 📂notebooks
 ┃ ┣ 📂eval_plots
 ┃ ┣ 📂model_plots
 ┃ ┣ 📂reports
 ┃ ┣ 📜01_eda_local.ipynb
 ┃ ┗ 📜02_local_results.ipynb
 ┣ 📂src
 ┃ ┣ 📂data
 ┃ ┃ ┣ 📜load_data.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📂evaluation
 ┃ ┃ ┣ 📜evaluate.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📂features
 ┃ ┃ ┣ 📜create_features.py
 ┃ ┃ ┣ 📜encoding.py
 ┃ ┃ ┣ 📜feature_engineering.py
 ┃ ┃ ┣ 📜preprocessing.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┣ 📂models
 ┃ ┃ ┗ 📜train.py
 ┃ ┣ 📂utils
 ┃ ┃ ┣ 📜config.py
 ┃ ┃ ┣ 📜logger.py
 ┃ ┃ ┗ 📜__init__.py
 ┃ ┗ 📜__init__.py
 ┣ 📜.gitignore
 ┣ 📜environment.yml
 ┣ 📜main.py
 ┣ 📜main_local.py
 ┗ 📜README.md


- `configs/` — конфигурационные файлы (settings, окружения).
- `data/` — данные:
  - `processed/` — обработанные данные.
  - `source/` — исходные данные.
- `logs/` — логи работы скрипта.
- `models/` — обученные модели.
- `notebooks/` — Jupyter notebooks для EDA и анализа.
- `reports/` — отчёты и визуализации.
- `src/` — основной код:
  - `data/` — загрузка и обработка данных.
  - `features/` — инженерия признаков.
  - `models/` — обучение моделей.
  - `evaluation/` — оценка моделей.
  - `utils/` — утилиты (логирование, конфигурация).
  - `preprocessing.py` — препроцессинг данных.
  - `main.py` — точка входа в проект.
- `.gitignore` — игнорируемые файлы Git.
- `environment.yml` — зависимости окружения.
- `README.md` — документация проекта.

## Установка и запуск локального прототипа
1. `conda env create -f environment.yml && conda activate dist-churn-pred-env`
2. `python main_local.py` (full run: load → features → train → eval, ~10–15 мин)
   - Опции: `--skip-load` (если данные есть), etc.
3. Метрики: ROC-AUC 0.93, PR-AUC 0.70, Precision@top-10% 0.76.

## Ключевые этапы пайплайна
- **Предобработка/Features**: Заполнение пропусков (median/missing), target encoding с smoothing=10, новые признаки (AVG_REVENUE, REGULARITY_SCORE). Сохранение в Parquet для Dask.
- **Обучение**: XGBoost с CV=5 (StratifiedKFold), early stopping. Feature importance: REGULARITY top-1.
- **Оценка**: Метрики на hold-out, графики (ROC/PR/Confusion) в notebooks/eval_plots/.
- **Benchmarks**: Локальный runtime ~6 мин (single-core). Distributed target: <1 мин на K8s кластере (**Еще не реализовано**).

## Результаты локального baseline
| Метрика              | Значение | Insight |
|----------------------|----------|---------|
| ROC-AUC             | 0.9315  | Сильная discriminative power. |
| PR-AUC              | 0.7047  | Хорошо для дисбаланса ~5% CHURN. |
| LogLoss             | 0.2512  | Низкий, модель confident. |
| Precision@top-10%   | 0.7608  | 76% churn в топ-рисковых — бизнес-lift для retention. |

Графики: См. notebooks/eval_plots/ (ROC/PR curves).

Top features (из train.log):
- REGULARITY: 0.45 (активность — ключевой churn-предиктор)
- FREQUENCE_RECH: 0.15
- REVENUE: 0.12

## Scalability Plan (Переход к Distributed)
1. **Dask Features/Train**: Заменить Pandas на Dask DataFrame (read_parquet, groupby.agg для encoding), dask-xgboost.train для обучения. Distributed CV via HyperbandSearchCV.
2. **Docker**: Образы для Dask scheduler/workers (с зависимостями: xgboost, pandas).
3. **Kubernetes**: Minikube setup, deploy cluster (Dask Kubernetes Operator), autoscaling workers (3–12), dashboard для visuals (task graphs, CPU/memory).
4. **Тюнинг**: Distributed hyperparam search (learning_rate, max_depth) на кластере.
5. **Benchmarks**: Speedup x5–10, cost estimates (e.g., AWS EKS).
6. **MLOps**: MLflow для tracking, Airflow для orchestration.
