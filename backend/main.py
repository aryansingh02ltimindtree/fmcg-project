from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
import json, yaml
import pandas as pd
import tempfile, os

from backend.ingest.excel_ingest import ingest_excel
from backend.sql.runner import run_sql, get_cfg

# use pandas path (your parser + runner)
from backend.nlp.parser import parse_user_text, intent_to_dict
from backend.nlp.pandas_runner import run_pandas_intent

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

# ---------- small cache so we don't reload same file repeatedly ----------
_DF_CACHE: Dict[str, pd.DataFrame] = {}

def _load_df(settings_path: str) -> pd.DataFrame:
    """
    Load & normalize the dataset using paths in settings.yaml.
    Expected keys:
      data:
        excel_path: data/sample_nielsen_extended.xlsx
        sheet_name: Sheet1
    """
    if settings_path in _DF_CACHE:
        return _DF_CACHE[settings_path]

    cfg = get_cfg(settings_path)
    data_cfg = cfg.get("data", {})
    excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
    sheet_name = data_cfg.get("sheet_name", "Sheet1")

    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    if "date" not in df.columns:
        raise ValueError("Dataset must have a 'date' column")
    df["date"] = pd.to_datetime(df["date"])
    for c in ["brand", "category", "market", "channel"]:
        if c in df.columns and df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()

    _DF_CACHE[settings_path] = df
    return df

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    mapper_json: str = json.dumps({
        "date":"date","market":"market","channel":"channel","category":"category",
        "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
    }),
    settings_path: str = "configs/settings.yaml"
):
    content = await file.read()
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, file.filename)
    with open(tmp_path, "wb") as f:
        f.write(content)

    mapper = json.loads(mapper_json)
    info = ingest_excel(tmp_path, mapper, settings_path)

    # bust cache so next /ask reloads fresh data for this settings_path
    _DF_CACHE.pop(settings_path, None)

    return {"status": "ok", "info": info}

@app.post("/ask")
@app.post("/ask")
def ask(body: AskBody):
    # inside /ask
    intent_model = parse_user_text(body.question)
    intent = intent_to_dict(intent_model, original_text=body.question)

    # enforce mode from text if still missing
    q = body.question.lower()
    tr = intent.get("time_range") or {}
    if "mode" not in tr:
        if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
            tr["mode"] = "MAT"
        elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
            tr["mode"] = "YTD"
    intent["time_range"] = tr or None

    # treat "table + limit" as Top-N and drop date
    if intent.get("task") == "table" and intent.get("top_n"):
        intent["task"] = "topn"
    if intent.get("task") == "topn":
        intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

    df = _load_df(body.settings_path)
    result = run_pandas_intent(df, intent)
    out_df, meta = result["data"], result["meta"]

    return {
        "intent": intent_model.model_dump(),
        "effective_intent": {
            **intent,
            # expose the actual dates the runner used
            "time_range": {
                **(intent.get("time_range") or {}),
                "start_used": meta["window"]["start"],
                "end_used": meta["window"]["end"],
            },
        },
        "sql": None,
        "meta": meta,
        "data": out_df.to_dict(orient="records"),
        "columns": list(out_df.columns),
        "insights": [],
    }

    # intent_model = parse_user_text(body.question)

    # # Build dict intent WITH original text so we can infer MAT/YTD
    # intent = intent_to_dict(intent_model, original_text=body.question)

    # # Safety: force mode if user text says MAT/YTD but converter didn't set it
    # q = body.question.lower()
    # tr = intent.get("time_range") or {}
    # if "mode" not in tr:
    #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
    #         tr["mode"] = "MAT"
    #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
    #         tr["mode"] = "YTD"
    # intent["time_range"] = tr if tr else None

    # # Safety: treat "table + limit" as Top-N
    # if intent.get("task") == "table" and intent.get("top_n"):
    #     intent["task"] = "topn"

    # # Safety: for Top-N, drop 'date' from dims
    # if intent.get("task") == "topn":
    #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

    # df = _load_df(body.settings_path)
    # result = run_pandas_intent(df, intent)
    # out_df, meta = result["data"], result["meta"]

    # bullets = []
    # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
    #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
    #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
    #     try:
    #         b = best.iloc[0]
    #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
    #     except Exception:
    #         pass
    #     try:
    #         w = worst.iloc[0]
    #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
    #     except Exception:
    #         pass
    # if "share" in out_df.columns and out_df["share"].notna().any():
    #     latest_share = out_df.iloc[-1]["share"]
    #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

    # empty_hint = None
    # if out_df.empty:
    #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

    # return {
    #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
    #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
    #     "sql": None,
    #     "meta": meta,                          # window actually used (dates)
    #     "data": out_df.to_dict(orient="records"),
    #     "columns": list(out_df.columns),
    #     "insights": bullets[:3],
    #     "empty_hint": empty_hint,
    # }

@app.post("/sql")
def run_raw_sql(body: SqlBody):
    # keep the raw SQL endpoint working exactly as before
    df, meta = run_sql(body.sql, body.settings_path)
    return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}
