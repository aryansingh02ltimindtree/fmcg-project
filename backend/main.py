from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict
import json, yaml, pandas as pd
import tempfile, os
from backend.ingest.excel_ingest import ingest_excel
from backend.sql.runner import run_sql, get_cfg
from backend.nlp.parser import parse_user_text, intent_to_sql

app = FastAPI(title="Nielsen Excel Q&A — Starter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class AskBody(BaseModel):
    question: str
    settings_path: str = "configs/settings.yaml"

class SqlBody(BaseModel):
    sql: str
    settings_path: str = "configs/settings.yaml"

@app.post("/upload")
async def upload_excel(file: UploadFile = File(...), mapper_json: str = json.dumps({
    "date":"date","market":"market","channel":"channel","category":"category",
    "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
}), settings_path: str = "configs/settings.yaml"):
    content = await file.read()
    # tmp_path = f"/tmp/{file.file5name}"
    # with open(tmp_path, "wb") as f:
    #     f.write(content)


    tmp_dir = tempfile.gettempdir()  # works on Windows and Linux
    tmp_path = os.path.join(tmp_dir, file.filename)

    with open(tmp_path, "wb") as f:
        f.write(content)
    mapper = json.loads(mapper_json)
    info = ingest_excel(tmp_path, mapper, settings_path)
    return {"status":"ok", "info": info}

@app.post("/ask")
def ask(body: AskBody):
    intent = parse_user_text(body.question)
    cfg = get_cfg(body.settings_path)
    sql = intent_to_sql(intent, cfg['table_name'])
    df, meta = run_sql(sql, body.settings_path)
    # Simple insights (top 3 bullets based on diffs if available)
    bullets = []
    if 'value_yoy' in df.columns and df['value_yoy'].notna().any():
        best = df.sort_values('value_yoy', ascending=False).head(1)
        worst = df.sort_values('value_yoy', ascending=True).head(1)
        try:
            b = best.iloc[0]
            bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
        except Exception:
            pass
        try:
            w = worst.iloc[0]
            bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
        except Exception:
            pass
    if 'share' in df.columns and df['share'].notna().any():
        latest_share = df.iloc[-1]['share']
        bullets.append(f"Latest share in slice: {latest_share:.1f}%")
    return {
        "intent": intent.model_dump(),
        "sql": sql,
        "meta": meta,
        "data": df.to_dict(orient="records"),
        "columns": list(df.columns),
        "insights": bullets[:3]
    }

@app.post("/sql")
def run_raw_sql(body: SqlBody):
    df, meta = run_sql(body.sql, body.settings_path)
    return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}
