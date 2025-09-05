import duckdb, yaml, pandas as pd
from typing import Tuple

def get_cfg(settings_path: str):
    with open(settings_path, 'r') as f:
        return yaml.safe_load(f)

ALLOWED_KEYWORDS = set([
    "select","from","where","group","by","order","limit","desc","asc","and","or",
    "sum","avg","count","min","max","date","market","channel","category","brand",
    "value_sales","unit_sales","share","value_yoy","share_yoy"
])

# def safe_sql(sql: str) -> bool:
#     test = sql.lower().replace("\n"," ")
#     # ultra-naive safety: deny semicolons & joins & subqueries to keep starter simple
#     if ";" in test: return False
#     if " join " in test: return False
#     if " union " in test: return False
#     if " insert " in test or " update " in test or " delete " in test: return False
#     return True
def safe_sql(sql: str):
    """
    Allow SELECT queries (incl. CTEs and JOINs).
    Block write/DDL and dangerous ops.
    Also strip a trailing semicolon so DuckDB accepts it either way.
    """
    sanitized = sql.strip().rstrip(";")
    test = " ".join(sanitized.lower().split())

    forbidden = [
        " insert ", " update ", " delete ", " drop ", " alter ",
        " create table ", " create schema ", " replace ", " vacuum ",
        " copy ", " attach ", " detach ", " pragma "
    ]
    if any(tok in test for tok in forbidden):
        return False, sanitized
    # must still be a SELECT
    if not test.startswith("with ") and not test.startswith("select "):
        return False, sanitized
    return True, sanitized


# def run_sql(sql: str, settings_path: str) -> Tuple[pd.DataFrame, str]:
#     if not safe_sql(sql):
#         raise ValueError("Query not allowed in starter (blocked keyword or pattern).")
#     cfg = get_cfg(settings_path)
#     con = duckdb.connect(cfg['duckdb_path'])
#     try:
#         df = con.execute(sql).fetchdf()
#     finally:
#         con.close()
#     if len(df) > cfg['max_rows']:
#         df = df.head(cfg['max_rows'])
#     return df, f"Rows: {len(df)}"
def run_sql(sql: str, settings_path: str):
    ok, sanitized = safe_sql(sql)
    if not ok:
        raise ValueError("Query not allowed in starter (blocked keyword or pattern).")
    cfg = get_cfg(settings_path)
    con = duckdb.connect(cfg['duckdb_path'])
    try:
        df = con.execute(sanitized).fetchdf()
    finally:
        con.close()
    if len(df) > cfg['max_rows']:
        df = df.head(cfg['max_rows'])
    return df, f"Rows: {len(df)}"
