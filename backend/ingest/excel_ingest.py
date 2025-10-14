# # backend/ingest/excel_ingest.py

# import duckdb, json, yaml
# from datetime import datetime
# import pandas as pd
# from pathlib import Path
# from .validators import validate_schema, validate_basic


# def month_start(x):
#     """Normalize to first day of that month.
#     Handles NaN, Excel serials, strings, and Timestamps safely."""
#     if pd.isna(x):
#         return pd.NaT

#     # Excel serials (int/float days since 1899-12-30)
#     if isinstance(x, (int, float)) and not isinstance(x, bool):
#         try:
#             dt = pd.to_datetime("1899-12-30") + pd.to_timedelta(int(x), unit="D")
#         except Exception:
#             return pd.NaT
#     else:
#         dt = pd.to_datetime(x, errors="coerce")

#     if pd.isna(dt):
#         return pd.NaT

#     return pd.Timestamp(year=dt.year, month=dt.month, day=1)


# def derive_fields(df: pd.DataFrame) -> pd.DataFrame:
#     # Ensure no NaT dates before sorting
#     df = df.dropna(subset=["date"]).reset_index(drop=True)
#     df = df.sort_values(["market", "channel", "category", "brand", "date"])

#     # YoY % change (12 months back) and Share YoY (pp change)
#     df["value_yoy"] = df.groupby(
#         ["market", "channel", "category", "brand"]
#     )["value_sales"].pct_change(12)

#     df["share_yoy"] = df.groupby(
#         ["market", "channel", "category", "brand"]
#     )["share"].diff(12)

#     return df


# def ingest_excel(xlsx_path: str, mapper_json: dict, settings_path: str):
#     # Load config
#     with open(settings_path, "r") as f:
#         cfg = yaml.safe_load(f)

#     # Load Excel (first sheet by default)
#     df = pd.read_excel(xlsx_path)

#     # Map columns (Excel → internal schema)
#     rename_map = {mapper_json[k]: k for k in mapper_json}
#     df = df.rename(columns=rename_map)

#     # Normalize and coerce types
#     df["date"] = df["date"].apply(month_start)
#     df = df.dropna(subset=["date"]).reset_index(drop=True)

#     for numcol in ["value_sales", "unit_sales", "share"]:
#         if numcol in df.columns:
#             df[numcol] = pd.to_numeric(df[numcol], errors="coerce")

#     # Validate schema
#     errors = validate_schema(df) + validate_basic(df)
#     if errors:
#         raise ValueError("; ".join(errors))

#     # Derive YoY/Share YoY fields
#     df = derive_fields(df)

#     # Save parquet
#     parquet_path = Path(cfg["parquet_path"])
#     parquet_path.parent.mkdir(parents=True, exist_ok=True)
#     df.to_parquet(parquet_path, index=False)

#     # Load into DuckDB
#     con = duckdb.connect(cfg["duckdb_path"])
#     con.execute(
#         f"""
#         CREATE OR REPLACE TABLE {cfg['table_name']}
#         AS SELECT * FROM read_parquet('{parquet_path.as_posix()}');
#         """
#     )
#     con.close()

#     return {
#         "rows": len(df),
#         "min_date": str(df["date"].min().date()),
#         "max_date": str(df["date"].max().date()),
#     }



#Working ingestion code



# # backend/ingest/excel_ingest.py

# # backend/ingest/excel_ingest.py

# # backend/ingest/excel_ingest.py
# import duckdb, json, yaml
# from datetime import datetime
# import pandas as pd
# from pathlib import Path
# from .validators import validate_schema, validate_basic
# import logging

# log = logging.getLogger("ingest")
# log.setLevel(logging.INFO)

# # --- robust date helpers -------------------------------------------------------

# def _parse_excel_date_cell(val):
#     """
#     Parse a cell that may be:
#       - pandas/py Timestamp or datetime
#       - Excel serial integer/float (days since 1899-12-30)
#       - string like '01-12-2025 00:00:00' or '25 Nov 2025'
#     Returns pandas.Timestamp or pd.NaT
#     """
#     if pd.isna(val):
#         return pd.NaT

#     # Already a Timestamp/datetime?
#     if isinstance(val, (pd.Timestamp, datetime)):
#         return pd.Timestamp(val)

#     # Numeric: could be Excel serial
#     if isinstance(val, (int, float)):
#         # very small/negative numbers are not valid serials
#         try:
#             # Excel epoch: 1899-12-30 (works for both Windows/Excel)
#             return pd.to_datetime(val, unit="d", origin="1899-12-30", errors="coerce")
#         except Exception:
#             return pd.NaT

#     # String: try multiple parses (day-first tolerant)
#     if isinstance(val, str):
#         s = val.strip()
#         if not s:
#             return pd.NaT
#         # First try pandas with dayfirst=True
#         ts = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
#         if pd.isna(ts):
#             # Try without dayfirst as a fallback
#             ts = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
#         return ts if not pd.isna(ts) else pd.NaT

#     # Unknown type
#     return pd.NaT


# def month_start(dt):
#     """
#     Safe month-normalizer:
#     - returns pd.NaT if input is invalid
#     - otherwise truncates to first day of that month
#     """
#     ts = _parse_excel_date_cell(dt)
#     if pd.isna(ts):
#         return pd.NaT
#     return pd.Timestamp(ts).to_period("M").to_timestamp(how="start")


# # --- feature derivations -------------------------------------------------------

# def derive_fields(df: pd.DataFrame) -> pd.DataFrame:
#     df = df.sort_values(['market','channel','category','brand','date'])
#     # only compute YoY if we have at least 12 months and non-null dates
#     ok = df['date'].notna()
#     df.loc[ok, 'value_yoy'] = (
#         df.loc[ok]
#           .groupby(['market','channel','category','brand'])['value_sales']
#           .pct_change(12)
#     )
#     df.loc[ok, 'share_yoy'] = (
#         df.loc[ok]
#           .groupby(['market','channel','category','brand'])['share']
#           .diff(12)
#     )
#     return df


# # --- main ingest ---------------------------------------------------------------

# def ingest_excel(xlsx_path: str, mapper_json: dict, settings_path: str):
#     with open(settings_path, 'r') as f:
#         cfg = yaml.safe_load(f)

#     # Load Excel (first sheet by default)
#     df = pd.read_excel(xlsx_path)

#     # Map columns to our canonical names
#     rename_map = {mapper_json[k]: k for k in mapper_json}
#     df = df.rename(columns=rename_map)

#     # --- parse & normalize dates robustly ---
#     raw_dates = df['date']
#     parsed_dates = raw_dates.map(_parse_excel_date_cell)
#     df['date'] = parsed_dates.map(month_start)  # normalize to month start (safe for NaT)

#     # numeric columns
#     for numcol in ['value_sales','unit_sales','share']:
#         if numcol in df.columns:
#             df[numcol] = pd.to_numeric(df[numcol], errors='coerce')

#     # Log/snapshot rows that still have invalid dates
#     bad_mask = df['date'].isna()
#     bad_count = int(bad_mask.sum())
#     if bad_count:
#         samples = df.loc[bad_mask, ['date', 'market','channel','category','brand']].head(3)
#         log.warning(f"[INGEST] Found {bad_count} rows with invalid/missing dates. Sample:\n{samples}")
#         # Save bad rows for inspection
#         invalid_dir = Path("data/invalid")
#         invalid_dir.mkdir(parents=True, exist_ok=True)
#         df.loc[bad_mask].to_csv(invalid_dir / "invalid_dates.csv", index=False)

#     # Drop invalid-date rows (required for time windows)
#     if bad_count:
#         df = df.loc[~bad_mask].copy()

#     # Validate
#     errors = validate_schema(df) + validate_basic(df)
#     if errors:
#         raise ValueError("; ".join(errors))

#     # Derive fields
#     df = derive_fields(df)

#     # Save parquet
#     parquet_path = Path(cfg['parquet_path'])
#     parquet_path.parent.mkdir(parents=True, exist_ok=True)
#     df.to_parquet(parquet_path, index=False)

#     # Load into DuckDB (kept for your SQL endpoint)
#     con = duckdb.connect(cfg['duckdb_path'])
#     con.execute(f"CREATE OR REPLACE TABLE {cfg['table_name']} AS SELECT * FROM read_parquet('{parquet_path.as_posix()}');")
#     con.close()

#     # Summary log
#     min_d = str(df['date'].min().date()) if not df.empty else None
#     max_d = str(df['date'].max().date()) if not df.empty else None
#     log.info(f"[INGEST] Ingested {len(df)} rows; date range {min_d} -> {max_d}")

#     return {
#         "rows": len(df),
#         "min_date": min_d,
#         "max_date": max_d,
#         "invalid_date_rows": bad_count
#     }














# backend/ingest/excel_ingest.py

# backend/ingest/excel_ingest.py

# backend/ingest/excel_ingest.py
# backend/ingest/excel_ingest.py
from typing import Optional
import pandas as pd

# GLOBAL_DF: Optional[pd.DataFrame] = None   # <-- top-level export

# def get_df() -> Optional[pd.DataFrame]:
#     # safer accessor (avoids weird import reload issues)
#     return GLOBAL_DF





import duckdb, json, yaml
from datetime import datetime
import pandas as pd
from pathlib import Path
from .validators import validate_schema, validate_basic
import logging

log = logging.getLogger("ingest")
log.setLevel(logging.INFO)

# --- robust date helpers -------------------------------------------------------

def _parse_excel_date_cell(val):
    """
    Parse a cell that may be:
      - pandas/py Timestamp or datetime
      - Excel serial integer/float (days since 1899-12-30)
      - string like '01-12-2025 00:00:00' or '25 Nov 2025'
    Returns pandas.Timestamp or pd.NaT
    """
    if pd.isna(val):
        return pd.NaT

    # Already a Timestamp/datetime?
    if isinstance(val, (pd.Timestamp, datetime)):
        return pd.Timestamp(val)

    # Numeric: could be Excel serial
    if isinstance(val, (int, float)):
        # very small/negative numbers are not valid serials
        try:
            # Excel epoch: 1899-12-30 (works for both Windows/Excel)
            return pd.to_datetime(val, unit="d", origin="1899-12-30", errors="coerce")
        except Exception:
            return pd.NaT

    # String: try multiple parses (day-first tolerant)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return pd.NaT
        # First try pandas with dayfirst=True
        ts = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
        if pd.isna(ts):
            # Try without dayfirst as a fallback
            ts = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
        return ts if not pd.isna(ts) else pd.NaT

    # Unknown type
    return pd.NaT


def month_start(dt):
    """
    Safe month-normalizer:
    - returns pd.NaT if input is invalid
    - otherwise truncates to first day of that month
    """
    ts = _parse_excel_date_cell(dt)
    if pd.isna(ts):
        return pd.NaT
    return pd.Timestamp(ts).to_period("M").to_timestamp(how="start")


# --- feature derivations -------------------------------------------------------

def derive_fields(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(['market','channel','category','brand','date'])
    # only compute YoY if we have at least 12 months and non-null dates
    ok = df['date'].notna()
    df.loc[ok, 'value_yoy'] = (
        df.loc[ok]
          .groupby(['market','channel','category','brand'])['value_sales']
          .pct_change(12)
    )
    df.loc[ok, 'share_yoy'] = (
        df.loc[ok]
          .groupby(['market','channel','category','brand'])['share']
          .diff(12)
    )
    return df


# --- main ingest ---------------------------------------------------------------

def ingest_excel(xlsx_path: str, mapper_json: dict, settings_path: str):
    # global GLOBAL_DF
    with open(settings_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    
    # Load Excel (first sheet by default)
    df = pd.read_excel(xlsx_path)
    
   
    # Map columns to our canonical names
    rename_map = {mapper_json[k]: k for k in mapper_json}
    df = df.rename(columns=rename_map)

    # --- parse & normalize dates robustly ---
    raw_dates = df['date']
    parsed_dates = raw_dates.map(_parse_excel_date_cell)
    df['date'] = parsed_dates.map(month_start)  # normalize to month start (safe for NaT)

    # numeric columns
    for numcol in ['value_sales','unit_sales','share']:
        if numcol in df.columns:
            df[numcol] = pd.to_numeric(df[numcol], errors='coerce')

    # Log/snapshot rows that still have invalid dates
    bad_mask = df['date'].isna()
    bad_count = int(bad_mask.sum())
    if bad_count:
        samples = df.loc[bad_mask, ['date', 'market','channel','category','brand']].head(3)
        log.warning(f"[INGEST] Found {bad_count} rows with invalid/missing dates. Sample:\n{samples}")
        # Save bad rows for inspection
        invalid_dir = Path("data/invalid")
        invalid_dir.mkdir(parents=True, exist_ok=True)
        df.loc[bad_mask].to_csv(invalid_dir / "invalid_dates.csv", index=False)

    # Drop invalid-date rows (required for time windows)
    if bad_count:
        df = df.loc[~bad_mask].copy()

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

    # Load into DuckDB (kept for your SQL endpoint)
    con = duckdb.connect(cfg['duckdb_path'])
    con.execute(f"CREATE OR REPLACE TABLE {cfg['table_name']} AS SELECT * FROM read_parquet('{parquet_path.as_posix()}');")
    con.close()

    # Summary log
    min_d = str(df['date'].min().date()) if not df.empty else None
    max_d = str(df['date'].max().date()) if not df.empty else None
    log.info(f"[INGEST] Ingested {len(df)} rows; date range {min_d} -> {max_d}")
    # GLOBAL_DF=df

    return {
        "rows": len(df),
        "min_date": min_d,
        "max_date": max_d,
        "invalid_date_rows": bad_count
    }

