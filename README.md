# distributed-churn-prediction

Пишем end-to-end ML-пайплайн для предсказания оттока клиентов на больших данных, демонстрируя распределённые вычисления для портфолио. Фокус на scalability и MLOps.

Этапы пайплайна:
Предобработка: Масштабная обработка в Dask (joins, groupby, handling missing/huge categoricals, target encoding).
Feature Engineering: Создание признаков на всём объёме (rolling windows, aggregations, one-hot/target encoding distributed).
Обучение: Распределённый градиентный бустинг (XGBoost/LightGBM via dask-xgboost/dask-lightgbm) на кластере.
Тюнинг: Distributed hyperparameter search (HyperbandSearchCV/RandomizedSearchCV с dask backend).
Оценка: Метрики (ROC-AUC, precision-recall), A/B-симуляция на hold-out, benchmarks speedup (single vs distributed).

Стек:
Python: Pandas/NumPy/Scikit-learn для прототипа.
Dask: Для распределённых DataFrame/Array и ML.
Docker: Контейнеризация образов (Dask workers/scheduler с зависимостями).
Kubernetes (minikube/kind локально + Dask Kubernetes Operator): Multi-node кластер (3–12 workers), autoscaling, dashboard для визуализации.
