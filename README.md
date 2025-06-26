# WajoPhase2-Backend

## Data Migration from MS-SQL to Postgresql
```
python manage.py dumpdata --database=mssql_legacy --settings=wajo_backend.settings_dev --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 4 > wajo_prod_mssql_data_26062025.json
```

```
python manage.py loaddata wajo_prod_mssql_data_26062025.json --settings=wajo_backend.settings_dev
```