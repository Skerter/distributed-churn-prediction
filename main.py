import sys, dask, dask_kubernetes, dask_ml, xgboost, dask_xgboost, sklearn, pandas, numpy, pyarrow  # jupyter импорт не нужен, это метапакет
print(f'Текущая версия Dask: {dask.__version__}')  # Должно вывести ~2026.2.x
print(f'Текущая версия Python: {sys.version}')
print("All imports successful!")

# TODO: организовать адекватное логгирование с сохранением в папку log/ или в папки проекта, добавить логи в игнор
# TODO: Сделать requirements.txt (вроде правильно название написал)
# TODO: Определиться с общей структурой проекта, выбрать паттерны и прочую хуйню
# TODO: Сделать нормальные конфиги как у людей
