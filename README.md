# SQL Config Generator

Python + **Tkinter** desktop tool that reads **table metadata** (JSON/CSV) and generates **SQL configuration scripts**.

Useful for platform/config setup work: create tables, seed config rows, and emit a configuration registry from metadata.

## Features

- Load table/column metadata from `.json` or `.csv`
- Multi-select tables in a GUI
- Preview column metadata
- Generate:
  - optional `DROP TABLE`
  - `CREATE TABLE`
  - seed `INSERT` statements
  - config registry SQL (`cfg_table_registry`)
- MySQL and PostgreSQL dialects
- CLI mode for automation / CI

## Run (GUI)

```bash
# Ubuntu/Debian if needed
sudo apt install python3-tk

python app.py
```

## Run (CLI)

```bash
python cli.py samples/sample_metadata.json -o output/config_script.sql --dialect mysql
python cli.py samples/sample_metadata.csv --tables notification_template --seed-rows 3
```

## Metadata formats

### JSON

```json
[
  {
    "name": "app_config",
    "schema": "platform",
    "comment": "...",
    "columns": [
      {"name": "id", "data_type": "INT", "nullable": false, "primary_key": true}
    ]
  }
]
```

### CSV headers

`table_name,schema,column_name,data_type,nullable,primary_key,default,table_comment,column_comment`

## Author

Sumanth D Gowda
