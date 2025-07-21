# WajoPhase2-Backend

## Data Migration from MS-SQL to Postgresql
```
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --exclude admin.logentry --indent 2 > wajo_prod_mssql_data_19July2025.json
```

```
python manage.py migrate --run-syncdb
```

```
python manage.py loaddata wajo_prod_mssql_data_19July2025.json --verbosity 3
```