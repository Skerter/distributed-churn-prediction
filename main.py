import sys, dask, dask_kubernetes, dask_ml, xgboost, dask_xgboost, sklearn, pandas, numpy, pyarrow  # jupyter импорт не нужен, это метапакет
print(f'Текущая версия Dask: {dask.__version__}')  # Должно вывести ~2026.2.x
print(f'Текущая версия Python: {sys.version}')
print("All imports successful!")

# TODO: Доделать вывод данных explore_dataset.ipynb
# TODO: Дописать kagglehub в environment.yml
# TODO: Проверять скачан ли датасет чтоб не перезагружать его, добавить обновление датасета и другие фичи