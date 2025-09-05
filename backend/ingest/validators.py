from typing import List
import pandas as pd

REQUIRED_COLUMNS = [
    "date","market","channel","category","brand","value_sales","unit_sales","share"
]

def validate_schema(df: pd.DataFrame) -> List[str]:
    errors = []
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
    return errors

def validate_basic(df: pd.DataFrame) -> List[str]:
    errors = []
    if df['date'].isna().any():
        errors.append("Null dates found.")
    if (df['value_sales'] < 0).any():
        errors.append("Negative value_sales found.")
    if (df['unit_sales'] < 0).any():
        errors.append("Negative unit_sales found.")
    return errors
