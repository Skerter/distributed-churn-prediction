import sys, dask, dask_kubernetes, dask_ml, xgboost, dask_xgboost, sklearn, pandas, numpy, pyarrow  # jupyter импорт не нужен, это метапакет
print(f'Текущая версия Dask: {dask.__version__}')  # Должно вывести ~2026.2.x
print(f'Текущая версия Python: {sys.version}')
print("All imports successful!")

# TODO: Определиться с общей структурой проекта, выбрать паттерны и прочую хуйню
# TODO: Подумать будет ли норм все работать с такими конфигами

# TODO: Исходный код для k8s не работает, контейнеры падают в ошибку, надо разбираться в документации dask_kubernetes
# TODO: Почистить репозиторий от мусора который написала нейронка, в src/ бардак