#Working code for everything else
# from fastapi import FastAPI, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Dict
# import json, yaml
# import pandas as pd
# import tempfile, os

# from backend.ingest.excel_ingest import ingest_excel
# from backend.sql.runner import run_sql, get_cfg

# # use pandas path (your parser + runner)
# from backend.nlp.parser import parse_user_text, intent_to_dict
# from backend.nlp.pandas_runner import run_pandas_intent

# app = FastAPI(title="Nielsen Excel Q&A — Starter API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )

# class AskBody(BaseModel):
#     question: str
#     settings_path: str = "configs/settings.yaml"

# class SqlBody(BaseModel):
#     sql: str
#     settings_path: str = "configs/settings.yaml"

# # ---------- small cache so we don't reload same file repeatedly ----------
# _DF_CACHE: Dict[str, pd.DataFrame] = {}

# def _load_df(settings_path: str) -> pd.DataFrame:
#     """
#     Load & normalize the dataset using paths in settings.yaml.
#     Expected keys:
#       data:
#         excel_path: data/sample_nielsen_extended.xlsx
#         sheet_name: Sheet1
#     """
#     if settings_path in _DF_CACHE:
#         return _DF_CACHE[settings_path]

#     cfg = get_cfg(settings_path)
#     data_cfg = cfg.get("data", {})
#     excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
#     sheet_name = data_cfg.get("sheet_name", "Sheet1")

#     df = pd.read_excel(excel_path, sheet_name=sheet_name)
#     if "date" not in df.columns:
#         raise ValueError("Dataset must have a 'date' column")
#     df["date"] = pd.to_datetime(df["date"])
#     for c in ["brand", "category", "market", "channel"]:
#         if c in df.columns and df[c].dtype == object:
#             df[c] = df[c].astype(str).str.strip()

#     _DF_CACHE[settings_path] = df
#     return df

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/upload")
# async def upload_excel(
#     file: UploadFile = File(...),
#     mapper_json: str = json.dumps({
#         "date":"date","market":"market","channel":"channel","category":"category",
#         "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
#     }),
#     settings_path: str = "configs/settings.yaml"
# ):
#     content = await file.read()
#     tmp_dir = tempfile.gettempdir()
#     tmp_path = os.path.join(tmp_dir, file.filename)
#     with open(tmp_path, "wb") as f:
#         f.write(content)

#     mapper = json.loads(mapper_json)
#     info = ingest_excel(tmp_path, mapper, settings_path)

#     # bust cache so next /ask reloads fresh data for this settings_path
#     _DF_CACHE.pop(settings_path, None)

#     return {"status": "ok", "info": info}

# @app.post("/ask")
# @app.post("/ask")
# def ask(body: AskBody):
#     # inside /ask
#     intent_model = parse_user_text(body.question)
#     intent = intent_to_dict(intent_model, original_text=body.question)

#     # enforce mode from text if still missing
#     q = body.question.lower()
#     tr = intent.get("time_range") or {}
#     if "mode" not in tr:
#         if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#             tr["mode"] = "MAT"
#         elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#             tr["mode"] = "YTD"
#     intent["time_range"] = tr or None

#     # treat "table + limit" as Top-N and drop date
#     if intent.get("task") == "table" and intent.get("top_n"):
#         intent["task"] = "topn"
#     if intent.get("task") == "topn":
#         intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     df = _load_df(body.settings_path)
#     result = run_pandas_intent(df, intent)
#     out_df, meta = result["data"], result["meta"]

#     return {
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
#         "insights": [],
#     }

#     # intent_model = parse_user_text(body.question)

#     # # Build dict intent WITH original text so we can infer MAT/YTD
#     # intent = intent_to_dict(intent_model, original_text=body.question)

#     # # Safety: force mode if user text says MAT/YTD but converter didn't set it
#     # q = body.question.lower()
#     # tr = intent.get("time_range") or {}
#     # if "mode" not in tr:
#     #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#     #         tr["mode"] = "MAT"
#     #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#     #         tr["mode"] = "YTD"
#     # intent["time_range"] = tr if tr else None

#     # # Safety: treat "table + limit" as Top-N
#     # if intent.get("task") == "table" and intent.get("top_n"):
#     #     intent["task"] = "topn"

#     # # Safety: for Top-N, drop 'date' from dims
#     # if intent.get("task") == "topn":
#     #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     # df = _load_df(body.settings_path)
#     # result = run_pandas_intent(df, intent)
#     # out_df, meta = result["data"], result["meta"]

#     # bullets = []
#     # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
#     #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
#     #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
#     #     try:
#     #         b = best.iloc[0]
#     #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     #     try:
#     #         w = worst.iloc[0]
#     #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     # if "share" in out_df.columns and out_df["share"].notna().any():
#     #     latest_share = out_df.iloc[-1]["share"]
#     #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

#     # empty_hint = None
#     # if out_df.empty:
#     #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

#     # return {
#     #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
#     #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
#     #     "sql": None,
#     #     "meta": meta,                          # window actually used (dates)
#     #     "data": out_df.to_dict(orient="records"),
#     #     "columns": list(out_df.columns),
#     #     "insights": bullets[:3],
#     #     "empty_hint": empty_hint,
#     # }

# @app.post("/sql")
# def run_raw_sql(body: SqlBody):
#     # keep the raw SQL endpoint working exactly as before
#     df, meta = run_sql(body.sql, body.settings_path)
#     return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}



#Working code for generating line chart insights, not others







# from fastapi import FastAPI, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Dict
# import json, yaml
# import pandas as pd
# import tempfile, os

# from backend.ingest.excel_ingest import ingest_excel
# from backend.sql.runner import run_sql, get_cfg

# # use pandas path (your parser + runner)
# from .nlp.parser import parse_user_text, intent_to_dict
# from .nlp.pandas_runner import run_pandas_intent,generate_simple_insights

# app = FastAPI(title="Nielsen Excel Q&A — Starter API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )

# class AskBody(BaseModel):
#     question: str
#     settings_path: str = "configs/settings.yaml"

# class SqlBody(BaseModel):
#     sql: str
#     settings_path: str = "configs/settings.yaml"

# # ---------- small cache so we don't reload same file repeatedly ----------
# _DF_CACHE: Dict[str, pd.DataFrame] = {}

# def _load_df(settings_path: str) -> pd.DataFrame:
#     """
#     Load & normalize the dataset using paths in settings.yaml.
#     Expected keys:
#       data:
#         excel_path: data/sample_nielsen_extended.xlsx
#         sheet_name: Sheet1
#     """
#     if settings_path in _DF_CACHE:
#         return _DF_CACHE[settings_path]

#     cfg = get_cfg(settings_path)
#     data_cfg = cfg.get("data", {})
#     excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
#     sheet_name = data_cfg.get("sheet_name", "Sheet1")

#     df = pd.read_excel(excel_path, sheet_name=sheet_name)
#     if "date" not in df.columns:
#         raise ValueError("Dataset must have a 'date' column")
#     df["date"] = pd.to_datetime(df["date"])
#     for c in ["brand", "category", "market", "channel"]:
#         if c in df.columns and df[c].dtype == object:
#             df[c] = df[c].astype(str).str.strip()

#     _DF_CACHE[settings_path] = df
#     return df

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/upload")
# async def upload_excel(
#     file: UploadFile = File(...),
#     mapper_json: str = json.dumps({
#         "date":"date","market":"market","channel":"channel","category":"category",
#         "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
#     }),
#     settings_path: str = "configs/settings.yaml"
# ):
#     content = await file.read()
#     tmp_dir = tempfile.gettempdir()
#     tmp_path = os.path.join(tmp_dir, file.filename)
#     with open(tmp_path, "wb") as f:
#         f.write(content)

#     mapper = json.loads(mapper_json)
#     info = ingest_excel(tmp_path, mapper, settings_path)

#     # bust cache so next /ask reloads fresh data for this settings_path
#     _DF_CACHE.pop(settings_path, None)

#     return {"status": "ok", "info": info}

# @app.post("/ask")
# @app.post("/ask")
# def ask(body: AskBody):
#     # inside /ask
#     intent_model = parse_user_text(body.question)
#     intent = intent_to_dict(intent_model, original_text=body.question)

#     # enforce mode from text if still missing
#     q = body.question.lower()
#     tr = intent.get("time_range") or {}
#     if "mode" not in tr:
#         if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#             tr["mode"] = "MAT"
#         elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#             tr["mode"] = "YTD"
#     intent["time_range"] = tr or None

#     # treat "table + limit" as Top-N and drop date
#     if intent.get("task") == "table" and intent.get("top_n"):
#         intent["task"] = "topn"
#     if intent.get("task") == "topn":
#         intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     df = _load_df(body.settings_path)
#     result = run_pandas_intent(df, intent)
#     out_df, meta = result["data"], result["meta"]
#     insights=generate_simple_insights(out_df,meta)

#     return {
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
#         "insights": insights,
#     }

#     # intent_model = parse_user_text(body.question)

#     # # Build dict intent WITH original text so we can infer MAT/YTD
#     # intent = intent_to_dict(intent_model, original_text=body.question)

#     # # Safety: force mode if user text says MAT/YTD but converter didn't set it
#     # q = body.question.lower()
#     # tr = intent.get("time_range") or {}
#     # if "mode" not in tr:
#     #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#     #         tr["mode"] = "MAT"
#     #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#     #         tr["mode"] = "YTD"
#     # intent["time_range"] = tr if tr else None

#     # # Safety: treat "table + limit" as Top-N
#     # if intent.get("task") == "table" and intent.get("top_n"):
#     #     intent["task"] = "topn"

#     # # Safety: for Top-N, drop 'date' from dims
#     # if intent.get("task") == "topn":
#     #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     # df = _load_df(body.settings_path)
#     # result = run_pandas_intent(df, intent)
#     # out_df, meta = result["data"], result["meta"]

#     # bullets = []
#     # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
#     #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
#     #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
#     #     try:
#     #         b = best.iloc[0]
#     #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     #     try:
#     #         w = worst.iloc[0]
#     #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     # if "share" in out_df.columns and out_df["share"].notna().any():
#     #     latest_share = out_df.iloc[-1]["share"]
#     #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

#     # empty_hint = None
#     # if out_df.empty:
#     #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

#     # return {
#     #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
#     #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
#     #     "sql": None,
#     #     "meta": meta,                          # window actually used (dates)
#     #     "data": out_df.to_dict(orient="records"),
#     #     "columns": list(out_df.columns),
#     #     "insights": bullets[:3],
#     #     "empty_hint": empty_hint,
#     # }

# @app.post("/sql")
# def run_raw_sql(body: SqlBody):
#     # keep the raw SQL endpoint working exactly as before
#     df, meta = run_sql(body.sql, body.settings_path)
#     return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}






#Working code bad insights




#Final working code:
# from fastapi import FastAPI, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Dict
# import json, yaml
# import pandas as pd
# import tempfile, os

# from backend.ingest.excel_ingest import ingest_excel
# from backend.sql.runner import run_sql, get_cfg

# # use pandas path (your parser + runner)
# from .nlp.parser import parse_user_text, intent_to_dict
# from .nlp.pandas_runner import run_pandas_intent
# from backend.insights import generate_simple_insights

# app = FastAPI(title="Nielsen Excel Q&A — Starter API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )

# class AskBody(BaseModel):
#     question: str
#     settings_path: str = "configs/settings.yaml"

# class SqlBody(BaseModel):
#     sql: str
#     settings_path: str = "configs/settings.yaml"

# # ---------- small cache so we don't reload same file repeatedly ----------
# _DF_CACHE: Dict[str, pd.DataFrame] = {}

# def _load_df(settings_path: str) -> pd.DataFrame:
#     """
#     Load & normalize the dataset using paths in settings.yaml.
#     Expected keys:
#       data:
#         excel_path: data/sample_nielsen_extended.xlsx
#         sheet_name: Sheet1
#     """
#     if settings_path in _DF_CACHE:
#         return _DF_CACHE[settings_path]

#     cfg = get_cfg(settings_path)
#     data_cfg = cfg.get("data", {})
#     excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
#     sheet_name = data_cfg.get("sheet_name", "Sheet1")

#     df = pd.read_excel(excel_path, sheet_name=sheet_name)
#     if "date" not in df.columns:
#         raise ValueError("Dataset must have a 'date' column")
#     df["date"] = pd.to_datetime(df["date"])
#     for c in ["brand", "category", "market", "channel"]:
#         if c in df.columns and df[c].dtype == object:
#             df[c] = df[c].astype(str).str.strip()

#     _DF_CACHE[settings_path] = df
#     return df

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/upload")
# async def upload_excel(
#     file: UploadFile = File(...),
#     mapper_json: str = json.dumps({
#         "date":"date","market":"market","channel":"channel","category":"category",
#         "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
#     }),
#     settings_path: str = "configs/settings.yaml"
# ):
#     content = await file.read()
#     tmp_dir = tempfile.gettempdir()
#     tmp_path = os.path.join(tmp_dir, file.filename)
#     with open(tmp_path, "wb") as f:
#         f.write(content)

#     mapper = json.loads(mapper_json)
#     info = ingest_excel(tmp_path, mapper, settings_path)

#     # bust cache so next /ask reloads fresh data for this settings_path
#     _DF_CACHE.pop(settings_path, None)

#     return {"status": "ok", "info": info}

# @app.post("/ask")
# @app.post("/ask")
# def ask(body: AskBody):
#     # inside /ask
#     intent_model = parse_user_text(body.question)
#     intent = intent_to_dict(intent_model, original_text=body.question)

#     # enforce mode from text if still missing
#     q = body.question.lower()
#     tr = intent.get("time_range") or {}
#     if "mode" not in tr:
#         if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#             tr["mode"] = "MAT"
#         elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#             tr["mode"] = "YTD"
#     intent["time_range"] = tr or None

#     # treat "table + limit" as Top-N and drop date
#     if intent.get("task") == "table" and intent.get("top_n"):
#         intent["task"] = "topn"
#     if intent.get("task") == "topn":
#         intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     df = _load_df(body.settings_path)
#     result = run_pandas_intent(df, intent)
#     # print(result["meta"])
#     import pandas as pd


#     import pandas as pd
#     import numpy as np
#     import json

    

#     out_df, meta = result["data"], result["meta"]
#     print(f"{result["meta"]}")
#     # print(f"DEBUG>>>> {out_df}")
#     insights=generate_simple_insights(out_df,meta)

#     return {
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
#         "insights": insights,
#     }
  
#     # intent_model = parse_user_text(body.question)

#     # # Build dict intent WITH original text so we can infer MAT/YTD
#     # intent = intent_to_dict(intent_model, original_text=body.question)

#     # # Safety: force mode if user text says MAT/YTD but converter didn't set it
#     # q = body.question.lower()
#     # tr = intent.get("time_range") or {}
#     # if "mode" not in tr:
#     #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#     #         tr["mode"] = "MAT"
#     #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#     #         tr["mode"] = "YTD"
#     # intent["time_range"] = tr if tr else None

#     # # Safety: treat "table + limit" as Top-N
#     # if intent.get("task") == "table" and intent.get("top_n"):
#     #     intent["task"] = "topn"

#     # # Safety: for Top-N, drop 'date' from dims
#     # if intent.get("task") == "topn":
#     #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     # df = _load_df(body.settings_path)
#     # result = run_pandas_intent(df, intent)
#     # out_df, meta = result["data"], result["meta"]

#     # bullets = []
#     # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
#     #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
#     #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
#     #     try:
#     #         b = best.iloc[0]
#     #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     #     try:
#     #         w = worst.iloc[0]
#     #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     # if "share" in out_df.columns and out_df["share"].notna().any():
#     #     latest_share = out_df.iloc[-1]["share"]
#     #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

#     # empty_hint = None
#     # if out_df.empty:
#     #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

#     # return {
#     #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
#     #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
#     #     "sql": None,
#     #     "meta": meta,                          # window actually used (dates)
#     #     "data": out_df.to_dict(orient="records"),
#     #     "columns": list(out_df.columns),
#     #     "insights": bullets[:3],
#     #     "empty_hint": empty_hint,
#     # }

# @app.post("/sql")
# def run_raw_sql(body: SqlBody):
#     # keep the raw SQL endpoint working exactly as before
#     df, meta = run_sql(body.sql, body.settings_path)
#     return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}










# from curses import meta
# from fastapi import FastAPI, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Dict
# import json, yaml
# import pandas as pd
# import tempfile, os

# from backend.ingest.excel_ingest import ingest_excel
# from backend.sql.runner import run_sql, get_cfg

# # use pandas path (your parser + runner)
# from .nlp.parser import parse_user_text, intent_to_dict
# from .nlp.pandas_runner import run_pandas_intent
# from backend.insights import generate_simple_insights

# app = FastAPI(title="Nielsen Excel Q&A — Starter API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )

# class AskBody(BaseModel):
#     question: str
#     settings_path: str = "configs/settings.yaml"

# class SqlBody(BaseModel):
#     sql: str
#     settings_path: str = "configs/settings.yaml"

# # ---------- small cache so we don't reload same file repeatedly ----------
# _DF_CACHE: Dict[str, pd.DataFrame] = {}

# def _load_df(settings_path: str) -> pd.DataFrame:
#     """
#     Load & normalize the dataset using paths in settings.yaml.
#     Expected keys:
#       data:
#         excel_path: data/sample_nielsen_extended.xlsx
#         sheet_name: Sheet1
#     """
#     if settings_path in _DF_CACHE:
#         return _DF_CACHE[settings_path]

#     cfg = get_cfg(settings_path)
#     data_cfg = cfg.get("data", {})
#     excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
#     sheet_name = data_cfg.get("sheet_name", "Sheet1")

#     df = pd.read_excel(excel_path, sheet_name=sheet_name)
#     if "date" not in df.columns:
#         raise ValueError("Dataset must have a 'date' column")
#     df["date"] = pd.to_datetime(df["date"])
#     for c in ["brand", "category", "market", "channel"]:
#         if c in df.columns and df[c].dtype == object:
#             df[c] = df[c].astype(str).str.strip()

#     _DF_CACHE[settings_path] = df
#     return df

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/upload")
# async def upload_excel(
#     file: UploadFile = File(...),
#     mapper_json: str = json.dumps({
#         "date":"date","market":"market","channel":"channel","category":"category",
#         "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
#     }),
#     settings_path: str = "configs/settings.yaml"
# ):
#     content = await file.read()
#     tmp_dir = tempfile.gettempdir()
#     tmp_path = os.path.join(tmp_dir, file.filename)
#     with open(tmp_path, "wb") as f:
#         f.write(content)

#     mapper = json.loads(mapper_json)
#     info = ingest_excel(tmp_path, mapper, settings_path)

#     # bust cache so next /ask reloads fresh data for this settings_path
#     _DF_CACHE.pop(settings_path, None)

#     return {"status": "ok", "info": info}

# @app.post("/ask")
# @app.post("/ask")
# def ask(body: AskBody):
#     # inside /ask
#     intent_model = parse_user_text(body.question)
#     intent = intent_to_dict(intent_model, original_text=body.question)

#     # enforce mode from text if still missing
#     q = body.question.lower()
#     tr = intent.get("time_range") or {}
#     if "mode" not in tr:
#         if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#             tr["mode"] = "MAT"
#         elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#             tr["mode"] = "YTD"
#     intent["time_range"] = tr or None

#     # treat "table + limit" as Top-N and drop date
#     if intent.get("task") == "table" and intent.get("top_n"):
#         intent["task"] = "topn"
#     if intent.get("task") == "topn":
#         intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     df = _load_df(body.settings_path)
#     result = run_pandas_intent(df, intent)
#     # print(result["meta"])
    

   

    

#     import pandas as pd
#     import numpy as np
#     import pandas as pd

#     def _pick_time_col(df: pd.DataFrame) -> str | None:
#         # prefer true datetime; fallbacks are ok too
#         for c in ["date", "month_date", "x_dt", "month"]:
#             if c in df.columns:
#                 return c
#         return None

#     def _format_period(val) -> str:
#         # output nice "Jan 2024" labels where possible
#         if isinstance(val, pd.Timestamp):
#             return val.to_period("M").strftime("%b %Y")
#         try:
#             ts = pd.to_datetime(val, errors="coerce")
#             if pd.notna(ts):
#                 return ts.to_period("M").strftime("%b %Y")
#         except Exception:
#             pass
#         return str(val)

#     def _pick_measure_for_line(df: pd.DataFrame, meta: dict) -> list[str]:
#         # choose the measure(s) to report
#         prefer = str(meta.get("measure") or "")
#         candidates = [m for m in ["value_sales", "unit_sales"] if m in df.columns]
#         if prefer and prefer in candidates:
#             return [prefer]
#         return candidates or []

#     def build_line_table_data(df: pd.DataFrame, meta: dict) -> dict:
#         """
#         Returns a dict ready to put under payload['table_data'] for line charts.
#         Structure:
#         {
#             "measure": "value_sales",
#             "by_brand": [
#             {"brand":"Alpha","min_value":..., "min_period":"...", "max_value":..., "max_period":"..."},
#             ...
#             ]
#         }
#         If no 'brand' column, returns "overall" with a single min/max row.
#         """
#         tcol = _pick_time_col(df)
#         measures = _pick_measure_for_line(df, meta)
#         out: dict = {"_time_col": tcol}  # small debug hint; remove if you don't want it

#         if not tcol or not measures:
#             return out  # nothing to do

#         # If both value & unit exist, we can emit both blocks
#         for m in measures:
#             block_key = m  # e.g. "value_sales"
#             rows = []

#             if "brand" in df.columns:
#                 for brand, g in df.groupby("brand", dropna=False):
#                     g = g.dropna(subset=[m])
#                     if g.empty or tcol not in g.columns:
#                         continue
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "brand": None if pd.isna(brand) else str(brand),
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })
#             else:
#                 g = df.dropna(subset=[m])
#                 if not g.empty and tcol in g.columns:
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })

#             out[block_key] = {
#                 "measure": m,
#                 "by_brand": rows if "brand" in df.columns else None,
#                 "overall": None if "brand" in df.columns else rows[0] if rows else None,
#             }

#         return out
#     # def build_llm_payload(df: pd.DataFrame, meta: dict, intent: dict) -> dict:
#     #     payload = {
#     #         "mode": meta.get("mode"),
#     #         "chart_type": meta.get("chart_type"),
#     #         "dims": meta.get("dims") or [],
#     #         "filters": meta.get("filters") or {},
#     #         "window": meta.get("window") or {},
#     #         "measure": meta.get("measure"),
#     #         # "table_data":{"brand":{Alpha:{min_sales:,monthofmaxsales date},max_sales:,maxsales month date}}}
#     #     }

#     #     if (meta.get("chart_type") == "line"):
#     #         payload["table_data"] = build_line_table_data(df, meta)
         
#     #     dims = [d for d in (meta.get("dims") or []) if d != "date"]
#     #     measure_hint = str(meta.get("measure") or "")
#     #     # print([for i in df.iterrows()])
#     #     if meta.get("chart_type")=="bar" and meta.get("mode")==None:
#     #         payload["table_data"]=df.to_json(orient="records")
#     #         print(payload)
#     #     #     payload["table_data"]=

#     #     # --- ✅ Capture YoY details ---
#     #     if measure_hint in ("value_yoy", "unit_yoy"):
#     #         base_measure = "value_sales" if "value" in measure_hint else "unit_sales"
#     #         curr_col = f"{base_measure}_curr"
#     #         prev_col = f"{base_measure}_prev"
#     #         yoy_col  = measure_hint

#     #         if all(c in df.columns for c in [curr_col, prev_col, yoy_col]):
#     #             yoy_records = []
#     #             for _, r in df[dims + [curr_col, prev_col, yoy_col]].iterrows():
#     #                 rec = {d: r[d] for d in dims}
#     #                 rec.update({
#     #                     "curr": r[curr_col],
#     #                     "prev": r[prev_col],
#     #                     "yoy_pct": r[yoy_col],
#     #                 })
#     #                 yoy_records.append(rec)

#     #             payload["yoy_details"] = {
#     #                 "base_measure": base_measure,
#     #                 "records": yoy_records,
#     #                 "prev_window": meta.get("prev_window") or (meta.get("debug", {}) or {}).get("prev_window"),
#     #             }

#     #     # --- ✅ Capture MAT compare details ---
#     #     if (meta.get("mode") == "MAT_COMPARE") or ("mat_compare" in meta):
#     #         mc = meta.get("mat_compare", {}) or {}
#     #         label_col = "mat_label" if "mat_label" in df.columns else None
#     #         base_measure = meta.get("measure") or "value_sales"

#     #         group_by = []
#     #         if label_col: group_by.append(label_col)
#     #         if "brand" in df.columns: group_by.append("brand")
#     #         for d in dims:
#     #             if d not in group_by: group_by.append(d)

#     #         mat_records = []
#     #         if base_measure in df.columns and group_by:
#     #             grouped = df.groupby(group_by, dropna=False)[base_measure].sum().reset_index()
#     #             mat_records = grouped.to_dict(orient="records")

#     #         payload["mat_details"] = {
#     #             "measure": base_measure,
#     #             "anchor_month": mc.get("anchor_month"),
#     #             "years": mc.get("years") or [],
#     #             "labels": mc.get("labels") or [],
#     #             "records": mat_records,
#     #         }

#     #     return payload

    


#     import pandas as pd
#     import numpy as np

#     def build_llm_payload(out_df: pd.DataFrame, meta: dict) -> dict:
#         df = out_df.copy()
#         chart_type = str(meta.get("chart_type") or "").lower()
#         dims       = list(meta.get("dims") or [])
#         filters    = dict(meta.get("filters") or {})
#         window     = dict(meta.get("window") or {})
#         measure    = str(meta.get("measure") or "value_sales")
#         mode_raw   = str(meta.get("mode") or "").upper()
#         periods=meta.get("periods")
#         print("DEBUG>>>")
#         # print(mode_raw)
#         if mode_raw=='_YOY':
#             mode_raw=mode_raw.replace("_","")

#         # print(periods)
        

#         # ---------- normalize mode ----------
#         if mode_raw in ("MAT_COMPARE", "YTD"):
#             mode_norm = mode_raw
#         else:
#             if chart_type == "line":   mode_norm = "LINE"
#             elif chart_type == "bar":  mode_norm = "BAR"
#             elif chart_type == "table":mode_norm = "TABLE"
#             else:                      mode_norm = "CUSTOM"

#         # ---------- ensure time cols ----------
#         time_col = None
#         if "date" in df.columns:
#             time_col = "date"
#             with pd.option_context("mode.chained_assignment", None):
#                 df["date"] = pd.to_datetime(df["date"], errors="coerce")
#                 df["month_label"] = df["date"].dt.strftime("%b %Y")
#                 df["month_iso"]   = df["date"].dt.to_period("M").astype(str)

#         # ---------- small sample ----------
#         sample_cols = [c for c in df.columns if c in
#                     ["date","month_label","month_iso","brand","category","market",
#                         "value_sales","unit_sales","share",
#                         "value_sales_curr","value_sales_prev","value_yoy",
#                         "unit_sales_curr","unit_sales_prev","unit_yoy",
#                         "value_mom","unit_mom"]]
#         table_sample = df[sample_cols].head(6).to_dict(orient="records") if sample_cols else []

#         # helper: pick a base measure sensibly
#         def _pick_base_measure(frame: pd.DataFrame) -> str | None:
#             for c in ("value_sales","unit_sales"):
#                 if c in frame.columns:
#                     return c
#             num = frame.select_dtypes(include=[np.number]).columns.tolist()
#             return num[0] if num else None

#         # ---------- TREND (unchanged) ----------
#         trend_block = None
#         if chart_type == "line" and time_col is not None:
#             base_measure = _pick_base_measure(df)
#             by_brand = []
#             if base_measure is not None:
#                 if "brand" in df.columns:
#                     for b, g in df.groupby("brand", dropna=False):
#                         g = g.dropna(subset=[base_measure])
#                         if g.empty: continue
#                         rmin = g.loc[g[base_measure].idxmin()]
#                         rmax = g.loc[g[base_measure].idxmax()]
#                         by_brand.append({
#                             "brand": b if pd.notna(b) else "Unknown",
#                             "min":  {"value": float(rmin[base_measure]),
#                                     "period": str(rmin.get("month_iso") or ""),
#                                     "label":  str(rmin.get("month_label") or "")},
#                             "max":  {"value": float(rmax[base_measure]),
#                                     "period": str(rmax.get("month_iso") or ""),
#                                     "label":  str(rmax.get("month_label") or "")},
#                         })
#                 g = df.dropna(subset=[base_measure])
#                 overall = None
#                 if not g.empty:
#                     rmin = g.loc[g[base_measure].idxmin()]
#                     rmax = g.loc[g[base_measure].idxmax()]
#                     overall = {
#                         "min":  {"value": float(rmin[base_measure]),
#                                 "period": str(rmin.get("month_iso") or ""),
#                                 "label":  str(rmin.get("month_label") or "")},
#                         "max":  {"value": float(rmax[base_measure]),
#                                 "period": str(rmax.get("month_iso") or ""),
#                                 "label":  str(rmax.get("month_label") or "")},
#                     }
#                 trend_block = {"measure": base_measure, "by_brand": by_brand, "overall": overall}
#                 # print(trend_block)

#         # ---------- YoY (unchanged; now explicit) ----------
#         # print(meta)
#         yoy_block = None
#         if {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns) or \
#         {"unit_sales_curr","unit_sales_prev","unit_yoy"}.issubset(df.columns):

#             use_value = {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns)
#             curr_col  = "value_sales_curr" if use_value else "unit_sales_curr"
#             prev_col  = "value_sales_prev" if use_value else "unit_sales_prev"
#             yoy_col   = "value_yoy"        if use_value else "unit_yoy"

#             group_dims = [d for d in ("brand","category","market","channel") if d in df.columns]

#             tmp = df[group_dims + [curr_col, prev_col, yoy_col]].copy()
#             print(df)
#             print(f"filters:{filters}")
#             print(tmp)
#             # if not tmp.empty:
#             #     tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             if group_dims:  # only group if dimensions exist
#                 tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             else:
#                 tmp = tmp.sum(numeric_only=True).to_frame().T.reset_index(drop=True)

#             items = []
#             for _, r in tmp.iterrows():
#                 item = {
#                     "curr": float(r[curr_col]) if pd.notna(r[curr_col]) else None,
#                     "prev": float(r[prev_col]) if pd.notna(r[prev_col]) else None,
#                     "yoy_pct": float(r[yoy_col]) if pd.notna(r[yoy_col]) else None,
#                 }
#                 for d in group_dims:
#                     item[d] = r[d] if d in r and pd.notna(r[d]) else None
#                 items.append(item)

#             yoy_block = {"measure_type": "value" if use_value else "unit", "items": items}
#         # print(yoy_block)
        

#         # # ---------- MAT compare (unchanged) ----------
#         from datetime import datetime
#         mat_block = None
#         mat_info = meta.get("mat_compare")
#         if isinstance(mat_info, dict) and "labels" in mat_info:
#             label_col = "mat_label" if "mat_label" in df.columns else None
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None
#             items = []
#             if label_col and base_measure:
#                 # print(label_col)
#                 agg = df.groupby(label_col, dropna=False)[base_measure].sum().reset_index()
#                 for _, r in agg.iterrows():
#                     items.append({"label": str(r[label_col]), "total": float(r[base_measure])})
#             mat_block = {"items": items, "anchor_month": mat_info.get("anchor_month")}
#         # for i in items[]
#         # for i in items:
            
#         #     year=int(i['label'].replace("MAT","").strip())
#         #     # print(year)
#         #     end=pd.to_datetime(window['end'])
#         #     end=end.replace(year=year)
#         #     # print(end)
#         #     start=end-pd.DateOffset(months=11)
#         #     # print(start)
#         # print(meta)
#         # print(meta)
#         if meta.get('periods') is not None:
#             for i in range(0,len(meta['periods'])):
#                 meta['periods'][i].update(out_df.to_dict(orient="records")[i])
#             # print("METAAAAAA DATA:",meta)
#             # print(mat_block)
        
#             # print(meta['periods'])

#             sorted_periods=sorted(meta['periods'], key=lambda x: x['value_sales'],reverse=True)
#             for i,j in enumerate(sorted_periods):
#                 meta['periods'][i].update({'rank':i+1})
#             print(meta)

#             # print("SORTED PERIODS:",meta)
            





#         # ---------- BAR / topN (unchanged) ----------
#         bar_block = None
#         if chart_type == "bar":
#             non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
#             xcat = None
#             for c in ["brand","category","market","channel","segment","manufacturer"]:
#                 if c in non_numeric: xcat = c; break
#             if xcat is None and non_numeric: xcat = non_numeric[0]
#             ycols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
#             prefer_y = [c for c in ["value_sales","unit_sales","value_yoy","unit_yoy"] if c in ycols]
#             y = prefer_y[0] if prefer_y else (ycols[0] if ycols else None)
#             items = []
#             if xcat and y:
#                 tmp = df[[xcat, y]].copy().groupby(xcat, dropna=False)[y].sum().reset_index()
#                 tmp = tmp.sort_values(y, ascending=False, na_position="last")
#                 for i, r in enumerate(tmp.itertuples(index=False), start=1):
#                     items.append({"rank": i, "label": getattr(r, xcat), "value": float(getattr(r, y))})
#                 bar_block = {"x": xcat, "y": y, "items": items}

#         # ---------- NEW: MoM block (per brand + overall) ----------
#         mom_block = None
#         if time_col is not None:
#             # choose measure for MoM (value preferred)
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None

#             # see if MoM column already exists
#             mom_col = "value_mom" if "value_mom" in df.columns else \
#                     "unit_mom"  if "unit_mom"  in df.columns else None

#             def _series_items(frame: pd.DataFrame) -> list[dict]:
#                 f = frame.copy()
#                 # Sort by time
#                 f = f.sort_values("month_iso" if "month_iso" in f.columns else "date")
#                 # Compute MoM if missing
#                 if mom_col is None and base_measure in f.columns:
#                     f["_prev"] = f[base_measure].shift(1)
#                     with np.errstate(divide="ignore", invalid="ignore"):
#                         f["_mom"] = (f[base_measure] / f["_prev"]) - 1
#                 else:
#                     # use existing column
#                     f["_mom"] = f[mom_col]
#                     if base_measure in f.columns:
#                         f["_prev"] = f[base_measure].shift(1)

#                 items = []
#                 for _, r in f.iterrows():
#                     period = str(r.get("month_iso") or (r["date"].to_period("M").strftime("%Y-%m")
#                                                         if pd.notna(r.get("date")) else ""))
#                     label  = str(r.get("month_label") or "")
#                     mom_pct = r.get("_mom")
#                     curr = r.get(base_measure) if base_measure in f.columns else None
#                     prev = r.get("_prev")
#                     if pd.isna(mom_pct):   mom_pct = None
#                     if pd.isna(curr):      curr = None
#                     if pd.isna(prev):      prev = None
#                     items.append({"period": period, "label": label,
#                                 "mom_pct": float(mom_pct) if mom_pct is not None else None,
#                                 "curr": float(curr) if curr is not None else None,
#                                 "prev": float(prev) if prev is not None else None})
#                 # keep only rows where mom is computed or exists
#                 return [it for it in items if it["mom_pct"] is not None]

#             by_brand = []
#             if "brand" in df.columns:
#                 for b, g in df.groupby("brand", dropna=False):
#                     ser = _series_items(g)
#                     if ser:
#                         by_brand.append({"brand": b if pd.notna(b) else "Unknown", "series": ser})

#             overall = None
#             ser_all = _series_items(df)
#             if ser_all:
#                 overall = {"series": ser_all}

#             if by_brand or overall:
#                 mom_block = {
#                     "measure": base_measure or ("value_sales" if mom_col == "value_mom" else "unit_sales"),
#                     "by_brand": by_brand,
#                     "overall": overall
#                 }

#         # ---------- assemble ----------
#         # if meta['periods'] is not None:

#         payload = {
#             "mode": mode_norm,
#             "measure": measure,
#             "window": window,
#             "dims": [d for d in dims if d != "date"],
#             "filters": filters,
#             # "table_sample": table_sample,
#         }
#         if mat_block is not None:
#             # print(meta)
#             mat_block=meta
#         if trend_block is not None:     payload["trend"] = trend_block
#         if yoy_block is not None:       payload["yoy"] = yoy_block
#         if mat_block is not None:       payload["mat_compare"] = mat_block
#         if bar_block is not None:       payload["bar"] = bar_block
#         if mom_block is not None:       payload["mom"] = mom_block
#         # print(mat_block)
#         if mat_block is not None:
#             # payload['items']=payload['periods']
#             del payload['bar']
#         # print(result["meta"])
#         # if mode_raw=="MAT_YOY" or mode_raw=="YTD_YOY"  or mode_raw=="YOY":
#         payload['calculation_mode']=mode_raw.lower()
#         if "total" in payload['calculation_mode']:
#             payload.pop('mom')
#             # print(payload.keys())
#         import re

#         total_pattern = re.compile(r"\b(total|overall|aggregate|grand\s*total|sum|cumulative|combined|net\s+sales)\b", re.IGNORECASE)
#         trend_pattern = re.compile(r"\b(trend|over\s+time|month[-\s]*wise|monthly|line\s*chart|last\s+\d+\s+months)\b", re.IGNORECASE)
#         if total_pattern.search(intent['raw_text']) and not trend_pattern.search(intent['raw_text']):
#            payload['calculation_mode']=f'total {measure}'

       

#         return payload
#     payload = build_llm_payload(result["data"], result["meta"])
#     print(f"ITEMSSSSS:{payload}")
#     print(intent['raw_text'])
    

#     # import pandas as pd

  

#     # print(build_llm_payload(result["data"],result["meta"]))


#     out_df, meta = result["data"], result["meta"]
#     # print(f"{result["meta"]}")
#     # print(f"DEBUG>>>> {out_df}")
#     insights=generate_simple_insights(out_df,meta)
#     aa={
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
        
#     }
#     # print(aa)
  

#     return {
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
#         "insights": insights,
#     }
  
#     # intent_model = parse_user_text(body.question)

#     # # Build dict intent WITH original text so we can infer MAT/YTD
#     # intent = intent_to_dict(intent_model, original_text=body.question)

#     # # Safety: force mode if user text says MAT/YTD but converter didn't set it
#     # q = body.question.lower()
#     # tr = intent.get("time_range") or {}
#     # if "mode" not in tr:
#     #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#     #         tr["mode"] = "MAT"
#     #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#     #         tr["mode"] = "YTD"
#     # intent["time_range"] = tr if tr else None

#     # # Safety: treat "table + limit" as Top-N
#     # if intent.get("task") == "table" and intent.get("top_n"):
#     #     intent["task"] = "topn"

#     # # Safety: for Top-N, drop 'date' from dims
#     # if intent.get("task") == "topn":
#     #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     # df = _load_df(body.settings_path)
#     # result = run_pandas_intent(df, intent)
#     # out_df, meta = result["data"], result["meta"]

#     # bullets = []
#     # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
#     #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
#     #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
#     #     try:
#     #         b = best.iloc[0]
#     #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     #     try:
#     #         w = worst.iloc[0]
#     #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     # if "share" in out_df.columns and out_df["share"].notna().any():
#     #     latest_share = out_df.iloc[-1]["share"]
#     #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

#     # empty_hint = None
#     # if out_df.empty:
#     #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

#     # return {
#     #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
#     #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
#     #     "sql": None,
#     #     "meta": meta,                          # window actually used (dates)
#     #     "data": out_df.to_dict(orient="records"),
#     #     "columns": list(out_df.columns),
#     #     "insights": bullets[:3],
#     #     "empty_hint": empty_hint,
#     # }

# @app.post("/sql")
# def run_raw_sql(body: SqlBody):
#     # keep the raw SQL endpoint working exactly as before
#     df, meta = run_sql(body.sql, body.settings_path)
#     return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}




















#Insights do not contain peak line chart, only contain top 2 no topn, do not contain ytd yoy and mat yoy window, plain ytd and mat also.




# from fastapi import FastAPI, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Dict
# import json, yaml
# import pandas as pd
# import tempfile, os

# from backend.ingest.excel_ingest import ingest_excel
# from backend.sql.runner import run_sql, get_cfg

# # use pandas path (your parser + runner)
# from .nlp.parser import parse_user_text, intent_to_dict
# from .nlp.pandas_runner import run_pandas_intent
# from backend.insights import generate_simple_insights,attach_insights

# app = FastAPI(title="Nielsen Excel Q&A — Starter API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )

# class AskBody(BaseModel):
#     question: str
#     settings_path: str = "configs/settings.yaml"

# class SqlBody(BaseModel):
#     sql: str
#     settings_path: str = "configs/settings.yaml"

# # ---------- small cache so we don't reload same file repeatedly ----------
# _DF_CACHE: Dict[str, pd.DataFrame] = {}

# def _load_df(settings_path: str) -> pd.DataFrame:
#     """
#     Load & normalize the dataset using paths in settings.yaml.
#     Expected keys:
#       data:
#         excel_path: data/sample_nielsen_extended.xlsx
#         sheet_name: Sheet1
#     """
#     if settings_path in _DF_CACHE:
#         return _DF_CACHE[settings_path]

#     cfg = get_cfg(settings_path)
#     data_cfg = cfg.get("data", {})
#     excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
#     sheet_name = data_cfg.get("sheet_name", "Sheet1")

#     df = pd.read_excel(excel_path, sheet_name=sheet_name)
#     if "date" not in df.columns:
#         raise ValueError("Dataset must have a 'date' column")
#     df["date"] = pd.to_datetime(df["date"])
#     for c in ["brand", "category", "market", "channel"]:
#         if c in df.columns and df[c].dtype == object:
#             df[c] = df[c].astype(str).str.strip()

#     _DF_CACHE[settings_path] = df
#     return df

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/upload")
# async def upload_excel(
#     file: UploadFile = File(...),
#     mapper_json: str = json.dumps({
#         "date":"date","market":"market","channel":"channel","category":"category",
#         "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
#     }),
#     settings_path: str = "configs/settings.yaml"
# ):
#     content = await file.read()
#     tmp_dir = tempfile.gettempdir()
#     tmp_path = os.path.join(tmp_dir, file.filename)
#     with open(tmp_path, "wb") as f:
#         f.write(content)

#     mapper = json.loads(mapper_json)
#     info = ingest_excel(tmp_path, mapper, settings_path)

#     # bust cache so next /ask reloads fresh data for this settings_path
#     _DF_CACHE.pop(settings_path, None)

#     return {"status": "ok", "info": info}

# @app.post("/ask")
# @app.post("/ask")
# def ask(body: AskBody):
#     # inside /ask
#     intent_model = parse_user_text(body.question)
#     intent = intent_to_dict(intent_model, original_text=body.question)

#     # enforce mode from text if still missing
#     q = body.question.lower()
#     tr = intent.get("time_range") or {}
#     if "mode" not in tr:
#         if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#             tr["mode"] = "MAT"
#         elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#             tr["mode"] = "YTD"
#     intent["time_range"] = tr or None

#     # treat "table + limit" as Top-N and drop date
#     if intent.get("task") == "table" and intent.get("top_n"):
#         intent["task"] = "topn"
#     if intent.get("task") == "topn":
#         intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     df = _load_df(body.settings_path)
#     result = run_pandas_intent(df, intent)
#     # payload= build_llm_payload(result["data"], result["meta"])
#     # print(payload)
#     # print(result["meta"])
    

   

    

#     import pandas as pd
#     import numpy as np
#     import pandas as pd

#     def _pick_time_col(df: pd.DataFrame) -> str | None:
#         # prefer true datetime; fallbacks are ok too
#         for c in ["date", "month_date", "x_dt", "month"]:
#             if c in df.columns:
#                 return c
#         return None

#     def _format_period(val) -> str:
#         # output nice "Jan 2024" labels where possible
#         if isinstance(val, pd.Timestamp):
#             return val.to_period("M").strftime("%b %Y")
#         try:
#             ts = pd.to_datetime(val, errors="coerce")
#             if pd.notna(ts):
#                 return ts.to_period("M").strftime("%b %Y")
#         except Exception:
#             pass
#         return str(val)

#     def _pick_measure_for_line(df: pd.DataFrame, meta: dict) -> list[str]:
#         # choose the measure(s) to report
#         prefer = str(meta.get("measure") or "")
#         candidates = [m for m in ["value_sales", "unit_sales"] if m in df.columns]
#         if prefer and prefer in candidates:
#             return [prefer]
#         return candidates or []

#     def build_line_table_data(df: pd.DataFrame, meta: dict) -> dict:
#         """
#         Returns a dict ready to put under payload['table_data'] for line charts.
#         Structure:
#         {
#             "measure": "value_sales",
#             "by_brand": [
#             {"brand":"Alpha","min_value":..., "min_period":"...", "max_value":..., "max_period":"..."},
#             ...
#             ]
#         }
#         If no 'brand' column, returns "overall" with a single min/max row.
#         """
#         tcol = _pick_time_col(df)
#         measures = _pick_measure_for_line(df, meta)
#         out: dict = {"_time_col": tcol}  # small debug hint; remove if you don't want it

#         if not tcol or not measures:
#             return out  # nothing to do

#         # If both value & unit exist, we can emit both blocks
#         for m in measures:
#             block_key = m  # e.g. "value_sales"
#             rows = []

#             if "brand" in df.columns:
#                 for brand, g in df.groupby("brand", dropna=False):
#                     g = g.dropna(subset=[m])
#                     if g.empty or tcol not in g.columns:
#                         continue
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "brand": None if pd.isna(brand) else str(brand),
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })
#             else:
#                 g = df.dropna(subset=[m])
#                 if not g.empty and tcol in g.columns:
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })

#             out[block_key] = {
#                 "measure": m,
#                 "by_brand": rows if "brand" in df.columns else None,
#                 "overall": None if "brand" in df.columns else rows[0] if rows else None,
#             }

#         return out
#     # def build_llm_payload(df: pd.DataFrame, meta: dict, intent: dict) -> dict:
#     #     payload = {
#     #         "mode": meta.get("mode"),
#     #         "chart_type": meta.get("chart_type"),
#     #         "dims": meta.get("dims") or [],
#     #         "filters": meta.get("filters") or {},
#     #         "window": meta.get("window") or {},
#     #         "measure": meta.get("measure"),
#     #         # "table_data":{"brand":{Alpha:{min_sales:,monthofmaxsales date},max_sales:,maxsales month date}}}
#     #     }

#     #     if (meta.get("chart_type") == "line"):
#     #         payload["table_data"] = build_line_table_data(df, meta)
         
#     #     dims = [d for d in (meta.get("dims") or []) if d != "date"]
#     #     measure_hint = str(meta.get("measure") or "")
#     #     # print([for i in df.iterrows()])
#     #     if meta.get("chart_type")=="bar" and meta.get("mode")==None:
#     #         payload["table_data"]=df.to_json(orient="records")
#     #         print(payload)
#     #     #     payload["table_data"]=

#     #     # --- ✅ Capture YoY details ---
#     #     if measure_hint in ("value_yoy", "unit_yoy"):
#     #         base_measure = "value_sales" if "value" in measure_hint else "unit_sales"
#     #         curr_col = f"{base_measure}_curr"
#     #         prev_col = f"{base_measure}_prev"
#     #         yoy_col  = measure_hint

#     #         if all(c in df.columns for c in [curr_col, prev_col, yoy_col]):
#     #             yoy_records = []
#     #             for _, r in df[dims + [curr_col, prev_col, yoy_col]].iterrows():
#     #                 rec = {d: r[d] for d in dims}
#     #                 rec.update({
#     #                     "curr": r[curr_col],
#     #                     "prev": r[prev_col],
#     #                     "yoy_pct": r[yoy_col],
#     #                 })
#     #                 yoy_records.append(rec)

#     #             payload["yoy_details"] = {
#     #                 "base_measure": base_measure,
#     #                 "records": yoy_records,
#     #                 "prev_window": meta.get("prev_window") or (meta.get("debug", {}) or {}).get("prev_window"),
#     #             }

#     #     # --- ✅ Capture MAT compare details ---
#     #     if (meta.get("mode") == "MAT_COMPARE") or ("mat_compare" in meta):
#     #         mc = meta.get("mat_compare", {}) or {}
#     #         label_col = "mat_label" if "mat_label" in df.columns else None
#     #         base_measure = meta.get("measure") or "value_sales"

#     #         group_by = []
#     #         if label_col: group_by.append(label_col)
#     #         if "brand" in df.columns: group_by.append("brand")
#     #         for d in dims:
#     #             if d not in group_by: group_by.append(d)

#     #         mat_records = []
#     #         if base_measure in df.columns and group_by:
#     #             grouped = df.groupby(group_by, dropna=False)[base_measure].sum().reset_index()
#     #             mat_records = grouped.to_dict(orient="records")

#     #         payload["mat_details"] = {
#     #             "measure": base_measure,
#     #             "anchor_month": mc.get("anchor_month"),
#     #             "years": mc.get("years") or [],
#     #             "labels": mc.get("labels") or [],
#     #             "records": mat_records,
#     #         }

#     #     return payload

    


#     import pandas as pd
#     import numpy as np

#     def build_llm_payload(out_df: pd.DataFrame, meta: dict) -> dict:
#         df = out_df.copy()
#         chart_type = str(meta.get("chart_type") or "").lower()
#         dims       = list(meta.get("dims") or [])
#         filters    = dict(meta.get("filters") or {})
#         window     = dict(meta.get("window") or {})
#         measure    = str(meta.get("measure") or "value_sales")
#         mode_raw   = str(meta.get("mode") or "").upper()
#         periods=meta.get("periods")
#         # print("DEBUG>>>")
#         # print(mode_raw)
#         if mode_raw=='_YOY':
#             mode_raw=mode_raw.replace("_","")

#         # print(periods)
        

#         # ---------- normalize mode ----------
#         if mode_raw in ("MAT_COMPARE", "YTD"):
#             mode_norm = mode_raw
#         else:
#             if chart_type == "line":   mode_norm = "LINE"
#             elif chart_type == "bar":  mode_norm = "BAR"
#             elif chart_type == "table":mode_norm = "TABLE"
#             else:                      mode_norm = "CUSTOM"

#         # ---------- ensure time cols ----------
#         time_col = None
#         if "date" in df.columns:
#             time_col = "date"
#             with pd.option_context("mode.chained_assignment", None):
#                 df["date"] = pd.to_datetime(df["date"], errors="coerce")
#                 df["month_label"] = df["date"].dt.strftime("%b %Y")
#                 df["month_iso"]   = df["date"].dt.to_period("M").astype(str)

#         # ---------- small sample ----------
#         sample_cols = [c for c in df.columns if c in
#                     ["date","month_label","month_iso","brand","category","market",
#                         "value_sales","unit_sales","share",
#                         "value_sales_curr","value_sales_prev","value_yoy",
#                         "unit_sales_curr","unit_sales_prev","unit_yoy",
#                         "value_mom","unit_mom"]]
#         table_sample = df[sample_cols].head(6).to_dict(orient="records") if sample_cols else []

#         # helper: pick a base measure sensibly
#         def _pick_base_measure(frame: pd.DataFrame) -> str | None:
#             for c in ("value_sales","unit_sales"):
#                 if c in frame.columns:
#                     return c
#             num = frame.select_dtypes(include=[np.number]).columns.tolist()
#             return num[0] if num else None

#         # ---------- TREND (unchanged) ----------
#         trend_block = None
#         if chart_type == "line" and time_col is not None:
#             base_measure = _pick_base_measure(df)
#             by_brand = []
#             if base_measure is not None:
#                 if "brand" in df.columns:
#                     for b, g in df.groupby("brand", dropna=False):
#                         g = g.dropna(subset=[base_measure])
#                         if g.empty: continue
#                         rmin = g.loc[g[base_measure].idxmin()]
#                         rmax = g.loc[g[base_measure].idxmax()]
#                         by_brand.append({
#                             "brand": b if pd.notna(b) else "Unknown",
#                             "min":  {"value": float(rmin[base_measure]),
#                                     "period": str(rmin.get("month_iso") or ""),
#                                     "label":  str(rmin.get("month_label") or "")},
#                             "max":  {"value": float(rmax[base_measure]),
#                                     "period": str(rmax.get("month_iso") or ""),
#                                     "label":  str(rmax.get("month_label") or "")},
#                         })
#                 g = df.dropna(subset=[base_measure])
#                 overall = None
#                 if not g.empty:
#                     rmin = g.loc[g[base_measure].idxmin()]
#                     rmax = g.loc[g[base_measure].idxmax()]
#                     overall = {
#                         "min":  {"value": float(rmin[base_measure]),
#                                 "period": str(rmin.get("month_iso") or ""),
#                                 "label":  str(rmin.get("month_label") or "")},
#                         "max":  {"value": float(rmax[base_measure]),
#                                 "period": str(rmax.get("month_iso") or ""),
#                                 "label":  str(rmax.get("month_label") or "")},
#                     }
#                 trend_block = {"measure": base_measure, "by_brand": by_brand, "overall": overall}
#                 # print(trend_block)

#         # ---------- YoY (unchanged; now explicit) ----------
#         # print(meta)
#         yoy_block = None
#         if {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns) or \
#         {"unit_sales_curr","unit_sales_prev","unit_yoy"}.issubset(df.columns):

#             use_value = {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns)
#             curr_col  = "value_sales_curr" if use_value else "unit_sales_curr"
#             prev_col  = "value_sales_prev" if use_value else "unit_sales_prev"
#             yoy_col   = "value_yoy"        if use_value else "unit_yoy"

#             group_dims = [d for d in ("brand","category","market","channel") if d in df.columns]

#             tmp = df[group_dims + [curr_col, prev_col, yoy_col]].copy()
#             # print(df)
#             # print(f"filters:{filters}")
#             # print(tmp)
#             # if not tmp.empty:
#             #     tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             if group_dims:  # only group if dimensions exist
#                 tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             else:
#                 tmp = tmp.sum(numeric_only=True).to_frame().T.reset_index(drop=True)

#             items = []
#             for _, r in tmp.iterrows():
#                 item = {
#                     "curr": float(r[curr_col]) if pd.notna(r[curr_col]) else None,
#                     "prev": float(r[prev_col]) if pd.notna(r[prev_col]) else None,
#                     "yoy_pct": float(r[yoy_col]) if pd.notna(r[yoy_col]) else None,
#                 }
#                 for d in group_dims:
#                     item[d] = r[d] if d in r and pd.notna(r[d]) else None
#                 items.append(item)

#             yoy_block = {"measure_type": "value" if use_value else "unit", "items": items}
#         # print(yoy_block)
        

#         # # ---------- MAT compare (unchanged) ----------
#         from datetime import datetime
#         mat_block = None
#         mat_info = meta.get("mat_compare")
#         if isinstance(mat_info, dict) and "labels" in mat_info:
#             label_col = "mat_label" if "mat_label" in df.columns else None
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None
#             items = []
#             if label_col and base_measure:
#                 # print(label_col)
#                 agg = df.groupby(label_col, dropna=False)[base_measure].sum().reset_index()
#                 for _, r in agg.iterrows():
#                     items.append({"label": str(r[label_col]), "total": float(r[base_measure])})
#             mat_block = {"items": items, "anchor_month": mat_info.get("anchor_month")}
#         # for i in items[]
#         # for i in items:
            
#         #     year=int(i['label'].replace("MAT","").strip())
#         #     # print(year)
#         #     end=pd.to_datetime(window['end'])
#         #     end=end.replace(year=year)
#         #     # print(end)
#         #     start=end-pd.DateOffset(months=11)
#         #     # print(start)
#         # print(meta)
#         # print(meta)
#         if meta.get('periods') is not None:
#             for i in range(0,len(meta['periods'])):
#                 meta['periods'][i].update(out_df.to_dict(orient="records")[i])
#             # print("METAAAAAA DATA:",meta)
#             # print(mat_block)
        
#             # print(meta['periods'])

#             sorted_periods=sorted(meta['periods'], key=lambda x: x['value_sales'],reverse=True)
#             for i,j in enumerate(sorted_periods):
#                 meta['periods'][i].update({'rank':i+1})
#             # print(meta)

#             # print("SORTED PERIODS:",meta)
            





#         # ---------- BAR / topN (unchanged) ----------
#         bar_block = None
#         if chart_type == "bar":
#             non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
#             xcat = None
#             for c in ["brand","category","market","channel","segment","manufacturer"]:
#                 if c in non_numeric: xcat = c; break
#             if xcat is None and non_numeric: xcat = non_numeric[0]
#             ycols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
#             prefer_y = [c for c in ["value_sales","unit_sales","value_yoy","unit_yoy"] if c in ycols]
#             y = prefer_y[0] if prefer_y else (ycols[0] if ycols else None)
#             items = []
#             if xcat and y:
#                 tmp = df[[xcat, y]].copy().groupby(xcat, dropna=False)[y].sum().reset_index()
#                 tmp = tmp.sort_values(y, ascending=False, na_position="last")
#                 for i, r in enumerate(tmp.itertuples(index=False), start=1):
#                     items.append({"rank": i, "label": getattr(r, xcat), "value": float(getattr(r, y))})
#                 bar_block = {"x": xcat, "y": y, "items": items}

#         # ---------- NEW: MoM block (per brand + overall) ----------
#         mom_block = None
#         if time_col is not None:
#             # choose measure for MoM (value preferred)
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None

#             # see if MoM column already exists
#             mom_col = "value_mom" if "value_mom" in df.columns else \
#                     "unit_mom"  if "unit_mom"  in df.columns else None

#             def _series_items(frame: pd.DataFrame) -> list[dict]:
#                 f = frame.copy()
#                 # Sort by time
#                 f = f.sort_values("month_iso" if "month_iso" in f.columns else "date")
#                 # Compute MoM if missing
#                 if mom_col is None and base_measure in f.columns:
#                     f["_prev"] = f[base_measure].shift(1)
#                     with np.errstate(divide="ignore", invalid="ignore"):
#                         f["_mom"] = (f[base_measure] / f["_prev"]) - 1
#                 else:
#                     # use existing column
#                     f["_mom"] = f[mom_col]
#                     if base_measure in f.columns:
#                         f["_prev"] = f[base_measure].shift(1)

#                 items = []
#                 for _, r in f.iterrows():
#                     period = str(r.get("month_iso") or (r["date"].to_period("M").strftime("%Y-%m")
#                                                         if pd.notna(r.get("date")) else ""))
#                     label  = str(r.get("month_label") or "")
#                     mom_pct = r.get("_mom")
#                     curr = r.get(base_measure) if base_measure in f.columns else None
#                     prev = r.get("_prev")
#                     if pd.isna(mom_pct):   mom_pct = None
#                     if pd.isna(curr):      curr = None
#                     if pd.isna(prev):      prev = None
#                     items.append({"period": period, "label": label,
#                                 "mom_pct": float(mom_pct) if mom_pct is not None else None,
#                                 "curr": float(curr) if curr is not None else None,
#                                 "prev": float(prev) if prev is not None else None})
#                 # keep only rows where mom is computed or exists
#                 return [it for it in items if it["mom_pct"] is not None]

#             by_brand = []
#             if "brand" in df.columns:
#                 for b, g in df.groupby("brand", dropna=False):
#                     ser = _series_items(g)
#                     if ser:
#                         by_brand.append({"brand": b if pd.notna(b) else "Unknown", "series": ser})

#             overall = None
#             ser_all = _series_items(df)
#             if ser_all:
#                 overall = {"series": ser_all}

#             if by_brand or overall:
#                 mom_block = {
#                     "measure": base_measure or ("value_sales" if mom_col == "value_mom" else "unit_sales"),
#                     "by_brand": by_brand,
#                     "overall": overall
#                 }

#         # ---------- assemble ----------
#         # if meta['periods'] is not None:

#         payload = {
#             "mode": mode_norm,
#             "measure": measure,
#             "window": window,
#             "dims": [d for d in dims if d != "date"],
#             "filters": filters,
#             # "table_sample": table_sample,
#         }
#         if mat_block is not None:
#             # print(meta)
#             mat_block=meta
#         if trend_block is not None:     payload["trend"] = trend_block
#         if yoy_block is not None:       payload["yoy"] = yoy_block
#         if mat_block is not None:       payload["mat_compare"] = mat_block
#         if bar_block is not None:       payload["bar"] = bar_block
#         if mom_block is not None:       payload["mom"] = mom_block
#         # print(mat_block)
#         if mat_block is not None:
#             # payload['items']=payload['periods']
#             del payload['bar']
#         # print(result["meta"])
#         # if mode_raw=="MAT_YOY" or mode_raw=="YTD_YOY"  or mode_raw=="YOY":
#         payload['calculation_mode']=mode_raw.lower()
#         if "total" in payload['calculation_mode']:
#             payload.pop('mom')
#             # print(payload.keys())
#         import re

#         total_pattern = re.compile(r"\b(total|overall|aggregate|grand\s*total|sum|cumulative|combined|net\s+sales)\b", re.IGNORECASE)
#         trend_pattern = re.compile(r"\b(trend|over\s+time|month[-\s]*wise|monthly|line\s*chart|last\s+\d+\s+months)\b", re.IGNORECASE)
#         if total_pattern.search(intent['raw_text']) and not trend_pattern.search(intent['raw_text']):
#            payload['calculation_mode']=f'total {measure}'

       

#         return payload
#     payload = build_llm_payload(result["data"], result["meta"])
#     # print(f"{attach_insights(payload)}")
#     payload=attach_insights(payload)
#     print(payload)
#     # print(intent['raw_text'])
    

#     # import pandas as pd

  

#     # print(build_llm_payload(result["data"],result["meta"]))


#     out_df, meta = result["data"], result["meta"]
#     # print(f"{result["meta"]}")
#     # print(f"DEBUG>>>> {out_df}")
#     insights=generate_simple_insights(out_df,meta)
#     aa={
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
        
#     }
#     # print(aa)
  

#     return {
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
#         "insights": payload['insights'],
#         # "derived": payload['derived'],
#     }
  
#     # intent_model = parse_user_text(body.question)

#     # # Build dict intent WITH original text so we can infer MAT/YTD
#     # intent = intent_to_dict(intent_model, original_text=body.question)

#     # # Safety: force mode if user text says MAT/YTD but converter didn't set it
#     # q = body.question.lower()
#     # tr = intent.get("time_range") or {}
#     # if "mode" not in tr:
#     #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#     #         tr["mode"] = "MAT"
#     #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#     #         tr["mode"] = "YTD"
#     # intent["time_range"] = tr if tr else None

#     # # Safety: treat "table + limit" as Top-N
#     # if intent.get("task") == "table" and intent.get("top_n"):
#     #     intent["task"] = "topn"

#     # # Safety: for Top-N, drop 'date' from dims
#     # if intent.get("task") == "topn":
#     #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     # df = _load_df(body.settings_path)
#     # result = run_pandas_intent(df, intent)
#     # out_df, meta = result["data"], result["meta"]

#     # bullets = []
#     # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
#     #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
#     #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
#     #     try:
#     #         b = best.iloc[0]
#     #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     #     try:
#     #         w = worst.iloc[0]
#     #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     # if "share" in out_df.columns and out_df["share"].notna().any():
#     #     latest_share = out_df.iloc[-1]["share"]
#     #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

#     # empty_hint = None
#     # if out_df.empty:
#     #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

#     # return {
#     #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
#     #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
#     #     "sql": None,
#     #     "meta": meta,                          # window actually used (dates)
#     #     "data": out_df.to_dict(orient="records"),
#     #     "columns": list(out_df.columns),
#     #     "insights": bullets[:3],
#     #     "empty_hint": empty_hint,
#     # }

# @app.post("/sql")
# def run_raw_sql(body: SqlBody):
#     # keep the raw SQL endpoint working exactly as before
#     df, meta = run_sql(body.sql, body.settings_path)
#     return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}















# backend/insights.py






#Working  code for table, chart, llm insights, not added time series functionality yet










# from fastapi import FastAPI, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Dict
# import json, yaml
# import pandas as pd
# import tempfile, os

# from backend.ingest.excel_ingest import ingest_excel
# from backend.sql.runner import run_sql, get_cfg

# # use pandas path (your parser + runner)
# from .nlp.parser import parse_user_text, intent_to_dict
# from .nlp.pandas_runner import run_pandas_intent
# from backend.insights import generate_simple_insights,attach_insights

# app = FastAPI(title="Nielsen Excel Q&A — Starter API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )

# class AskBody(BaseModel):
#     question: str
#     settings_path: str = "configs/settings.yaml"

# class SqlBody(BaseModel):
#     sql: str
#     settings_path: str = "configs/settings.yaml"

# # ---------- small cache so we don't reload same file repeatedly ----------
# _DF_CACHE: Dict[str, pd.DataFrame] = {}

# def _load_df(settings_path: str) -> pd.DataFrame:
#     """
#     Load & normalize the dataset using paths in settings.yaml.
#     Expected keys:
#       data:
#         excel_path: data/sample_nielsen_extended.xlsx
#         sheet_name: Sheet1
#     """
#     if settings_path in _DF_CACHE:
#         return _DF_CACHE[settings_path]

#     cfg = get_cfg(settings_path)
#     data_cfg = cfg.get("data", {})
#     excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
#     sheet_name = data_cfg.get("sheet_name", "Sheet1")

#     df = pd.read_excel(excel_path, sheet_name=sheet_name)
#     if "date" not in df.columns:
#         raise ValueError("Dataset must have a 'date' column")
#     df["date"] = pd.to_datetime(df["date"])
#     for c in ["brand", "category", "market", "channel"]:
#         if c in df.columns and df[c].dtype == object:
#             df[c] = df[c].astype(str).str.strip()

#     _DF_CACHE[settings_path] = df
#     return df

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/upload")
# async def upload_excel(
#     file: UploadFile = File(...),
#     mapper_json: str = json.dumps({
#         "date":"date","market":"market","channel":"channel","category":"category",
#         "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
#     }),
#     settings_path: str = "configs/settings.yaml"
# ):
#     content = await file.read()
#     tmp_dir = tempfile.gettempdir()
#     tmp_path = os.path.join(tmp_dir, file.filename)
#     with open(tmp_path, "wb") as f:
#         f.write(content)

#     mapper = json.loads(mapper_json)
#     info = ingest_excel(tmp_path, mapper, settings_path)

#     # bust cache so next /ask reloads fresh data for this settings_path
#     _DF_CACHE.pop(settings_path, None)

#     return {"status": "ok", "info": info}

# @app.post("/ask")
# @app.post("/ask")
# def ask(body: AskBody):
#     # inside /ask
#     intent_model = parse_user_text(body.question)
#     intent = intent_to_dict(intent_model, original_text=body.question)

#     # enforce mode from text if still missing
#     q = body.question.lower()
#     tr = intent.get("time_range") or {}
#     if "mode" not in tr:
#         if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#             tr["mode"] = "MAT"
#         elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#             tr["mode"] = "YTD"
#     intent["time_range"] = tr or None

#     # treat "table + limit" as Top-N and drop date
#     if intent.get("task") == "table" and intent.get("top_n"):
#         intent["task"] = "topn"
#     if intent.get("task") == "topn":
#         intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     df = _load_df(body.settings_path)
#     result = run_pandas_intent(df, intent)
#     # payload= build_llm_payload(result["data"], result["meta"])
#     # print(payload)
#     # print(result["meta"])
    

   

    

#     import pandas as pd
#     import numpy as np
#     import pandas as pd

#     def _pick_time_col(df: pd.DataFrame) -> str | None:
#         # prefer true datetime; fallbacks are ok too
#         for c in ["date", "month_date", "x_dt", "month"]:
#             if c in df.columns:
#                 return c
#         return None

#     def _format_period(val) -> str:
#         # output nice "Jan 2024" labels where possible
#         if isinstance(val, pd.Timestamp):
#             return val.to_period("M").strftime("%b %Y")
#         try:
#             ts = pd.to_datetime(val, errors="coerce")
#             if pd.notna(ts):
#                 return ts.to_period("M").strftime("%b %Y")
#         except Exception:
#             pass
#         return str(val)

#     def _pick_measure_for_line(df: pd.DataFrame, meta: dict) -> list[str]:
#         # choose the measure(s) to report
#         prefer = str(meta.get("measure") or "")
#         candidates = [m for m in ["value_sales", "unit_sales"] if m in df.columns]
#         if prefer and prefer in candidates:
#             return [prefer]
#         return candidates or []

#     def build_line_table_data(df: pd.DataFrame, meta: dict) -> dict:
#         """
#         Returns a dict ready to put under payload['table_data'] for line charts.
#         Structure:
#         {
#             "measure": "value_sales",
#             "by_brand": [
#             {"brand":"Alpha","min_value":..., "min_period":"...", "max_value":..., "max_period":"..."},
#             ...
#             ]
#         }
#         If no 'brand' column, returns "overall" with a single min/max row.
#         """
#         tcol = _pick_time_col(df)
#         measures = _pick_measure_for_line(df, meta)
#         out: dict = {"_time_col": tcol}  # small debug hint; remove if you don't want it

#         if not tcol or not measures:
#             return out  # nothing to do

#         # If both value & unit exist, we can emit both blocks
#         for m in measures:
#             block_key = m  # e.g. "value_sales"
#             rows = []

#             if "brand" in df.columns:
#                 for brand, g in df.groupby("brand", dropna=False):
#                     g = g.dropna(subset=[m])
#                     if g.empty or tcol not in g.columns:
#                         continue
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "brand": None if pd.isna(brand) else str(brand),
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })
#             else:
#                 g = df.dropna(subset=[m])
#                 if not g.empty and tcol in g.columns:
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })

#             out[block_key] = {
#                 "measure": m,
#                 "by_brand": rows if "brand" in df.columns else None,
#                 "overall": None if "brand" in df.columns else rows[0] if rows else None,
#             }

#         return out
#     # def build_llm_payload(df: pd.DataFrame, meta: dict, intent: dict) -> dict:
#     #     payload = {
#     #         "mode": meta.get("mode"),
#     #         "chart_type": meta.get("chart_type"),
#     #         "dims": meta.get("dims") or [],
#     #         "filters": meta.get("filters") or {},
#     #         "window": meta.get("window") or {},
#     #         "measure": meta.get("measure"),
#     #         # "table_data":{"brand":{Alpha:{min_sales:,monthofmaxsales date},max_sales:,maxsales month date}}}
#     #     }

#     #     if (meta.get("chart_type") == "line"):
#     #         payload["table_data"] = build_line_table_data(df, meta)
         
#     #     dims = [d for d in (meta.get("dims") or []) if d != "date"]
#     #     measure_hint = str(meta.get("measure") or "")
#     #     # print([for i in df.iterrows()])
#     #     if meta.get("chart_type")=="bar" and meta.get("mode")==None:
#     #         payload["table_data"]=df.to_json(orient="records")
#     #         print(payload)
#     #     #     payload["table_data"]=

#     #     # --- ✅ Capture YoY details ---
#     #     if measure_hint in ("value_yoy", "unit_yoy"):
#     #         base_measure = "value_sales" if "value" in measure_hint else "unit_sales"
#     #         curr_col = f"{base_measure}_curr"
#     #         prev_col = f"{base_measure}_prev"
#     #         yoy_col  = measure_hint

#     #         if all(c in df.columns for c in [curr_col, prev_col, yoy_col]):
#     #             yoy_records = []
#     #             for _, r in df[dims + [curr_col, prev_col, yoy_col]].iterrows():
#     #                 rec = {d: r[d] for d in dims}
#     #                 rec.update({
#     #                     "curr": r[curr_col],
#     #                     "prev": r[prev_col],
#     #                     "yoy_pct": r[yoy_col],
#     #                 })
#     #                 yoy_records.append(rec)

#     #             payload["yoy_details"] = {
#     #                 "base_measure": base_measure,
#     #                 "records": yoy_records,
#     #                 "prev_window": meta.get("prev_window") or (meta.get("debug", {}) or {}).get("prev_window"),
#     #             }

#     #     # --- ✅ Capture MAT compare details ---
#     #     if (meta.get("mode") == "MAT_COMPARE") or ("mat_compare" in meta):
#     #         mc = meta.get("mat_compare", {}) or {}
#     #         label_col = "mat_label" if "mat_label" in df.columns else None
#     #         base_measure = meta.get("measure") or "value_sales"

#     #         group_by = []
#     #         if label_col: group_by.append(label_col)
#     #         if "brand" in df.columns: group_by.append("brand")
#     #         for d in dims:
#     #             if d not in group_by: group_by.append(d)

#     #         mat_records = []
#     #         if base_measure in df.columns and group_by:
#     #             grouped = df.groupby(group_by, dropna=False)[base_measure].sum().reset_index()
#     #             mat_records = grouped.to_dict(orient="records")

#     #         payload["mat_details"] = {
#     #             "measure": base_measure,
#     #             "anchor_month": mc.get("anchor_month"),
#     #             "years": mc.get("years") or [],
#     #             "labels": mc.get("labels") or [],
#     #             "records": mat_records,
#     #         }

#     #     return payload

    




#     import pandas as pd
#     import numpy as np

#     def build_llm_payload(out_df: pd.DataFrame, meta: dict) -> dict:
#         df = out_df.copy()
#         chart_type = str(meta.get("chart_type") or "").lower()
#         dims       = list(meta.get("dims") or [])
#         filters    = dict(meta.get("filters") or {})
#         window     = dict(meta.get("window") or {})
#         measure    = str(meta.get("measure") or "value_sales")
#         mode_raw   = str(meta.get("mode") or "").upper()
#         periods=meta.get("periods")
#         # print("DEBUG>>>")
#         # print(mode_raw)
#         if mode_raw=='_YOY':
#             mode_raw=mode_raw.replace("_","")

#         # print(periods)
        

#         # ---------- normalize mode ----------
#         if mode_raw in ("MAT_COMPARE", "YTD"):
#             mode_norm = mode_raw
#         else:
#             if chart_type == "line":   mode_norm = "LINE"
#             elif chart_type == "bar":  mode_norm = "BAR"
#             elif chart_type == "table":mode_norm = "TABLE"
#             else:                      mode_norm = "CUSTOM"

#         # ---------- ensure time cols ----------
#         time_col = None
#         if "date" in df.columns:
#             time_col = "date"
#             with pd.option_context("mode.chained_assignment", None):
#                 df["date"] = pd.to_datetime(df["date"], errors="coerce")
#                 df["month_label"] = df["date"].dt.strftime("%b %Y")
#                 df["month_iso"]   = df["date"].dt.to_period("M").astype(str)

#         # ---------- small sample ----------
#         sample_cols = [c for c in df.columns if c in
#                     ["date","month_label","month_iso","brand","category","market",
#                         "value_sales","unit_sales","share",
#                         "value_sales_curr","value_sales_prev","value_yoy",
#                         "unit_sales_curr","unit_sales_prev","unit_yoy",
#                         "value_mom","unit_mom"]]
#         table_sample = df[sample_cols].head(6).to_dict(orient="records") if sample_cols else []

#         # helper: pick a base measure sensibly
#         def _pick_base_measure(frame: pd.DataFrame) -> str | None:
#             for c in ("value_sales","unit_sales"):
#                 if c in frame.columns:
#                     return c
#             num = frame.select_dtypes(include=[np.number]).columns.tolist()
#             return num[0] if num else None

#         # ---------- TREND (unchanged) ----------
#         trend_block = None
#         if chart_type == "line" and time_col is not None:
#             base_measure = _pick_base_measure(df)
#             by_brand = []
#             if base_measure is not None:
#                 if "brand" in df.columns:
#                     for b, g in df.groupby("brand", dropna=False):
#                         g = g.dropna(subset=[base_measure])
#                         if g.empty: continue
#                         rmin = g.loc[g[base_measure].idxmin()]
#                         rmax = g.loc[g[base_measure].idxmax()]
#                         by_brand.append({
#                             "brand": b if pd.notna(b) else "Unknown",
#                             "min":  {"value": float(rmin[base_measure]),
#                                     "period": str(rmin.get("month_iso") or ""),
#                                     "label":  str(rmin.get("month_label") or "")},
#                             "max":  {"value": float(rmax[base_measure]),
#                                     "period": str(rmax.get("month_iso") or ""),
#                                     "label":  str(rmax.get("month_label") or "")},
#                         })
#                 g = df.dropna(subset=[base_measure])
#                 overall = None
#                 if not g.empty:
#                     rmin = g.loc[g[base_measure].idxmin()]
#                     rmax = g.loc[g[base_measure].idxmax()]
#                     overall = {
#                         "min":  {"value": float(rmin[base_measure]),
#                                 "period": str(rmin.get("month_iso") or ""),
#                                 "label":  str(rmin.get("month_label") or "")},
#                         "max":  {"value": float(rmax[base_measure]),
#                                 "period": str(rmax.get("month_iso") or ""),
#                                 "label":  str(rmax.get("month_label") or "")},
#                     }
#                 trend_block = {"measure": base_measure, "by_brand": by_brand, "overall": overall}
#                 # print(trend_block)

#         # ---------- YoY (unchanged; now explicit) ----------
#         # print(meta)
#         yoy_block = None
#         if {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns) or \
#         {"unit_sales_curr","unit_sales_prev","unit_yoy"}.issubset(df.columns):

#             use_value = {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns)
#             curr_col  = "value_sales_curr" if use_value else "unit_sales_curr"
#             prev_col  = "value_sales_prev" if use_value else "unit_sales_prev"
#             yoy_col   = "value_yoy"        if use_value else "unit_yoy"

#             group_dims = [d for d in ("brand","category","market","channel") if d in df.columns]

#             tmp = df[group_dims + [curr_col, prev_col, yoy_col]].copy()
#             # print(df)
#             # print(f"filters:{filters}")
#             # print(tmp)
#             # if not tmp.empty:
#             #     tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             if group_dims:  # only group if dimensions exist
#                 tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             else:
#                 tmp = tmp.sum(numeric_only=True).to_frame().T.reset_index(drop=True)

#             items = []
#             for _, r in tmp.iterrows():
#                 item = {
#                     "curr": float(r[curr_col]) if pd.notna(r[curr_col]) else None,
#                     "prev": float(r[prev_col]) if pd.notna(r[prev_col]) else None,
#                     "yoy_pct": float(r[yoy_col]) if pd.notna(r[yoy_col]) else None,
#                 }
#                 for d in group_dims:
#                     item[d] = r[d] if d in r and pd.notna(r[d]) else None
#                 items.append(item)

#             yoy_block = {"measure_type": "value" if use_value else "unit", "items": items}
#         # print(yoy_block)
        

#         # # ---------- MAT compare (unchanged) ----------
#         from datetime import datetime
#         mat_block = None
#         mat_info = meta.get("mat_compare")
#         if isinstance(mat_info, dict) and "labels" in mat_info:
#             label_col = "mat_label" if "mat_label" in df.columns else None
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None
#             items = []
#             if label_col and base_measure:
#                 # print(label_col)
#                 agg = df.groupby(label_col, dropna=False)[base_measure].sum().reset_index()
#                 for _, r in agg.iterrows():
#                     items.append({"label": str(r[label_col]), "total": float(r[base_measure])})
#             mat_block = {"items": items, "anchor_month": mat_info.get("anchor_month")}
#         # for i in items[]
#         # for i in items:
            
#         #     year=int(i['label'].replace("MAT","").strip())
#         #     # print(year)
#         #     end=pd.to_datetime(window['end'])
#         #     end=end.replace(year=year)
#         #     # print(end)
#         #     start=end-pd.DateOffset(months=11)
#         #     # print(start)
#         # print(meta)
#         # print(meta)
#         if meta.get('periods') is not None:
#             for i in range(0,len(meta['periods'])):
#                 meta['periods'][i].update(out_df.to_dict(orient="records")[i])
#             # print("METAAAAAA DATA:",meta)
#             # print(mat_block)
        
#             # print(meta['periods'])

#             sorted_periods=sorted(meta['periods'], key=lambda x: x['value_sales'],reverse=True)
#             for i,j in enumerate(sorted_periods):
#                 meta['periods'][i].update({'rank':i+1})
#             # print(meta)

#             # print("SORTED PERIODS:",meta)
            





#         # ---------- BAR / topN (unchanged) ----------
#         bar_block = None
#         if chart_type == "bar":
#             non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
#             xcat = None
#             for c in ["brand","category","market","channel","segment","manufacturer"]:
#                 if c in non_numeric: xcat = c; break
#             if xcat is None and non_numeric: xcat = non_numeric[0]
#             ycols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
#             prefer_y = [c for c in ["value_sales","unit_sales","value_yoy","unit_yoy"] if c in ycols]
#             y = prefer_y[0] if prefer_y else (ycols[0] if ycols else None)
#             items = []
#             if xcat and y:
#                 tmp = df[[xcat, y]].copy().groupby(xcat, dropna=False)[y].sum().reset_index()
#                 tmp = tmp.sort_values(y, ascending=False, na_position="last")
#                 for i, r in enumerate(tmp.itertuples(index=False), start=1):
#                     items.append({"rank": i, "label": getattr(r, xcat), "value": float(getattr(r, y))})
#                 bar_block = {"x": xcat, "y": y, "items": items}

#         # ---------- NEW: MoM block (per brand + overall) ----------
#         mom_block = None
#         if time_col is not None:
#             # choose measure for MoM (value preferred)
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None

#             # see if MoM column already exists
#             mom_col = "value_mom" if "value_mom" in df.columns else \
#                     "unit_mom"  if "unit_mom"  in df.columns else None

#             def _series_items(frame: pd.DataFrame) -> list[dict]:
#                 f = frame.copy()
#                 # Sort by time
#                 f = f.sort_values("month_iso" if "month_iso" in f.columns else "date")
#                 # Compute MoM if missing
#                 if mom_col is None and base_measure in f.columns:
#                     f["_prev"] = f[base_measure].shift(1)
#                     with np.errstate(divide="ignore", invalid="ignore"):
#                         f["_mom"] = (f[base_measure] / f["_prev"]) - 1
#                 else:
#                     # use existing column
#                     f["_mom"] = f[mom_col]
#                     if base_measure in f.columns:
#                         f["_prev"] = f[base_measure].shift(1)

#                 items = []
#                 for _, r in f.iterrows():
#                     period = str(r.get("month_iso") or (r["date"].to_period("M").strftime("%Y-%m")
#                                                         if pd.notna(r.get("date")) else ""))
#                     label  = str(r.get("month_label") or "")
#                     mom_pct = r.get("_mom")
#                     curr = r.get(base_measure) if base_measure in f.columns else None
#                     prev = r.get("_prev")
#                     if pd.isna(mom_pct):   mom_pct = None
#                     if pd.isna(curr):      curr = None
#                     if pd.isna(prev):      prev = None
#                     items.append({"period": period, "label": label,
#                                 "mom_pct": float(mom_pct) if mom_pct is not None else None,
#                                 "curr": float(curr) if curr is not None else None,
#                                 "prev": float(prev) if prev is not None else None})
#                 # keep only rows where mom is computed or exists
#                 return [it for it in items if it["mom_pct"] is not None]

#             by_brand = []
#             if "brand" in df.columns:
#                 for b, g in df.groupby("brand", dropna=False):
#                     ser = _series_items(g)
#                     if ser:
#                         by_brand.append({"brand": b if pd.notna(b) else "Unknown", "series": ser})

#             overall = None
#             ser_all = _series_items(df)
#             if ser_all:
#                 overall = {"series": ser_all}

#             if by_brand or overall:
#                 mom_block = {
#                     "measure": base_measure or ("value_sales" if mom_col == "value_mom" else "unit_sales"),
#                     "by_brand": by_brand,
#                     "overall": overall
#                 }

#         # ---------- assemble ----------
#         # if meta['periods'] is not None:

#         payload = {
#             "mode": mode_norm,
#             "measure": measure,
#             "window": window,
#             "dims": [d for d in dims if d != "date"],
#             "filters": filters,
#             # "table_sample": table_sample,
#         }
#         if mat_block is not None:
#             # print(meta)
#             mat_block=meta
#         if trend_block is not None:     payload["trend"] = trend_block
#         if yoy_block is not None:       payload["yoy"] = yoy_block
#         if mat_block is not None:       payload["mat_compare"] = mat_block
#         if bar_block is not None:       payload["bar"] = bar_block
#         if mom_block is not None:       payload["mom"] = mom_block
#         # print(mat_block)
#         if mat_block is not None:
#             # payload['items']=payload['periods']
#             del payload['bar']
#         # print(result["meta"])
#         # if mode_raw=="MAT_YOY" or mode_raw=="YTD_YOY"  or mode_raw=="YOY":
#         payload['calculation_mode']=mode_raw.lower()
#         if "total" in payload['calculation_mode']:
#             payload.pop('mom')
#             # print(payload.keys())
#         import re

#         total_pattern = re.compile(r"\b(total|overall|aggregate|grand\s*total|sum|cumulative|combined|net\s+sales)\b", re.IGNORECASE)
#         trend_pattern = re.compile(r"\b(trend|over\s+time|month[-\s]*wise|monthly|line\s*chart|last\s+\d+\s+months)\b", re.IGNORECASE)
#         if total_pattern.search(intent['raw_text']) and not trend_pattern.search(intent['raw_text']):
#            payload['calculation_mode']=f'total {measure}'

       

#         return payload
#     payload = build_llm_payload(result["data"], result["meta"])
#     # print(f"{attach_insights(payload)}")
#     payload=attach_insights(payload)
#     print(f"The payload>>>>>>>>>>>>>>>>>>>>>>>>>>>")
#     print(payload)
#     print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
#     # print(intent['raw_text'])
    

#     # import pandas as pd

  

#     # print(build_llm_payload(result["data"],result["meta"]))


#     out_df, meta = result["data"], result["meta"]
#     # print(f"{result["meta"]}")
#     # print(f"DEBUG>>>> {out_df}")
#     insights=generate_simple_insights(out_df,meta)
#     aa={
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
        
#     }
#     # print(aa)
  

#     return {
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
#         "insights": payload['insights'],
#         # "derived": payload['derived'],
#     }
  
#     # intent_model = parse_user_text(body.question)

#     # # Build dict intent WITH original text so we can infer MAT/YTD
#     # intent = intent_to_dict(intent_model, original_text=body.question)

#     # # Safety: force mode if user text says MAT/YTD but converter didn't set it
#     # q = body.question.lower()
#     # tr = intent.get("time_range") or {}
#     # if "mode" not in tr:
#     #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#     #         tr["mode"] = "MAT"
#     #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#     #         tr["mode"] = "YTD"
#     # intent["time_range"] = tr if tr else None

#     # # Safety: treat "table + limit" as Top-N
#     # if intent.get("task") == "table" and intent.get("top_n"):
#     #     intent["task"] = "topn"

#     # # Safety: for Top-N, drop 'date' from dims
#     # if intent.get("task") == "topn":
#     #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     # df = _load_df(body.settings_path)
#     # result = run_pandas_intent(df, intent)
#     # out_df, meta = result["data"], result["meta"]

#     # bullets = []
#     # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
#     #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
#     #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
#     #     try:
#     #         b = best.iloc[0]
#     #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     #     try:
#     #         w = worst.iloc[0]
#     #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     # if "share" in out_df.columns and out_df["share"].notna().any():
#     #     latest_share = out_df.iloc[-1]["share"]
#     #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

#     # empty_hint = None
#     # if out_df.empty:
#     #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

#     # return {
#     #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
#     #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
#     #     "sql": None,
#     #     "meta": meta,                          # window actually used (dates)
#     #     "data": out_df.to_dict(orient="records"),
#     #     "columns": list(out_df.columns),
#     #     "insights": bullets[:3],
#     #     "empty_hint": empty_hint,
#     # }

# @app.post("/sql")
# def run_raw_sql(body: SqlBody):
#     # keep the raw SQL endpoint working exactly as before
#     df, meta = run_sql(body.sql, body.settings_path)
#     return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}











#Working time series forecasting code





# from fastapi import FastAPI, UploadFile, File
# from fastapi.middleware.cors import CORSMiddleware
# from backend.forecasting_api import router as forecasting_router
# from pydantic import BaseModel
# from typing import Dict
# import json, yaml
# import pandas as pd
# import tempfile, os

# from backend.ingest.excel_ingest import ingest_excel
# from backend.sql.runner import run_sql, get_cfg

# # use pandas path (your parser + runner)
# from .nlp.parser import parse_user_text, intent_to_dict
# from .nlp.pandas_runner import run_pandas_intent
# from backend.insights import generate_simple_insights,attach_insights

# app = FastAPI(title="Nielsen Excel Q&A — Starter API")
# app.include_router(forecasting_router)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )

# class AskBody(BaseModel):
#     question: str
#     settings_path: str = "configs/settings.yaml"

# class SqlBody(BaseModel):
#     sql: str
#     settings_path: str = "configs/settings.yaml"

# # ---------- small cache so we don't reload same file repeatedly ----------
# _DF_CACHE: Dict[str, pd.DataFrame] = {}

# def _load_df(settings_path: str) -> pd.DataFrame:
#     """
#     Load & normalize the dataset using paths in settings.yaml.
#     Expected keys:
#       data:
#         excel_path: data/sample_nielsen_extended.xlsx
#         sheet_name: Sheet1
#     """
#     if settings_path in _DF_CACHE:
#         return _DF_CACHE[settings_path]

#     cfg = get_cfg(settings_path)
#     data_cfg = cfg.get("data", {})
#     excel_path = data_cfg.get("excel_path", "data/sample_nielsen_extended.xlsx")
#     sheet_name = data_cfg.get("sheet_name", "Sheet1")

#     df = pd.read_excel(excel_path, sheet_name=sheet_name)
#     if "date" not in df.columns:
#         raise ValueError("Dataset must have a 'date' column")
#     df["date"] = pd.to_datetime(df["date"])
#     for c in ["brand", "category", "market", "channel"]:
#         if c in df.columns and df[c].dtype == object:
#             df[c] = df[c].astype(str).str.strip()

#     _DF_CACHE[settings_path] = df
#     return df

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/upload")
# async def upload_excel(
#     file: UploadFile = File(...),
#     mapper_json: str = json.dumps({
#         "date":"date","market":"market","channel":"channel","category":"category",
#         "brand":"brand","value_sales":"value_sales","unit_sales":"unit_sales","share":"share"
#     }),
#     settings_path: str = "configs/settings.yaml"
# ):
#     content = await file.read()
#     tmp_dir = tempfile.gettempdir()
#     tmp_path = os.path.join(tmp_dir, file.filename)
#     with open(tmp_path, "wb") as f:
#         f.write(content)

#     mapper = json.loads(mapper_json)
#     info = ingest_excel(tmp_path, mapper, settings_path)

#     # bust cache so next /ask reloads fresh data for this settings_path
#     _DF_CACHE.pop(settings_path, None)

#     return {"status": "ok", "info": info}

# @app.post("/ask")
# @app.post("/ask")
# def ask(body: AskBody):
#     # inside /ask
#     intent_model = parse_user_text(body.question)
#     intent = intent_to_dict(intent_model, original_text=body.question)

#     # enforce mode from text if still missing
#     q = body.question.lower()
#     tr = intent.get("time_range") or {}
#     if "mode" not in tr:
#         if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#             tr["mode"] = "MAT"
#         elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#             tr["mode"] = "YTD"
#     intent["time_range"] = tr or None

#     # treat "table + limit" as Top-N and drop date
#     if intent.get("task") == "table" and intent.get("top_n"):
#         intent["task"] = "topn"
#     if intent.get("task") == "topn":
#         intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     df = _load_df(body.settings_path)
#     result = run_pandas_intent(df, intent)
#     # payload= build_llm_payload(result["data"], result["meta"])
#     # print(payload)
#     # print(result["meta"])
    

   

    

#     import pandas as pd
#     import numpy as np
#     import pandas as pd

#     def _pick_time_col(df: pd.DataFrame) -> str | None:
#         # prefer true datetime; fallbacks are ok too
#         for c in ["date", "month_date", "x_dt", "month"]:
#             if c in df.columns:
#                 return c
#         return None

#     def _format_period(val) -> str:
#         # output nice "Jan 2024" labels where possible
#         if isinstance(val, pd.Timestamp):
#             return val.to_period("M").strftime("%b %Y")
#         try:
#             ts = pd.to_datetime(val, errors="coerce")
#             if pd.notna(ts):
#                 return ts.to_period("M").strftime("%b %Y")
#         except Exception:
#             pass
#         return str(val)

#     def _pick_measure_for_line(df: pd.DataFrame, meta: dict) -> list[str]:
#         # choose the measure(s) to report
#         prefer = str(meta.get("measure") or "")
#         candidates = [m for m in ["value_sales", "unit_sales"] if m in df.columns]
#         if prefer and prefer in candidates:
#             return [prefer]
#         return candidates or []

#     def build_line_table_data(df: pd.DataFrame, meta: dict) -> dict:
#         """
#         Returns a dict ready to put under payload['table_data'] for line charts.
#         Structure:
#         {
#             "measure": "value_sales",
#             "by_brand": [
#             {"brand":"Alpha","min_value":..., "min_period":"...", "max_value":..., "max_period":"..."},
#             ...
#             ]
#         }
#         If no 'brand' column, returns "overall" with a single min/max row.
#         """
#         tcol = _pick_time_col(df)
#         measures = _pick_measure_for_line(df, meta)
#         out: dict = {"_time_col": tcol}  # small debug hint; remove if you don't want it

#         if not tcol or not measures:
#             return out  # nothing to do

#         # If both value & unit exist, we can emit both blocks
#         for m in measures:
#             block_key = m  # e.g. "value_sales"
#             rows = []

#             if "brand" in df.columns:
#                 for brand, g in df.groupby("brand", dropna=False):
#                     g = g.dropna(subset=[m])
#                     if g.empty or tcol not in g.columns:
#                         continue
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "brand": None if pd.isna(brand) else str(brand),
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })
#             else:
#                 g = df.dropna(subset=[m])
#                 if not g.empty and tcol in g.columns:
#                     idx_min = g[m].idxmin()
#                     idx_max = g[m].idxmax()
#                     rows.append({
#                         "min_value": float(g.loc[idx_min, m]),
#                         "min_period": _format_period(g.loc[idx_min, tcol]),
#                         "max_value": float(g.loc[idx_max, m]),
#                         "max_period": _format_period(g.loc[idx_max, tcol]),
#                     })

#             out[block_key] = {
#                 "measure": m,
#                 "by_brand": rows if "brand" in df.columns else None,
#                 "overall": None if "brand" in df.columns else rows[0] if rows else None,
#             }

#         return out
#     # def build_llm_payload(df: pd.DataFrame, meta: dict, intent: dict) -> dict:
#     #     payload = {
#     #         "mode": meta.get("mode"),
#     #         "chart_type": meta.get("chart_type"),
#     #         "dims": meta.get("dims") or [],
#     #         "filters": meta.get("filters") or {},
#     #         "window": meta.get("window") or {},
#     #         "measure": meta.get("measure"),
#     #         # "table_data":{"brand":{Alpha:{min_sales:,monthofmaxsales date},max_sales:,maxsales month date}}}
#     #     }

#     #     if (meta.get("chart_type") == "line"):
#     #         payload["table_data"] = build_line_table_data(df, meta)
         
#     #     dims = [d for d in (meta.get("dims") or []) if d != "date"]
#     #     measure_hint = str(meta.get("measure") or "")
#     #     # print([for i in df.iterrows()])
#     #     if meta.get("chart_type")=="bar" and meta.get("mode")==None:
#     #         payload["table_data"]=df.to_json(orient="records")
#     #         print(payload)
#     #     #     payload["table_data"]=

#     #     # --- ✅ Capture YoY details ---
#     #     if measure_hint in ("value_yoy", "unit_yoy"):
#     #         base_measure = "value_sales" if "value" in measure_hint else "unit_sales"
#     #         curr_col = f"{base_measure}_curr"
#     #         prev_col = f"{base_measure}_prev"
#     #         yoy_col  = measure_hint

#     #         if all(c in df.columns for c in [curr_col, prev_col, yoy_col]):
#     #             yoy_records = []
#     #             for _, r in df[dims + [curr_col, prev_col, yoy_col]].iterrows():
#     #                 rec = {d: r[d] for d in dims}
#     #                 rec.update({
#     #                     "curr": r[curr_col],
#     #                     "prev": r[prev_col],
#     #                     "yoy_pct": r[yoy_col],
#     #                 })
#     #                 yoy_records.append(rec)

#     #             payload["yoy_details"] = {
#     #                 "base_measure": base_measure,
#     #                 "records": yoy_records,
#     #                 "prev_window": meta.get("prev_window") or (meta.get("debug", {}) or {}).get("prev_window"),
#     #             }

#     #     # --- ✅ Capture MAT compare details ---
#     #     if (meta.get("mode") == "MAT_COMPARE") or ("mat_compare" in meta):
#     #         mc = meta.get("mat_compare", {}) or {}
#     #         label_col = "mat_label" if "mat_label" in df.columns else None
#     #         base_measure = meta.get("measure") or "value_sales"

#     #         group_by = []
#     #         if label_col: group_by.append(label_col)
#     #         if "brand" in df.columns: group_by.append("brand")
#     #         for d in dims:
#     #             if d not in group_by: group_by.append(d)

#     #         mat_records = []
#     #         if base_measure in df.columns and group_by:
#     #             grouped = df.groupby(group_by, dropna=False)[base_measure].sum().reset_index()
#     #             mat_records = grouped.to_dict(orient="records")

#     #         payload["mat_details"] = {
#     #             "measure": base_measure,
#     #             "anchor_month": mc.get("anchor_month"),
#     #             "years": mc.get("years") or [],
#     #             "labels": mc.get("labels") or [],
#     #             "records": mat_records,
#     #         }

#     #     return payload

    




#     import pandas as pd
#     import numpy as np

#     def build_llm_payload(out_df: pd.DataFrame, meta: dict) -> dict:
#         df = out_df.copy()
#         chart_type = str(meta.get("chart_type") or "").lower()
#         dims       = list(meta.get("dims") or [])
#         filters    = dict(meta.get("filters") or {})
#         window     = dict(meta.get("window") or {})
#         measure    = str(meta.get("measure") or "value_sales")
#         mode_raw   = str(meta.get("mode") or "").upper()
#         periods=meta.get("periods")
#         # print("DEBUG>>>")
#         # print(mode_raw)
#         if mode_raw=='_YOY':
#             mode_raw=mode_raw.replace("_","")

#         # print(periods)
        

#         # ---------- normalize mode ----------
#         if mode_raw in ("MAT_COMPARE", "YTD"):
#             mode_norm = mode_raw
#         else:
#             if chart_type == "line":   mode_norm = "LINE"
#             elif chart_type == "bar":  mode_norm = "BAR"
#             elif chart_type == "table":mode_norm = "TABLE"
#             else:                      mode_norm = "CUSTOM"

#         # ---------- ensure time cols ----------
#         time_col = None
#         if "date" in df.columns:
#             time_col = "date"
#             with pd.option_context("mode.chained_assignment", None):
#                 df["date"] = pd.to_datetime(df["date"], errors="coerce")
#                 df["month_label"] = df["date"].dt.strftime("%b %Y")
#                 df["month_iso"]   = df["date"].dt.to_period("M").astype(str)

#         # ---------- small sample ----------
#         sample_cols = [c for c in df.columns if c in
#                     ["date","month_label","month_iso","brand","category","market",
#                         "value_sales","unit_sales","share",
#                         "value_sales_curr","value_sales_prev","value_yoy",
#                         "unit_sales_curr","unit_sales_prev","unit_yoy",
#                         "value_mom","unit_mom"]]
#         table_sample = df[sample_cols].head(6).to_dict(orient="records") if sample_cols else []

#         # helper: pick a base measure sensibly
#         def _pick_base_measure(frame: pd.DataFrame) -> str | None:
#             for c in ("value_sales","unit_sales"):
#                 if c in frame.columns:
#                     return c
#             num = frame.select_dtypes(include=[np.number]).columns.tolist()
#             return num[0] if num else None

#         # ---------- TREND (unchanged) ----------
#         trend_block = None
#         if chart_type == "line" and time_col is not None:
#             base_measure = _pick_base_measure(df)
#             by_brand = []
#             if base_measure is not None:
#                 if "brand" in df.columns:
#                     for b, g in df.groupby("brand", dropna=False):
#                         g = g.dropna(subset=[base_measure])
#                         if g.empty: continue
#                         rmin = g.loc[g[base_measure].idxmin()]
#                         rmax = g.loc[g[base_measure].idxmax()]
#                         by_brand.append({
#                             "brand": b if pd.notna(b) else "Unknown",
#                             "min":  {"value": float(rmin[base_measure]),
#                                     "period": str(rmin.get("month_iso") or ""),
#                                     "label":  str(rmin.get("month_label") or "")},
#                             "max":  {"value": float(rmax[base_measure]),
#                                     "period": str(rmax.get("month_iso") or ""),
#                                     "label":  str(rmax.get("month_label") or "")},
#                         })
#                 g = df.dropna(subset=[base_measure])
#                 overall = None
#                 if not g.empty:
#                     rmin = g.loc[g[base_measure].idxmin()]
#                     rmax = g.loc[g[base_measure].idxmax()]
#                     overall = {
#                         "min":  {"value": float(rmin[base_measure]),
#                                 "period": str(rmin.get("month_iso") or ""),
#                                 "label":  str(rmin.get("month_label") or "")},
#                         "max":  {"value": float(rmax[base_measure]),
#                                 "period": str(rmax.get("month_iso") or ""),
#                                 "label":  str(rmax.get("month_label") or "")},
#                     }
#                 trend_block = {"measure": base_measure, "by_brand": by_brand, "overall": overall}
#                 # print(trend_block)

#         # ---------- YoY (unchanged; now explicit) ----------
#         # print(meta)
#         yoy_block = None
#         if {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns) or \
#         {"unit_sales_curr","unit_sales_prev","unit_yoy"}.issubset(df.columns):

#             use_value = {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns)
#             curr_col  = "value_sales_curr" if use_value else "unit_sales_curr"
#             prev_col  = "value_sales_prev" if use_value else "unit_sales_prev"
#             yoy_col   = "value_yoy"        if use_value else "unit_yoy"

#             group_dims = [d for d in ("brand","category","market","channel") if d in df.columns]

#             tmp = df[group_dims + [curr_col, prev_col, yoy_col]].copy()
#             # print(df)
#             # print(f"filters:{filters}")
#             # print(tmp)
#             # if not tmp.empty:
#             #     tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             if group_dims:  # only group if dimensions exist
#                 tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
#             else:
#                 tmp = tmp.sum(numeric_only=True).to_frame().T.reset_index(drop=True)

#             items = []
#             for _, r in tmp.iterrows():
#                 item = {
#                     "curr": float(r[curr_col]) if pd.notna(r[curr_col]) else None,
#                     "prev": float(r[prev_col]) if pd.notna(r[prev_col]) else None,
#                     "yoy_pct": float(r[yoy_col]) if pd.notna(r[yoy_col]) else None,
#                 }
#                 for d in group_dims:
#                     item[d] = r[d] if d in r and pd.notna(r[d]) else None
#                 items.append(item)

#             yoy_block = {"measure_type": "value" if use_value else "unit", "items": items}
#         # print(yoy_block)
        

#         # # ---------- MAT compare (unchanged) ----------
#         from datetime import datetime
#         mat_block = None
#         mat_info = meta.get("mat_compare")
#         if isinstance(mat_info, dict) and "labels" in mat_info:
#             label_col = "mat_label" if "mat_label" in df.columns else None
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None
#             items = []
#             if label_col and base_measure:
#                 # print(label_col)
#                 agg = df.groupby(label_col, dropna=False)[base_measure].sum().reset_index()
#                 for _, r in agg.iterrows():
#                     items.append({"label": str(r[label_col]), "total": float(r[base_measure])})
#             mat_block = {"items": items, "anchor_month": mat_info.get("anchor_month")}
#         # for i in items[]
#         # for i in items:
            
#         #     year=int(i['label'].replace("MAT","").strip())
#         #     # print(year)
#         #     end=pd.to_datetime(window['end'])
#         #     end=end.replace(year=year)
#         #     # print(end)
#         #     start=end-pd.DateOffset(months=11)
#         #     # print(start)
#         # print(meta)
#         # print(meta)
#         if meta.get('periods') is not None:
#             for i in range(0,len(meta['periods'])):
#                 meta['periods'][i].update(out_df.to_dict(orient="records")[i])
#             # print("METAAAAAA DATA:",meta)
#             # print(mat_block)
        
#             # print(meta['periods'])

#             sorted_periods=sorted(meta['periods'], key=lambda x: x['value_sales'],reverse=True)
#             for i,j in enumerate(sorted_periods):
#                 meta['periods'][i].update({'rank':i+1})
#             # print(meta)

#             # print("SORTED PERIODS:",meta)
            





#         # ---------- BAR / topN (unchanged) ----------
#         bar_block = None
#         if chart_type == "bar":
#             non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
#             xcat = None
#             for c in ["brand","category","market","channel","segment","manufacturer"]:
#                 if c in non_numeric: xcat = c; break
#             if xcat is None and non_numeric: xcat = non_numeric[0]
#             ycols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
#             prefer_y = [c for c in ["value_sales","unit_sales","value_yoy","unit_yoy"] if c in ycols]
#             y = prefer_y[0] if prefer_y else (ycols[0] if ycols else None)
#             items = []
#             if xcat and y:
#                 tmp = df[[xcat, y]].copy().groupby(xcat, dropna=False)[y].sum().reset_index()
#                 tmp = tmp.sort_values(y, ascending=False, na_position="last")
#                 for i, r in enumerate(tmp.itertuples(index=False), start=1):
#                     items.append({"rank": i, "label": getattr(r, xcat), "value": float(getattr(r, y))})
#                 bar_block = {"x": xcat, "y": y, "items": items}

#         # ---------- NEW: MoM block (per brand + overall) ----------
#         mom_block = None
#         if time_col is not None:
#             # choose measure for MoM (value preferred)
#             base_measure = "value_sales" if "value_sales" in df.columns else \
#                         "unit_sales"  if "unit_sales"  in df.columns else None

#             # see if MoM column already exists
#             mom_col = "value_mom" if "value_mom" in df.columns else \
#                     "unit_mom"  if "unit_mom"  in df.columns else None

#             def _series_items(frame: pd.DataFrame) -> list[dict]:
#                 f = frame.copy()
#                 # Sort by time
#                 f = f.sort_values("month_iso" if "month_iso" in f.columns else "date")
#                 # Compute MoM if missing
#                 if mom_col is None and base_measure in f.columns:
#                     f["_prev"] = f[base_measure].shift(1)
#                     with np.errstate(divide="ignore", invalid="ignore"):
#                         f["_mom"] = (f[base_measure] / f["_prev"]) - 1
#                 else:
#                     # use existing column
#                     f["_mom"] = f[mom_col]
#                     if base_measure in f.columns:
#                         f["_prev"] = f[base_measure].shift(1)

#                 items = []
#                 for _, r in f.iterrows():
#                     period = str(r.get("month_iso") or (r["date"].to_period("M").strftime("%Y-%m")
#                                                         if pd.notna(r.get("date")) else ""))
#                     label  = str(r.get("month_label") or "")
#                     mom_pct = r.get("_mom")
#                     curr = r.get(base_measure) if base_measure in f.columns else None
#                     prev = r.get("_prev")
#                     if pd.isna(mom_pct):   mom_pct = None
#                     if pd.isna(curr):      curr = None
#                     if pd.isna(prev):      prev = None
#                     items.append({"period": period, "label": label,
#                                 "mom_pct": float(mom_pct) if mom_pct is not None else None,
#                                 "curr": float(curr) if curr is not None else None,
#                                 "prev": float(prev) if prev is not None else None})
#                 # keep only rows where mom is computed or exists
#                 return [it for it in items if it["mom_pct"] is not None]

#             by_brand = []
#             if "brand" in df.columns:
#                 for b, g in df.groupby("brand", dropna=False):
#                     ser = _series_items(g)
#                     if ser:
#                         by_brand.append({"brand": b if pd.notna(b) else "Unknown", "series": ser})

#             overall = None
#             ser_all = _series_items(df)
#             if ser_all:
#                 overall = {"series": ser_all}

#             if by_brand or overall:
#                 mom_block = {
#                     "measure": base_measure or ("value_sales" if mom_col == "value_mom" else "unit_sales"),
#                     "by_brand": by_brand,
#                     "overall": overall
#                 }

#         # ---------- assemble ----------
#         # if meta['periods'] is not None:

#         payload = {
#             "mode": mode_norm,
#             "measure": measure,
#             "window": window,
#             "dims": [d for d in dims if d != "date"],
#             "filters": filters,
#             # "table_sample": table_sample,
#         }
#         if mat_block is not None:
#             # print(meta)
#             mat_block=meta
#         if trend_block is not None:     payload["trend"] = trend_block
#         if yoy_block is not None:       payload["yoy"] = yoy_block
#         if mat_block is not None:       payload["mat_compare"] = mat_block
#         if bar_block is not None:       payload["bar"] = bar_block
#         if mom_block is not None:       payload["mom"] = mom_block
#         # print(mat_block)
#         if mat_block is not None:
#             # payload['items']=payload['periods']
#             del payload['bar']
#         # print(result["meta"])
#         # if mode_raw=="MAT_YOY" or mode_raw=="YTD_YOY"  or mode_raw=="YOY":
#         payload['calculation_mode']=mode_raw.lower()
#         if "total" in payload['calculation_mode']:
#             payload.pop('mom')
#             # print(payload.keys())
#         import re

#         total_pattern = re.compile(r"\b(total|overall|aggregate|grand\s*total|sum|cumulative|combined|net\s+sales)\b", re.IGNORECASE)
#         trend_pattern = re.compile(r"\b(trend|over\s+time|month[-\s]*wise|monthly|line\s*chart|last\s+\d+\s+months)\b", re.IGNORECASE)
#         if total_pattern.search(intent['raw_text']) and not trend_pattern.search(intent['raw_text']):
#            payload['calculation_mode']=f'total {measure}'

       

#         return payload
#     payload = build_llm_payload(result["data"], result["meta"])
#     # print(f"{attach_insights(payload)}")
#     payload=attach_insights(payload)
#     print(f"The payload>>>>>>>>>>>>>>>>>>>>>>>>>>>")
#     print(payload)
#     print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
#     # print(intent['raw_text'])
    

#     # import pandas as pd

  

#     # print(build_llm_payload(result["data"],result["meta"]))


#     out_df, meta = result["data"], result["meta"]
#     # print(f"{result["meta"]}")
#     # print(f"DEBUG>>>> {out_df}")
#     insights=generate_simple_insights(out_df,meta)
#     aa={
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
        
#     }
#     # print(aa)
  

#     return {
#         "intent": intent_model.model_dump(),
#         "effective_intent": {
#             **intent,
#             # expose the actual dates the runner used
#             "time_range": {
#                 **(intent.get("time_range") or {}),
#                 "start_used": meta["window"]["start"],
#                 "end_used": meta["window"]["end"],
#             },
#         },
#         "sql": None,
#         "meta": meta,
#         "data": out_df.to_dict(orient="records"),
#         "columns": list(out_df.columns),
#         "insights": payload['insights'],
#         # "derived": payload['derived'],
#     }
  
#     # intent_model = parse_user_text(body.question)

#     # # Build dict intent WITH original text so we can infer MAT/YTD
#     # intent = intent_to_dict(intent_model, original_text=body.question)

#     # # Safety: force mode if user text says MAT/YTD but converter didn't set it
#     # q = body.question.lower()
#     # tr = intent.get("time_range") or {}
#     # if "mode" not in tr:
#     #     if any(k in q for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#     #         tr["mode"] = "MAT"
#     #     elif any(k in q for k in ["ytd", "year to date", "year-to-date"]):
#     #         tr["mode"] = "YTD"
#     # intent["time_range"] = tr if tr else None

#     # # Safety: treat "table + limit" as Top-N
#     # if intent.get("task") == "table" and intent.get("top_n"):
#     #     intent["task"] = "topn"

#     # # Safety: for Top-N, drop 'date' from dims
#     # if intent.get("task") == "topn":
#     #     intent["dims"] = [d for d in (intent.get("dims") or []) if d != "date"]

#     # df = _load_df(body.settings_path)
#     # result = run_pandas_intent(df, intent)
#     # out_df, meta = result["data"], result["meta"]

#     # bullets = []
#     # if "value_yoy" in out_df.columns and out_df["value_yoy"].notna().any():
#     #     best = out_df.sort_values("value_yoy", ascending=False).head(1)
#     #     worst = out_df.sort_values("value_yoy", ascending=True).head(1)
#     #     try:
#     #         b = best.iloc[0]
#     #         bullets.append(f"Best YoY mover: {b.get('brand','(agg)')} value_yoy={b['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     #     try:
#     #         w = worst.iloc[0]
#     #         bullets.append(f"Worst YoY mover: {w.get('brand','(agg)')} value_yoy={w['value_yoy']:.1%}")
#     #     except Exception:
#     #         pass
#     # if "share" in out_df.columns and out_df["share"].notna().any():
#     #     latest_share = out_df.iloc[-1]["share"]
#     #     bullets.append(f"Latest share in slice: {latest_share:.1f}%")

#     # empty_hint = None
#     # if out_df.empty:
#     #     empty_hint = "No rows in the selected window/filters. Check spelling or try YTD/MAT explicitly."

#     # return {
#     #     "intent": intent_model.model_dump(),   # raw parsed (may show time_range NULL)
#     #     "effective_intent": intent,            # ✅ what runner actually used (will show mode)
#     #     "sql": None,
#     #     "meta": meta,                          # window actually used (dates)
#     #     "data": out_df.to_dict(orient="records"),
#     #     "columns": list(out_df.columns),
#     #     "insights": bullets[:3],
#     #     "empty_hint": empty_hint,
#     # }

# @app.post("/sql")
# def run_raw_sql(body: SqlBody):
#     # keep the raw SQL endpoint working exactly as before
#     df, meta = run_sql(body.sql, body.settings_path)
#     return {"meta": meta, "data": df.to_dict(orient="records"), "columns": list(df.columns)}






























from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from backend.forecasting_api import router as forecasting_router
from pydantic import BaseModel
from typing import Dict
import json, yaml
import pandas as pd
import tempfile, os

from backend.routes import ask
from backend.llm.gemini import generate_gemini_insights
from backend.llm.utils import strip_for_llm, fallback_bullets

from backend.ingest.excel_ingest import ingest_excel
from backend.sql.runner import run_sql, get_cfg

# use pandas path (your parser + runner)
from .nlp.parser import parse_user_text, intent_to_dict
from .nlp.pandas_runner import run_pandas_intent
from backend.insights import generate_simple_insights,attach_insights
# from backend.routes import ask  
app = FastAPI(title="Nielsen Excel Q&A — Starter API")
app.state.df = None 


app.state.gemini_key = ""   # <- stored in memory only
app.include_router(forecasting_router)
# app.include_router(ask.router)
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
    # payload= build_llm_payload(result["data"], result["meta"])
    # print(payload)
    # print(result["meta"])
    

   

    

    import pandas as pd
    import numpy as np
    import pandas as pd

    def _pick_time_col(df: pd.DataFrame) -> str | None:
        # prefer true datetime; fallbacks are ok too
        for c in ["date", "month_date", "x_dt", "month"]:
            if c in df.columns:
                return c
        return None

    def _format_period(val) -> str:
        # output nice "Jan 2024" labels where possible
        if isinstance(val, pd.Timestamp):
            return val.to_period("M").strftime("%b %Y")
        try:
            ts = pd.to_datetime(val, errors="coerce")
            if pd.notna(ts):
                return ts.to_period("M").strftime("%b %Y")
        except Exception:
            pass
        return str(val)

    def _pick_measure_for_line(df: pd.DataFrame, meta: dict) -> list[str]:
        # choose the measure(s) to report
        prefer = str(meta.get("measure") or "")
        candidates = [m for m in ["value_sales", "unit_sales"] if m in df.columns]
        if prefer and prefer in candidates:
            return [prefer]
        return candidates or []

    def build_line_table_data(df: pd.DataFrame, meta: dict) -> dict:
        """
        Returns a dict ready to put under payload['table_data'] for line charts.
        Structure:
        {
            "measure": "value_sales",
            "by_brand": [
            {"brand":"Alpha","min_value":..., "min_period":"...", "max_value":..., "max_period":"..."},
            ...
            ]
        }
        If no 'brand' column, returns "overall" with a single min/max row.
        """
        tcol = _pick_time_col(df)
        measures = _pick_measure_for_line(df, meta)
        out: dict = {"_time_col": tcol}  # small debug hint; remove if you don't want it

        if not tcol or not measures:
            return out  # nothing to do

        # If both value & unit exist, we can emit both blocks
        for m in measures:
            block_key = m  # e.g. "value_sales"
            rows = []

            if "brand" in df.columns:
                for brand, g in df.groupby("brand", dropna=False):
                    g = g.dropna(subset=[m])
                    if g.empty or tcol not in g.columns:
                        continue
                    idx_min = g[m].idxmin()
                    idx_max = g[m].idxmax()
                    rows.append({
                        "brand": None if pd.isna(brand) else str(brand),
                        "min_value": float(g.loc[idx_min, m]),
                        "min_period": _format_period(g.loc[idx_min, tcol]),
                        "max_value": float(g.loc[idx_max, m]),
                        "max_period": _format_period(g.loc[idx_max, tcol]),
                    })
            else:
                g = df.dropna(subset=[m])
                if not g.empty and tcol in g.columns:
                    idx_min = g[m].idxmin()
                    idx_max = g[m].idxmax()
                    rows.append({
                        "min_value": float(g.loc[idx_min, m]),
                        "min_period": _format_period(g.loc[idx_min, tcol]),
                        "max_value": float(g.loc[idx_max, m]),
                        "max_period": _format_period(g.loc[idx_max, tcol]),
                    })

            out[block_key] = {
                "measure": m,
                "by_brand": rows if "brand" in df.columns else None,
                "overall": None if "brand" in df.columns else rows[0] if rows else None,
            }

        return out
    # def build_llm_payload(df: pd.DataFrame, meta: dict, intent: dict) -> dict:
    #     payload = {
    #         "mode": meta.get("mode"),
    #         "chart_type": meta.get("chart_type"),
    #         "dims": meta.get("dims") or [],
    #         "filters": meta.get("filters") or {},
    #         "window": meta.get("window") or {},
    #         "measure": meta.get("measure"),
    #         # "table_data":{"brand":{Alpha:{min_sales:,monthofmaxsales date},max_sales:,maxsales month date}}}
    #     }

    #     if (meta.get("chart_type") == "line"):
    #         payload["table_data"] = build_line_table_data(df, meta)
         
    #     dims = [d for d in (meta.get("dims") or []) if d != "date"]
    #     measure_hint = str(meta.get("measure") or "")
    #     # print([for i in df.iterrows()])
    #     if meta.get("chart_type")=="bar" and meta.get("mode")==None:
    #         payload["table_data"]=df.to_json(orient="records")
    #         print(payload)
    #     #     payload["table_data"]=

    #     # --- ✅ Capture YoY details ---
    #     if measure_hint in ("value_yoy", "unit_yoy"):
    #         base_measure = "value_sales" if "value" in measure_hint else "unit_sales"
    #         curr_col = f"{base_measure}_curr"
    #         prev_col = f"{base_measure}_prev"
    #         yoy_col  = measure_hint

    #         if all(c in df.columns for c in [curr_col, prev_col, yoy_col]):
    #             yoy_records = []
    #             for _, r in df[dims + [curr_col, prev_col, yoy_col]].iterrows():
    #                 rec = {d: r[d] for d in dims}
    #                 rec.update({
    #                     "curr": r[curr_col],
    #                     "prev": r[prev_col],
    #                     "yoy_pct": r[yoy_col],
    #                 })
    #                 yoy_records.append(rec)

    #             payload["yoy_details"] = {
    #                 "base_measure": base_measure,
    #                 "records": yoy_records,
    #                 "prev_window": meta.get("prev_window") or (meta.get("debug", {}) or {}).get("prev_window"),
    #             }

    #     # --- ✅ Capture MAT compare details ---
    #     if (meta.get("mode") == "MAT_COMPARE") or ("mat_compare" in meta):
    #         mc = meta.get("mat_compare", {}) or {}
    #         label_col = "mat_label" if "mat_label" in df.columns else None
    #         base_measure = meta.get("measure") or "value_sales"

    #         group_by = []
    #         if label_col: group_by.append(label_col)
    #         if "brand" in df.columns: group_by.append("brand")
    #         for d in dims:
    #             if d not in group_by: group_by.append(d)

    #         mat_records = []
    #         if base_measure in df.columns and group_by:
    #             grouped = df.groupby(group_by, dropna=False)[base_measure].sum().reset_index()
    #             mat_records = grouped.to_dict(orient="records")

    #         payload["mat_details"] = {
    #             "measure": base_measure,
    #             "anchor_month": mc.get("anchor_month"),
    #             "years": mc.get("years") or [],
    #             "labels": mc.get("labels") or [],
    #             "records": mat_records,
    #         }

    #     return payload

    




    import pandas as pd
    import numpy as np

    def build_llm_payload(out_df: pd.DataFrame, meta: dict) -> dict:
        df = out_df.copy()
        chart_type = str(meta.get("chart_type") or "").lower()
        dims       = list(meta.get("dims") or [])
        filters    = dict(meta.get("filters") or {})
        window     = dict(meta.get("window") or {})
        measure    = str(meta.get("measure") or "value_sales")
        mode_raw   = str(meta.get("mode") or "").upper()
        periods=meta.get("periods")
        # print("DEBUG>>>")
        # print(mode_raw)
        if mode_raw=='_YOY':
            mode_raw=mode_raw.replace("_","")

        # print(periods)
        

        # ---------- normalize mode ----------
        if mode_raw in ("MAT_COMPARE", "YTD"):
            mode_norm = mode_raw
        else:
            if chart_type == "line":   mode_norm = "LINE"
            elif chart_type == "bar":  mode_norm = "BAR"
            elif chart_type == "table":mode_norm = "TABLE"
            else:                      mode_norm = "CUSTOM"

        # ---------- ensure time cols ----------
        time_col = None
        if "date" in df.columns:
            time_col = "date"
            with pd.option_context("mode.chained_assignment", None):
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df["month_label"] = df["date"].dt.strftime("%b %Y")
                df["month_iso"]   = df["date"].dt.to_period("M").astype(str)

        # ---------- small sample ----------
        sample_cols = [c for c in df.columns if c in
                    ["date","month_label","month_iso","brand","category","market",
                        "value_sales","unit_sales","share",
                        "value_sales_curr","value_sales_prev","value_yoy",
                        "unit_sales_curr","unit_sales_prev","unit_yoy",
                        "value_mom","unit_mom"]]
        table_sample = df[sample_cols].head(6).to_dict(orient="records") if sample_cols else []

        # helper: pick a base measure sensibly
        def _pick_base_measure(frame: pd.DataFrame) -> str | None:
            for c in ("value_sales","unit_sales"):
                if c in frame.columns:
                    return c
            num = frame.select_dtypes(include=[np.number]).columns.tolist()
            return num[0] if num else None

        # ---------- TREND (unchanged) ----------
        trend_block = None
        if chart_type == "line" and time_col is not None:
            base_measure = _pick_base_measure(df)
            by_brand = []
            if base_measure is not None:
                if "brand" in df.columns:
                    for b, g in df.groupby("brand", dropna=False):
                        g = g.dropna(subset=[base_measure])
                        if g.empty: continue
                        rmin = g.loc[g[base_measure].idxmin()]
                        rmax = g.loc[g[base_measure].idxmax()]
                        by_brand.append({
                            "brand": b if pd.notna(b) else "Unknown",
                            "min":  {"value": float(rmin[base_measure]),
                                    "period": str(rmin.get("month_iso") or ""),
                                    "label":  str(rmin.get("month_label") or "")},
                            "max":  {"value": float(rmax[base_measure]),
                                    "period": str(rmax.get("month_iso") or ""),
                                    "label":  str(rmax.get("month_label") or "")},
                        })
                g = df.dropna(subset=[base_measure])
                overall = None
                if not g.empty:
                    rmin = g.loc[g[base_measure].idxmin()]
                    rmax = g.loc[g[base_measure].idxmax()]
                    overall = {
                        "min":  {"value": float(rmin[base_measure]),
                                "period": str(rmin.get("month_iso") or ""),
                                "label":  str(rmin.get("month_label") or "")},
                        "max":  {"value": float(rmax[base_measure]),
                                "period": str(rmax.get("month_iso") or ""),
                                "label":  str(rmax.get("month_label") or "")},
                    }
                trend_block = {"measure": base_measure, "by_brand": by_brand, "overall": overall}
                # print(trend_block)

        # ---------- YoY (unchanged; now explicit) ----------
        # print(meta)
        yoy_block = None
        if {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns) or \
        {"unit_sales_curr","unit_sales_prev","unit_yoy"}.issubset(df.columns):

            use_value = {"value_sales_curr","value_sales_prev","value_yoy"}.issubset(df.columns)
            curr_col  = "value_sales_curr" if use_value else "unit_sales_curr"
            prev_col  = "value_sales_prev" if use_value else "unit_sales_prev"
            yoy_col   = "value_yoy"        if use_value else "unit_yoy"

            group_dims = [d for d in ("brand","category","market","channel") if d in df.columns]

            tmp = df[group_dims + [curr_col, prev_col, yoy_col]].copy()
            # print(df)
            # print(f"filters:{filters}")
            # print(tmp)
            # if not tmp.empty:
            #     tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
            if group_dims:  # only group if dimensions exist
                tmp = tmp.groupby(group_dims, dropna=False).sum(numeric_only=True).reset_index()
            else:
                tmp = tmp.sum(numeric_only=True).to_frame().T.reset_index(drop=True)

            items = []
            for _, r in tmp.iterrows():
                item = {
                    "curr": float(r[curr_col]) if pd.notna(r[curr_col]) else None,
                    "prev": float(r[prev_col]) if pd.notna(r[prev_col]) else None,
                    "yoy_pct": float(r[yoy_col]) if pd.notna(r[yoy_col]) else None,
                }
                for d in group_dims:
                    item[d] = r[d] if d in r and pd.notna(r[d]) else None
                items.append(item)

            yoy_block = {"measure_type": "value" if use_value else "unit", "items": items}
        # print(yoy_block)
        

        # # ---------- MAT compare (unchanged) ----------
        from datetime import datetime
        mat_block = None
        mat_info = meta.get("mat_compare")
        if isinstance(mat_info, dict) and "labels" in mat_info:
            label_col = "mat_label" if "mat_label" in df.columns else None
            base_measure = "value_sales" if "value_sales" in df.columns else \
                        "unit_sales"  if "unit_sales"  in df.columns else None
            items = []
            if label_col and base_measure:
                # print(label_col)
                agg = df.groupby(label_col, dropna=False)[base_measure].sum().reset_index()
                for _, r in agg.iterrows():
                    items.append({"label": str(r[label_col]), "total": float(r[base_measure])})
            mat_block = {"items": items, "anchor_month": mat_info.get("anchor_month")}
        # for i in items[]
        # for i in items:
            
        #     year=int(i['label'].replace("MAT","").strip())
        #     # print(year)
        #     end=pd.to_datetime(window['end'])
        #     end=end.replace(year=year)
        #     # print(end)
        #     start=end-pd.DateOffset(months=11)
        #     # print(start)
        # print(meta)
        # print(meta)
        if meta.get('periods') is not None:
            for i in range(0,len(meta['periods'])):
                meta['periods'][i].update(out_df.to_dict(orient="records")[i])
            # print("METAAAAAA DATA:",meta)
            # print(mat_block)
        
            # print(meta['periods'])

            sorted_periods=sorted(meta['periods'], key=lambda x: x['value_sales'],reverse=True)
            for i,j in enumerate(sorted_periods):
                meta['periods'][i].update({'rank':i+1})
            # print(meta)

            # print("SORTED PERIODS:",meta)
            





        # ---------- BAR / topN (unchanged) ----------
        bar_block = None
        if chart_type == "bar":
            non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
            xcat = None
            for c in ["brand","category","market","channel","segment","manufacturer"]:
                if c in non_numeric: xcat = c; break
            if xcat is None and non_numeric: xcat = non_numeric[0]
            ycols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            prefer_y = [c for c in ["value_sales","unit_sales","value_yoy","unit_yoy"] if c in ycols]
            y = prefer_y[0] if prefer_y else (ycols[0] if ycols else None)
            items = []
            if xcat and y:
                tmp = df[[xcat, y]].copy().groupby(xcat, dropna=False)[y].sum().reset_index()
                tmp = tmp.sort_values(y, ascending=False, na_position="last")
                for i, r in enumerate(tmp.itertuples(index=False), start=1):
                    items.append({"rank": i, "label": getattr(r, xcat), "value": float(getattr(r, y))})
                bar_block = {"x": xcat, "y": y, "items": items}

        # ---------- NEW: MoM block (per brand + overall) ----------
        mom_block = None
        if time_col is not None:
            # choose measure for MoM (value preferred)
            base_measure = "value_sales" if "value_sales" in df.columns else \
                        "unit_sales"  if "unit_sales"  in df.columns else None

            # see if MoM column already exists
            mom_col = "value_mom" if "value_mom" in df.columns else \
                    "unit_mom"  if "unit_mom"  in df.columns else None

            def _series_items(frame: pd.DataFrame) -> list[dict]:
                f = frame.copy()
                # Sort by time
                f = f.sort_values("month_iso" if "month_iso" in f.columns else "date")
                # Compute MoM if missing
                if mom_col is None and base_measure in f.columns:
                    f["_prev"] = f[base_measure].shift(1)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        f["_mom"] = (f[base_measure] / f["_prev"]) - 1
                else:
                    # use existing column
                    f["_mom"] = f[mom_col]
                    if base_measure in f.columns:
                        f["_prev"] = f[base_measure].shift(1)

                items = []
                for _, r in f.iterrows():
                    period = str(r.get("month_iso") or (r["date"].to_period("M").strftime("%Y-%m")
                                                        if pd.notna(r.get("date")) else ""))
                    label  = str(r.get("month_label") or "")
                    mom_pct = r.get("_mom")
                    curr = r.get(base_measure) if base_measure in f.columns else None
                    prev = r.get("_prev")
                    if pd.isna(mom_pct):   mom_pct = None
                    if pd.isna(curr):      curr = None
                    if pd.isna(prev):      prev = None
                    items.append({"period": period, "label": label,
                                "mom_pct": float(mom_pct) if mom_pct is not None else None,
                                "curr": float(curr) if curr is not None else None,
                                "prev": float(prev) if prev is not None else None})
                # keep only rows where mom is computed or exists
                return [it for it in items if it["mom_pct"] is not None]

            by_brand = []
            if "brand" in df.columns:
                for b, g in df.groupby("brand", dropna=False):
                    ser = _series_items(g)
                    if ser:
                        by_brand.append({"brand": b if pd.notna(b) else "Unknown", "series": ser})

            overall = None
            ser_all = _series_items(df)
            if ser_all:
                overall = {"series": ser_all}

            if by_brand or overall:
                mom_block = {
                    "measure": base_measure or ("value_sales" if mom_col == "value_mom" else "unit_sales"),
                    "by_brand": by_brand,
                    "overall": overall
                }

        # ---------- assemble ----------
        # if meta['periods'] is not None:

        payload = {
            "mode": mode_norm,
            "measure": measure,
            "window": window,
            "dims": [d for d in dims if d != "date"],
            "filters": filters,
            # "table_sample": table_sample,
        }
        if mat_block is not None:
            # print(meta)
            mat_block=meta
        if trend_block is not None:     payload["trend"] = trend_block
        if yoy_block is not None:       payload["yoy"] = yoy_block
        if mat_block is not None:       payload["mat_compare"] = mat_block
        if bar_block is not None:       payload["bar"] = bar_block
        if mom_block is not None:       payload["mom"] = mom_block
        # print(mat_block)
        if mat_block is not None:
            # payload['items']=payload['periods']
            del payload['bar']
        # print(result["meta"])
        # if mode_raw=="MAT_YOY" or mode_raw=="YTD_YOY"  or mode_raw=="YOY":
        payload['calculation_mode']=mode_raw.lower()
        if "total" in payload['calculation_mode']:
            payload.pop('mom')
            # print(payload.keys())
        import re

        total_pattern = re.compile(r"\b(total|overall|aggregate|grand\s*total|sum|cumulative|combined|net\s+sales)\b", re.IGNORECASE)
        trend_pattern = re.compile(r"\b(trend|over\s+time|month[-\s]*wise|monthly|line\s*chart|last\s+\d+\s+months)\b", re.IGNORECASE)
        if total_pattern.search(intent['raw_text']) and not trend_pattern.search(intent['raw_text']):
           payload['calculation_mode']=f'total {measure}'

       

        return payload
    payload = build_llm_payload(result["data"], result["meta"])
    api_key=""
    llm_bullets = generate_gemini_insights(api_key,payload)
    # print(f"{attach_insights(payload)}")
    # bullets=[]
    # bullets=["hello"]
    # print(f"Bullets generated by gemmini:{bullets}")
    print(llm_bullets)
    payload=attach_insights(payload)
    # print(llm_bullets)
    # llm_bullets=llm_bullets.split(".")
    # llm_bullets=llm_bullets[1:]
    payload['insights']['rule_based_bullets']=payload['insights']['bullets']
    del payload['insights']['bullets']
    # payload['insights']['llm_based_bullets']=llm_bullets
    # print(llm_bullets)
    
    # print(bullets)
    # payload['insights']['bullets']=
    payload['insights'].update({"llm_based_bullets":llm_bullets})
    print(payload['insights'])
    # print(payload['insights'])
    # print(payload)
    # print(f"The payload>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    # clean_payload = strip_for_llm(payload)
  
    # if not bullets:
        # bullets = fallback_bullets(clean_payload)

    # print("Final Output:", {"stats": payload, "bullets": bullets})
    # print(payload)
    print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    # print(intent['raw_text'])
    

    # import pandas as pd

  

    # print(build_llm_payload(result["data"],result["meta"]))


    out_df, meta = result["data"], result["meta"]
    # print(f"{result["meta"]}")
    # print(f"DEBUG>>>> {out_df}")
    insights=generate_simple_insights(out_df,meta)
    aa={
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
        
    }
    # print(aa)
  

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
        "insights": payload['insights'],
        # "derived": payload['derived'],
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













# backend/insights.py









# # backend/insights.py

