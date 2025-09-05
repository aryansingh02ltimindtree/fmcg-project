import duckdb, json, yaml
from datetime import datetime
import pandas as pd
from pathlib import Path
from .validators import validate_schema, validate_basic

def month_start(dt):
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    return pd.Timestamp(year=dt.year, month=dt.month, day=1)

def derive_fields(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(['market','channel','category','brand','date'])
    df['value_yoy'] = df.groupby(['market','channel','category','brand'])['value_sales'].pct_change(12)
    df['share_yoy'] = df.groupby(['market','channel','category','brand'])['share'].diff(12)
    return df

def ingest_excel(xlsx_path: str, mapper_json: dict, settings_path: str):
    with open(settings_path, 'r') as f:
        cfg = yaml.safe_load(f)

    # Load Excel (first sheet)
    df = pd.read_excel(xlsx_path)

    # Map columns
    rename_map = {mapper_json[k]: k for k in mapper_json}
    df = df.rename(columns=rename_map)

    # Coerce types
    df['date'] = pd.to_datetime(df['date']).map(month_start)
    for numcol in ['value_sales','unit_sales','share']:
        df[numcol] = pd.to_numeric(df[numcol], errors='coerce')

    # Validate
    errors = validate_schema(df) + validate_basic(df)
    if errors:
        raise ValueError("; ".join(errors))

    # Derive fields
    df = derive_fields(df)

    # Save parquet
    parquet_path = Path(cfg['parquet_path'])
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, index=False)

    # Load into DuckDB
    con = duckdb.connect(cfg['duckdb_path'])
    con.execute(f"CREATE OR REPLACE TABLE {cfg['table_name']} AS SELECT * FROM read_parquet('{parquet_path.as_posix()}');")
    con.close()
    return {
        "rows": len(df),
        "min_date": str(df['date'].min().date()),
        "max_date": str(df['date'].max().date())
    }
