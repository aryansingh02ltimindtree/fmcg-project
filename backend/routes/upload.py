from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from typing import Dict
import pandas as pd, yaml, json
from pathlib import Path

from backend.ingest.excel_ingest import ingest_excel

router = APIRouter()

@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    mapper_json: str = Form(...),          # JSON string with column mapping
    settings_path: str = Form("config/settings.yaml")
):
    # save temp file
    tmp_path = Path("data/tmp.xlsx")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    mapper = json.loads(mapper_json)

    # run your ingestion (writes parquet + duckdb)
    summary = ingest_excel(str(tmp_path), mapper, settings_path)

    # load the parquet into memory for fast queries
    with open(settings_path, "r") as f:
        cfg = yaml.safe_load(f)
    df = pd.read_parquet(Path(cfg["parquet_path"]))

    # store on app.state
    request.app.state.df = df

    return {"ok": True, "summary": summary}
