# # Working code MAT YoY,YTD, TopN, Brand Grouping
# # backend/nlp/pandas_runner.py
# import pandas as pd
# import numpy as np
# from typing import Dict, Any, List, Optional, Tuple

# # ---------- helpers ----------

# def _system_last_full_month_end(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
#     now = now or pd.Timestamp.today()
#     return (now.to_period("M") - 1).to_timestamp(how="end")

# def _month_bounds_from_end(month_end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return (month_start, month_end) for the given month_end (normalized to month)."""
#     me = month_end.to_period("M").to_timestamp(how="end")
#     ms = me.to_period("M").to_timestamp(how="start")
#     return ms, me

# def _prev_month_end(month_end: pd.Timestamp) -> pd.Timestamp:
#     """End of the immediately previous month."""
#     return (month_end.to_period("M") - 1).to_timestamp(how="end")

# def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return the previous-year window aligned to the same months."""
#     prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#     prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#     return prev_start, prev_end

# def _aggregate(df: pd.DataFrame, dims: List[str], measure_col: str):
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True, dropna=False)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return df.groupby(gcols, dropna=False)[measure_col].sum().reset_index()

# def periods_from_system_now(now: Optional[pd.Timestamp] = None) -> Dict[str, pd.Timestamp]:
#     """System-time aware anchors (used for YTD fallback)."""
#     now = now or pd.Timestamp.today()
#     ytd_start = pd.Timestamp(f"{now.year}-01-01")
#     ytd_end   = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
#     mat_end   = ytd_end
#     mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

# def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT = last 12 complete months ending at the previous full month (by system time),
#     clamped to the latest full month that exists in the dataset.
#     Returns (start, end) as month-start and month-end timestamps.
#     """
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     dates = pd.to_datetime(df["date"])
#     system_today   = system_today or pd.Timestamp.today()
#     prev_full_end  = (system_today.to_period("M") - 1).to_timestamp(how="end")
#     dataset_last   = dates.max().to_period("M").to_timestamp(how="end")
#     mat_end        = min(prev_full_end, dataset_last)
#     mat_start      = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return mat_start.normalize(), mat_end.normalize()

# # ---------- core compute ----------

# def apply_filters(df, filters):
#     out = df.copy()
#     for col, val in (filters or {}).items():
#         if col not in out.columns:
#             continue
#         # case-insensitive, trimmed comparisons
#         if isinstance(val, list):
#             vals = [str(v).strip().lower() for v in val]
#             out = out[out[col].astype(str).str.strip().str.lower().isin(vals)]
#         else:
#             v = str(val).strip().lower()
#             out = out[out[col].astype(str).str.strip().str.lower() == v]
#     return out

# def aggregate(df: pd.DataFrame, dims: List[str], measure_col: str = "value_sales") -> pd.DataFrame:
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return (
#         df.groupby(gcols, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#     )

# def compute_topN(df: pd.DataFrame, dim: str, measure_col: str, n: int) -> pd.DataFrame:
#     return (
#         df.groupby(dim, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#           .head(n)
#     )

# # ------------------------------ main entry ------------------------------

# def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     intent dict:
#       - task: "topn" | "table" | "chart"
#       - dims: list (e.g., ["brand"])
#       - measures: list or str (default "value_sales")
#       - filters: dict (e.g., {"category":"Biscuits","market":"India"})
#       - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
#       - top_n: int
#       - mom: bool
#       - is_yoy: bool (explicit YoY request)
#       - brand_group: bool (explicit "by brand" request)
#       - has_brand_filter: bool (explicit brand fixed by filter)
#     """
#     import numpy as np

#     # ---------- normalize ----------
#     measure = (intent.get("measures") or ["value_sales"])
#     measure = measure[0] if isinstance(measure, list) else measure
#     dims             = intent.get("dims") or []
#     filters          = dict(intent.get("filters") or {})
#     # normalize top_n robustly
#     _topn_raw = intent.get("top_n")
#     top_n = int(_topn_raw) if _topn_raw is not None else 5

#     time            = intent.get("time_range") or {}
#     mode            = (time.get("mode") or "").upper()
#     brand_group     = bool(intent.get("brand_group"))
#     has_brand_filter= bool(intent.get("has_brand_filter"))
#     asked_yoy       = bool(intent.get("is_yoy"))

#     # If grouping by brand, drop any brand filter (avoid double restriction)
#     if brand_group and "brand" in filters:
#         filters.pop("brand", None)

#     # ---------- date column ----------
#     df = df.copy()
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     df["date"] = pd.to_datetime(df["date"])
#     dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

#     # ---------- choose window ----------
#     if mode == "MAT":
#         start, end = compute_mat_window(df)
#     elif mode == "YTD":
#         system_today  = pd.Timestamp.today()
#         prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
#         end   = min(prev_full_end, dataset_last_full)
#         start = pd.Timestamp(f"{end.year}-01-01")
#     elif "start" in time and "end" in time:
#         # custom period support
#         start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
#         end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
#         end   = min(end, dataset_last_full)
#     else:
#         start = df["date"].min().to_period("M").to_timestamp(how="start")
#         end   = dataset_last_full

#     # ---------- base frame ----------
#     base = apply_filters(df, filters)

#     # ===================== MoM BRANCH =====================
#     measures_list = intent.get("measures") or []
#     need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
#     if need_mom:
#         # (left intentionally unchanged per your request)
#         pass

#     # ===================== YoY BRANCH (MAT / YTD / CUSTOM supported) =====================
#     if asked_yoy:
#         use_unit     = "unit_sales" in (intent.get("measures") or [])
#         base_measure = "unit_sales" if use_unit else "value_sales"
#         curr_col     = f"{base_measure}_curr"
#         prev_col     = f"{base_measure}_prev"
#         yoy_col      = "unit_yoy" if use_unit else "value_yoy"

#         # dims for YoY (drop date; keep brand only if brand_group=True)
#         dims_for_yoy = [d for d in (dims or []) if d != "date"]
#         dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         # current period
#         cur_mask = (base["date"] >= start) & (base["date"] <= end)
#         sliced   = base.loc[cur_mask]
#         cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})

#         # aligned previous period (shift -12 months)
#         prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#         prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#         prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
#                         .rename(columns={base_measure: prev_col})

#         out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
#                else pd.concat([cur_agg, prev_agg], axis=1))

#         prev_vals = out[prev_col]
#         cur_vals  = out[curr_col]
#         with np.errstate(divide="ignore", invalid="ignore"):
#             out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

#         # --- Top-N cut for YoY (no logic change; only post-process sorting & truncation) ---
#         if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
#             out = out.sort_values(yoy_col, ascending=False, na_position="last")
#             # If grouping by brand, ensure distinct brands before cutting
#             if brand_group and "brand" in out.columns:
#                 out = out.drop_duplicates(subset=["brand"], keep="first")
#             out = out.head(top_n)

#         out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#         return {"data": out, "meta": {
#             "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#             "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
#             "dims": dims_for_yoy,
#             "measure": yoy_col,
#             "filters": filters,
#             "mode": mode or "CUSTOM",
#             "rowcount": int(out.shape[0]),
#         }}

#     # ===================== Non-MoM/YoY =====================
#     work = base.loc[(base["date"] >= start) & (base["date"] <= end)]

#     if intent.get("task") == "topn":
#         preferred_dim = None
#         if brand_group and "brand" in df.columns:
#             preferred_dim = "brand"
#         else:
#             candidates = [d for d in (dims or []) if d != "date" and d not in filters]
#             preferred_dim = candidates[0] if candidates else None

#         if preferred_dim is None:
#             out = aggregate(work, dims=[], measure_col=measure)
#             for lbl in ("category", "market", "channel", "brand"):
#                 if lbl in filters:
#                     out[lbl] = filters[lbl]
#             label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#             out = out[label_cols + [c for c in out.columns if c not in label_cols]]
#             out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#             return {"data": out, "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "dims": [],
#                 "measure": measure,
#                 "filters": filters,
#                 "mode": mode or None,
#                 "rowcount": int(out.shape[0]),
#             }}

#         out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
#         # Defensive: ensure unique brand rows if ranking by brand
#         if preferred_dim == "brand" and "brand" in out.columns:
#             out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
#         else:
#             out = out.head(top_n)

#         out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#         return {"data": out, "meta": {
#             "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#             "dims": [preferred_dim],
#             "measure": measure,
#             "filters": filters,
#             "mode": mode or None,
#             "rowcount": int(out.shape[0]),
#         }}

#     # normal aggregate / chart
#     if not ("date" in dims and intent.get("task") == "chart"):
#         dims = [d for d in (dims or []) if d != "date"]
#     if not brand_group:
#         dims = [d for d in dims if d != "brand"]

#     out = aggregate(work, dims=dims, measure_col=measure)

#     if not dims:
#         for lbl in ("category", "market", "channel", "brand"):
#             if lbl in filters:
#                 out[lbl] = filters[lbl]
#         label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#         out = out[label_cols + [c for c in out.columns if c not in label_cols]]

#     out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#     return {"data": out, "meta": {
#         "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#         "dims": dims,
#         "measure": measure,
#         "filters": filters,
#         "mode": mode or None,
#         "rowcount": int(out.shape[0]),
#     }}


#Bar chart , Line chart added MAT comparisons remaining , when calculating YoY not charts showing YoY% growth


# # Working code MAT YoY,YTD, TopN, Brand Grouping
# # backend/nlp/pandas_runner.py
# import pandas as pd
# import numpy as np
# from typing import Dict, Any, List, Optional, Tuple

# # ---------- helpers ----------
# def _suggest_chart_type(task: str,
#                         dims: list,
#                         measure: str,
#                         rowcount: int,
#                         is_time: bool) -> str:
#     """
#     Heuristic chart chooser.
#     Returns one of: "line", "bar", "pie", "table"
#     """
#     # Explicit chart task with date → line
#     if task == "chart" and is_time:
#         return "line"

#     # If date present in result → line (timeseries)
#     if is_time:
#         return "line"

#     # Single categorical dim, small N → pie; larger N → bar
#     if len(dims) == 1 and dims[0] != "date":
#         if rowcount <= 8:
#             return "pie"
#         return "bar"

#     # Multiple categorical dims → bar (stack/group handled by front-end)
#     if len(dims) >= 2 and "date" not in dims:
#         return "bar"

#     # Fallbacks
#     if task == "chart":
#         return "bar"
#     return "table"

# def _system_last_full_month_end(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
#     now = now or pd.Timestamp.today()
#     return (now.to_period("M") - 1).to_timestamp(how="end")

# def _month_bounds_from_end(month_end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return (month_start, month_end) for the given month_end (normalized to month)."""
#     me = month_end.to_period("M").to_timestamp(how="end")
#     ms = me.to_period("M").to_timestamp(how="start")
#     return ms, me

# def _prev_month_end(month_end: pd.Timestamp) -> pd.Timestamp:
#     """End of the immediately previous month."""
#     return (month_end.to_period("M") - 1).to_timestamp(how="end")

# def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return the previous-year window aligned to the same months."""
#     prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#     prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#     return prev_start, prev_end

# def _aggregate(df: pd.DataFrame, dims: List[str], measure_col: str):
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True, dropna=False)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return df.groupby(gcols, dropna=False)[measure_col].sum().reset_index()

# def periods_from_system_now(now: Optional[pd.Timestamp] = None) -> Dict[str, pd.Timestamp]:
#     """System-time aware anchors (used for YTD fallback)."""
#     now = now or pd.Timestamp.today()
#     ytd_start = pd.Timestamp(f"{now.year}-01-01")
#     ytd_end   = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
#     mat_end   = ytd_end
#     mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

# def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT = last 12 complete months ending at the previous full month (by system time),
#     clamped to the latest full month that exists in the dataset.
#     Returns (start, end) as month-start and month-end timestamps.
#     """
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     dates = pd.to_datetime(df["date"])
#     system_today   = system_today or pd.Timestamp.today()
#     prev_full_end  = (system_today.to_period("M") - 1).to_timestamp(how="end")
#     dataset_last   = dates.max().to_period("M").to_timestamp(how="end")
#     mat_end        = min(prev_full_end, dataset_last)
#     mat_start      = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return mat_start.normalize(), mat_end.normalize()

# # ---------- core compute ----------

# def apply_filters(df, filters):
#     out = df.copy()
#     for col, val in (filters or {}).items():
#         if col not in out.columns:
#             continue
#         # case-insensitive, trimmed comparisons
#         if isinstance(val, list):
#             vals = [str(v).strip().lower() for v in val]
#             out = out[out[col].astype(str).str.strip().str.lower().isin(vals)]
#         else:
#             v = str(val).strip().lower()
#             out = out[out[col].astype(str).str.strip().str.lower() == v]
#     return out

# def aggregate(df: pd.DataFrame, dims: List[str], measure_col: str = "value_sales") -> pd.DataFrame:
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return (
#         df.groupby(gcols, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#     )

# def compute_topN(df: pd.DataFrame, dim: str, measure_col: str, n: int) -> pd.DataFrame:
#     return (
#         df.groupby(dim, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#           .head(n)
#     )

# # ------------------------------ main entry ------------------------------


# def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     intent dict:
#       - task: "topn" | "table" | "chart"
#       - dims: list (e.g., ["brand"])
#       - measures: list or str (default "value_sales")
#       - filters: dict (e.g., {"category":"Biscuits","market":"India"})
#       - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
#       - top_n: int
#       - mom: bool
#       - is_yoy: bool (explicit YoY request)
#       - brand_group: bool (explicit "by brand" request)
#       - has_brand_filter: bool (explicit brand fixed by filter)
#     """
#     import numpy as np
#     from typing import List, Optional  # keep for helper types

#     # ---------- tiny helper: choose a chart hint for the FRONTEND ----------
#     def _decide_chart_type(task: str, dims_used: List[str], asked_yoy: bool, brand_group: bool) -> Optional[str]:
#         dims_used = dims_used or []
#         if "date" in dims_used:
#             return "line"
#         if task == "chart":
#             if any(d in dims_used for d in ("brand", "category", "market", "channel", "segment", "manufacturer")):
#                 return "bar"
#         if task == "topn":
#             return "bar"
#         if asked_yoy and (brand_group or any(d in dims_used for d in ("brand", "category", "market", "channel"))):
#             return "bar"
#         return None

#     # ---------- normalize ----------
#     measure = (intent.get("measures") or ["value_sales"])
#     measure = measure[0] if isinstance(measure, list) else measure
#     dims               = intent.get("dims") or []
#     filters            = dict(intent.get("filters") or {})
#     _topn_raw          = intent.get("top_n")
#     top_n              = int(_topn_raw) if _topn_raw is not None else 5
#     time               = intent.get("time_range") or {}
#     mode               = (time.get("mode") or "").upper()
#     brand_group        = bool(intent.get("brand_group"))
#     has_brand_filter   = bool(intent.get("has_brand_filter"))
#     asked_yoy          = bool(intent.get("is_yoy"))
#     task               = intent.get("task") or "table"

#     if brand_group and "brand" in filters:
#         filters.pop("brand", None)

#     # ---------- date column ----------
#     df = df.copy()
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     df["date"] = pd.to_datetime(df["date"])
#     dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

#     # ---------- choose window ----------
#     if mode == "MAT":
#         start, end = compute_mat_window(df)
#     elif mode == "YTD":
#         system_today  = pd.Timestamp.today()
#         prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
#         end   = min(prev_full_end, dataset_last_full)
#         start = pd.Timestamp(f"{end.year}-01-01")
#     elif "start" in time and "end" in time:
#         start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
#         end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
#         end   = min(end, dataset_last_full)
#     else:
#         start = df["date"].min().to_period("M").to_timestamp(how="start")
#         end   = dataset_last_full

#     # ---------- base frame ----------
#     base = apply_filters(df, filters)

#     # ===================== MoM BRANCH =====================
#     measures_list = intent.get("measures") or []
#     need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
#     if need_mom:
#         # (unchanged)
#         pass

#     # ===================== YoY BRANCH (MAT / YTD / CUSTOM supported) =====================
#     if asked_yoy:
#         use_unit     = "unit_sales" in (intent.get("measures") or [])
#         base_measure = "unit_sales" if use_unit else "value_sales"
#         curr_col     = f"{base_measure}_curr"
#         prev_col     = f"{base_measure}_prev"
#         yoy_col      = "unit_yoy" if use_unit else "value_yoy"

#         dims_for_yoy = [d for d in (dims or []) if d != "date"]
#         dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         cur_mask = (base["date"] >= start) & (base["date"] <= end)
#         sliced   = base.loc[cur_mask]
#         cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})

#         prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#         prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#         prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
#                         .rename(columns={base_measure: prev_col})

#         out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
#                else pd.concat([cur_agg, prev_agg], axis=1))

#         prev_vals = out[prev_col]
#         cur_vals  = out[curr_col]
#         with np.errstate(divide="ignore", invalid="ignore"):
#             out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

#         if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
#             out = out.sort_values(yoy_col, ascending=False, na_position="last")
#             if brand_group and "brand" in out.columns:
#                 out = out.drop_duplicates(subset=["brand"], keep="first")
#             out = out.head(top_n)

#         out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#         chart_type = _decide_chart_type(task, dims_for_yoy, asked_yoy=True, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
#                 "dims": dims_for_yoy,
#                 "measure": yoy_col,
#                 "filters": filters,
#                 "mode": mode or "CUSTOM",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ===================== Non-MoM/YoY =====================
#     work = base.loc[(base["date"] >= start) & (base["date"] <= end)]

#     if intent.get("task") == "topn":
#         preferred_dim = None
#         if brand_group and "brand" in df.columns:
#             preferred_dim = "brand"
#         else:
#             candidates = [d for d in (dims or []) if d != "date" and d not in filters]
#             preferred_dim = candidates[0] if candidates else None

#         if preferred_dim is None:
#             out = aggregate(work, dims=[], measure_col=measure)
#             for lbl in ("category", "market", "channel", "brand"):
#                 if lbl in filters:
#                     out[lbl] = filters[lbl]
#             label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#             out = out[label_cols + [c for c in out.columns if c not in label_cols]]
#             out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#             chart_type = _decide_chart_type("topn", [], asked_yoy=False, brand_group=brand_group)
#             return {
#                 "data": out,
#                 "meta": {
#                     "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                     "dims": [],
#                     "measure": measure,
#                     "filters": filters,
#                     "mode": mode or None,
#                     "rowcount": int(out.shape[0]),
#                     "chart_type": chart_type,
#                 },
#             }

#         out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
#         if preferred_dim == "brand" and "brand" in out.columns:
#             out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
#         else:
#             out = out.head(top_n)
#         out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#         chart_type = _decide_chart_type("topn", [preferred_dim], asked_yoy=False, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "dims": [preferred_dim],
#                 "measure": measure,
#                 "filters": filters,
#                 "mode": mode or None,
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ---------- normal aggregate / chart (monthly-friendly output) ----------
#     if not ("date" in dims and intent.get("task") == "chart"):
#         dims = [d for d in (dims or []) if d != "date"]
#     if not brand_group:
#         dims = [d for d in dims if d != "brand"]

#     out = aggregate(work, dims=dims, measure_col=measure)

#     # ✅ Monthly table & chart hygiene (no math changes)
#     if "date" in out.columns:
#         # normalize to month start and add readable label
#         out["date"] = pd.to_datetime(out["date"]).dt.to_period("M").dt.to_timestamp(how="start")
#         out["month"] = out["date"].dt.strftime("%b %Y")
#         # if no series dims, one row per month
#         series_dims = [d for d in dims if d != "date"]
#         if len(series_dims) == 0:
#             out = out.groupby(["date", "month"], as_index=False)[measure].sum()
#         # always sort chronologically and drop duplicate monthly rows per series
#         dedupe_keys = ["date"] + series_dims
#         out = out.sort_values("date", ascending=True).drop_duplicates(subset=dedupe_keys, keep="first")

#     # At the very end of run_pandas_intent, right before return {...}

# # --- Final output cleanup ---
#     out = out.replace([np.inf, -np.inf], np.nan).fillna(0)

#     # Convert date → month-year string for readability
#     if "date" in out.columns:
#         out["month"] = pd.to_datetime(out["date"]).dt.strftime("%b %Y")
#         out = out.drop(columns=["date"])  # remove raw date, only keep month

#     chart_type = _decide_chart_type(task, dims, asked_yoy=False, brand_group=brand_group)

#     return {
#         "data": out,
#         "meta": {
#             "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#             "dims": dims,
#             "measure": measure,
#             "filters": filters,
#             "mode": mode or None,
#             "rowcount": int(out.shape[0]),
#             "chart_type": chart_type,
#         },
#     }


#Bar chart , Line chart added MAT comparisons remaining , when calculating YoY not charts showing YoY% growth





# Working code MAT YoY,YTD, TopN, Brand Grouping
# backend/nlp/pandas_runner.py
# import pandas as pd
# import numpy as np
# from typing import Dict, Any, List, Optional, Tuple

# # ---------- helpers ----------
# def _suggest_chart_type(task: str,
#                         dims: list,
#                         measure: str,
#                         rowcount: int,
#                         is_time: bool) -> str:
#     """
#     Heuristic chart chooser.
#     Returns one of: "line", "bar", "pie", "table"
#     """
#     # Explicit chart task with date → line
#     if task == "chart" and is_time:
#         return "line"

#     # If date present in result → line (timeseries)
#     if is_time:
#         return "line"

#     # Single categorical dim, small N → pie; larger N → bar
#     if len(dims) == 1 and dims[0] != "date":
#         if rowcount <= 8:
#             return "pie"
#         return "bar"

#     # Multiple categorical dims → bar (stack/group handled by front-end)
#     if len(dims) >= 2 and "date" not in dims:
#         return "bar"

#     # Fallbacks
#     if task == "chart":
#         return "bar"
#     return "table"

# def _system_last_full_month_end(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
#     now = now or pd.Timestamp.today()
#     return (now.to_period("M") - 1).to_timestamp(how="end")

# def _month_bounds_from_end(month_end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return (month_start, month_end) for the given month_end (normalized to month)."""
#     me = month_end.to_period("M").to_timestamp(how="end")
#     ms = me.to_period("M").to_timestamp(how="start")
#     return ms, me

# def _prev_month_end(month_end: pd.Timestamp) -> pd.Timestamp:
#     """End of the immediately previous month."""
#     return (month_end.to_period("M") - 1).to_timestamp(how="end")

# def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return the previous-year window aligned to the same months."""
#     prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#     prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#     return prev_start, prev_end

# def _aggregate(df: pd.DataFrame, dims: List[str], measure_col: str):
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True, dropna=False)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return df.groupby(gcols, dropna=False)[measure_col].sum().reset_index()

# def periods_from_system_now(now: Optional[pd.Timestamp] = None) -> Dict[str, pd.Timestamp]:
#     """System-time aware anchors (used for YTD fallback)."""
#     now = now or pd.Timestamp.today()
#     ytd_start = pd.Timestamp(f"{now.year}-01-01")
#     ytd_end   = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
#     mat_end   = ytd_end
#     mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

# def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT = last 12 complete months ending at the previous full month (by system time),
#     clamped to the latest full month that exists in the dataset.
#     Returns (start, end) as month-start and month-end timestamps.
#     """
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     dates = pd.to_datetime(df["date"])
#     system_today   = system_today or pd.Timestamp.today()
#     prev_full_end  = (system_today.to_period("M") - 1).to_timestamp(how="end")
#     dataset_last   = dates.max().to_period("M").to_timestamp(how="end")
#     mat_end        = min(prev_full_end, dataset_last)
#     mat_start      = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return mat_start.normalize(), mat_end.normalize()

# # ---------- core compute ----------

# def apply_filters(df, filters):
#     out = df.copy()
#     for col, val in (filters or {}).items():
#         if col not in out.columns:
#             continue
#         # case-insensitive, trimmed comparisons
#         if isinstance(val, list):
#             vals = [str(v).strip().lower() for v in val]
#             out = out[out[col].astype(str).str.strip().str.lower().isin(vals)]
#         else:
#             v = str(val).strip().lower()
#             out = out[out[col].astype(str).str.strip().str.lower() == v]
#     return out

# def aggregate(df: pd.DataFrame, dims: List[str], measure_col: str = "value_sales") -> pd.DataFrame:
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return (
#         df.groupby(gcols, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#     )

# def compute_topN(df: pd.DataFrame, dim: str, measure_col: str, n: int) -> pd.DataFrame:
#     return (
#         df.groupby(dim, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#           .head(n)
#     )

# # ------------------------------ main entry ------------------------------


# def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     intent dict:
#       - task: "topn" | "table" | "chart"
#       - dims: list (e.g., ["brand"])
#       - measures: list or str (default "value_sales")
#       - filters: dict (e.g., {"category":"Biscuits","market":"India"})
#       - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
#       - top_n: int
#       - mom: bool
#       - is_yoy: bool (explicit YoY request)
#       - brand_group: bool (explicit "by brand" request)
#       - has_brand_filter: bool (explicit brand fixed by filter)
#     """
#     import numpy as np
#     from typing import List, Optional  # keep for helper types

#     # ---------- tiny helper: choose a chart hint for the FRONTEND ----------
#     def _decide_chart_type(task: str, dims_used: List[str], asked_yoy: bool, brand_group: bool) -> Optional[str]:
#         dims_used = dims_used or []
#         if "date" in dims_used:
#             return "line"
#         if task == "chart":
#             if any(d in dims_used for d in ("brand", "category", "market", "channel", "segment", "manufacturer")):
#                 return "bar"
#         if task == "topn":
#             return "bar"
#         if asked_yoy and (brand_group or any(d in dims_used for d in ("brand", "category", "market", "channel"))):
#             return "bar"
#         return None

#     # ---------- normalize ----------
#     measure = (intent.get("measures") or ["value_sales"])
#     measure = measure[0] if isinstance(measure, list) else measure
#     dims               = intent.get("dims") or []
#     filters            = dict(intent.get("filters") or {})
#     _topn_raw          = intent.get("top_n")
#     top_n              = int(_topn_raw) if _topn_raw is not None else 5
#     time               = intent.get("time_range") or {}
#     mode               = (time.get("mode") or "").upper()
#     brand_group        = bool(intent.get("brand_group"))
#     has_brand_filter   = bool(intent.get("has_brand_filter"))
#     asked_yoy          = bool(intent.get("is_yoy"))
#     task               = intent.get("task") or "table"

#     if brand_group and "brand" in filters:
#         filters.pop("brand", None)

#     # ---------- date column ----------
#     df = df.copy()
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     df["date"] = pd.to_datetime(df["date"])
#     dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

#     # ---------- choose window ----------
#     if mode == "MAT":
#         start, end = compute_mat_window(df)
#     elif mode == "YTD":
#         system_today  = pd.Timestamp.today()
#         prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
#         end   = min(prev_full_end, dataset_last_full)
#         start = pd.Timestamp(f"{end.year}-01-01")
#     elif "start" in time and "end" in time:
#         start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
#         end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
#         end   = min(end, dataset_last_full)
#     else:
#         start = df["date"].min().to_period("M").to_timestamp(how="start")
#         end   = dataset_last_full

#     # ---------- base frame ----------
#     base = apply_filters(df, filters)

#     # ===================== MoM BRANCH =====================
#     measures_list = intent.get("measures") or []
#     need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
#     if need_mom:
#         # (unchanged)
#         pass

#     # ===================== YoY BRANCH (MAT / YTD / CUSTOM supported) =====================
#     if asked_yoy:
#         use_unit     = "unit_sales" in (intent.get("measures") or [])
#         base_measure = "unit_sales" if use_unit else "value_sales"
#         curr_col     = f"{base_measure}_curr"
#         prev_col     = f"{base_measure}_prev"
#         yoy_col      = "unit_yoy" if use_unit else "value_yoy"

#         dims_for_yoy = [d for d in (dims or []) if d != "date"]
#         dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         cur_mask = (base["date"] >= start) & (base["date"] <= end)
#         sliced   = base.loc[cur_mask]
#         cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})

#         prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#         prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#         prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
#                         .rename(columns={base_measure: prev_col})

#         out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
#                else pd.concat([cur_agg, prev_agg], axis=1))

#         prev_vals = out[prev_col]
#         cur_vals  = out[curr_col]
#         with np.errstate(divide="ignore", invalid="ignore"):
#             out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

#         if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
#             out = out.sort_values(yoy_col, ascending=False, na_position="last")
#             if brand_group and "brand" in out.columns:
#                 out = out.drop_duplicates(subset=["brand"], keep="first")
#             out = out.head(top_n)

#         out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#         chart_type = _decide_chart_type(task, dims_for_yoy, asked_yoy=True, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
#                 "dims": dims_for_yoy,
#                 "measure": yoy_col,
#                 "filters": filters,
#                 "mode": mode or "CUSTOM",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ===================== Non-MoM/YoY =====================
#     work = base.loc[(base["date"] >= start) & (base["date"] <= end)]

#     if intent.get("task") == "topn":
#         preferred_dim = None
#         if brand_group and "brand" in df.columns:
#             preferred_dim = "brand"
#         else:
#             candidates = [d for d in (dims or []) if d != "date" and d not in filters]
#             preferred_dim = candidates[0] if candidates else None

#         if preferred_dim is None:
#             out = aggregate(work, dims=[], measure_col=measure)
#             for lbl in ("category", "market", "channel", "brand"):
#                 if lbl in filters:
#                     out[lbl] = filters[lbl]
#             label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#             out = out[label_cols + [c for c in out.columns if c not in label_cols]]
#             out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#             chart_type = _decide_chart_type("topn", [], asked_yoy=False, brand_group=brand_group)
#             return {
#                 "data": out,
#                 "meta": {
#                     "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                     "dims": [],
#                     "measure": measure,
#                     "filters": filters,
#                     "mode": mode or None,
#                     "rowcount": int(out.shape[0]),
#                     "chart_type": chart_type,
#                 },
#             }

#         out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
#         if preferred_dim == "brand" and "brand" in out.columns:
#             out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
#         else:
#             out = out.head(top_n)
#         out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
#         chart_type = _decide_chart_type("topn", [preferred_dim], asked_yoy=False, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "dims": [preferred_dim],
#                 "measure": measure,
#                 "filters": filters,
#                 "mode": mode or None,
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ---------- normal aggregate / chart (monthly-friendly output) ----------
#     if not ("date" in dims and intent.get("task") == "chart"):
#         dims = [d for d in (dims or []) if d != "date"]
#     if not brand_group:
#         dims = [d for d in dims if d != "brand"]

#     out = aggregate(work, dims=dims, measure_col=measure)

#     # ✅ Monthly table & chart hygiene (no math changes)
#     if "date" in out.columns:
#         # normalize to month start and add readable label
#         out["date"] = pd.to_datetime(out["date"]).dt.to_period("M").dt.to_timestamp(how="start")
#         out["month"] = out["date"].dt.strftime("%b %Y")
#         # if no series dims, one row per month
#         series_dims = [d for d in dims if d != "date"]
#         if len(series_dims) == 0:
#             out = out.groupby(["date", "month"], as_index=False)[measure].sum()
#         # always sort chronologically and drop duplicate monthly rows per series
#         dedupe_keys = ["date"] + series_dims
#         out = out.sort_values("date", ascending=True).drop_duplicates(subset=dedupe_keys, keep="first")

#     # At the very end of run_pandas_intent, right before return {...}

# # --- Final output cleanup ---
#     out = out.replace([np.inf, -np.inf], np.nan).fillna(0)

#     # Convert date → month-year string for readability
#     if "date" in out.columns:
#         out["month"] = pd.to_datetime(out["date"]).dt.strftime("%b %Y")
#         out = out.drop(columns=["date"])  # remove raw date, only keep month

#     chart_type = _decide_chart_type(task, dims, asked_yoy=False, brand_group=brand_group)

#     return {
#         "data": out,
#         "meta": {
#             "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#             "dims": dims,
#             "measure": measure,
#             "filters": filters,
#             "mode": mode or None,
#             "rowcount": int(out.shape[0]),
#             "chart_type": chart_type,
#         },
#     }





#Bar chart for YoY single brand not showing Yoy change mat, MAT comparisons added everything else working fine

# import pandas as pd
# import numpy as np
# from typing import Dict, Any, List, Optional, Tuple


# # near the top of run_pandas_intent (after imports inside the function)
# def _safe_numeric_fill(df: pd.DataFrame) -> pd.DataFrame:
#     df = df.copy()
#     df.replace([np.inf, -np.inf], np.nan, inplace=True)
#     num_cols = df.select_dtypes(include=[np.number]).columns
#     if len(num_cols) > 0:
#         df[num_cols] = df[num_cols].fillna(0)
#     return df

# # ---------- helpers ----------
# def _suggest_chart_type(task: str,
#                         dims: list,
#                         measure: str,
#                         rowcount: int,
#                         is_time: bool) -> str:
#     """
#     Heuristic chart chooser.
#     Returns one of: "line", "bar", "pie", "table"
#     """
#     # Explicit chart task with date → line
#     if task == "chart" and is_time:
#         return "line"

#     # If date present in result → line (timeseries)
#     if is_time:
#         return "line"

#     # Single categorical dim, small N → pie; larger N → bar
#     if len(dims) == 1 and dims[0] != "date":
#         if rowcount <= 8:
#             return "pie"
#         return "bar"

#     # Multiple categorical dims → bar (stack/group handled by front-end)
#     if len(dims) >= 2 and "date" not in dims:
#         return "bar"

#     # Fallbacks
#     if task == "chart":
#         return "bar"
#     return "table"

# def _system_last_full_month_end(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
#     now = now or pd.Timestamp.today()
#     return (now.to_period("M") - 1).to_timestamp(how="end")

# def _month_bounds_from_end(month_end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return (month_start, month_end) for the given month_end (normalized to month)."""
#     me = month_end.to_period("M").to_timestamp(how="end")
#     ms = me.to_period("M").to_timestamp(how="start")
#     return ms, me

# def _prev_month_end(month_end: pd.Timestamp) -> pd.Timestamp:
#     """End of the immediately previous month."""
#     return (month_end.to_period("M") - 1).to_timestamp(how="end")

# def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return the previous-year window aligned to the same months."""
#     prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#     prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#     return prev_start, prev_end

# def _aggregate(df: pd.DataFrame, dims: List[str], measure_col: str):
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True, dropna=False)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return df.groupby(gcols, dropna=False)[measure_col].sum().reset_index()

# def periods_from_system_now(now: Optional[pd.Timestamp] = None) -> Dict[str, pd.Timestamp]:
#     """System-time aware anchors (used for YTD fallback)."""
#     now = now or pd.Timestamp.today()
#     ytd_start = pd.Timestamp(f"{now.year}-01-01")
#     ytd_end   = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
#     mat_end   = ytd_end
#     mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

# def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT = last 12 complete months ending at the previous full month (by system time),
#     clamped to the latest full month that exists in the dataset.
#     Returns (start, end) as month-start and month-end timestamps.
#     """
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     dates = pd.to_datetime(df["date"])
#     system_today   = system_today or pd.Timestamp.today()
#     prev_full_end  = (system_today.to_period("M") - 1).to_timestamp(how="end")
#     dataset_last   = dates.max().to_period("M").to_timestamp(how="end")
#     mat_end        = min(prev_full_end, dataset_last)
#     mat_start      = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return mat_start.normalize(), mat_end.normalize()

# # ---------- core compute ----------

# def apply_filters(df, filters):
#     out = df.copy()
#     for col, val in (filters or {}).items():
#         if col not in out.columns:
#             continue
#         # case-insensitive, trimmed comparisons
#         if isinstance(val, list):
#             vals = [str(v).strip().lower() for v in val]
#             out = out[out[col].astype(str).str.strip().str.lower().isin(vals)]
#         else:
#             v = str(val).strip().lower()
#             out = out[out[col].astype(str).str.strip().str.lower() == v]
#     return out

# def aggregate(df: pd.DataFrame, dims: List[str], measure_col: str = "value_sales") -> pd.DataFrame:
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return (
#         df.groupby(gcols, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#     )

# def compute_topN(df: pd.DataFrame, dim: str, measure_col: str, n: int) -> pd.DataFrame:
#     return (
#         df.groupby(dim, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#           .head(n)
#     )

# # ------------------------------ main entry ------------------------------


# def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     intent dict:
#       - task: "topn" | "table" | "chart"
#       - dims: list (e.g., ["brand"])
#       - measures: list or str (default "value_sales")
#       - filters: dict (e.g., {"category":"Biscuits","market":"India"})
#       - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
#       - top_n: int
#       - mom: bool
#       - is_yoy: bool (explicit YoY request)
#       - brand_group: bool (explicit "by brand" request)
#       - has_brand_filter: bool (explicit brand fixed by filter)
#       - raw_text: original user question (string)
#     """
#     import numpy as np
#     import re
#     from typing import List, Optional

#     # ---- numeric-only sanitizer to avoid filling categoricals with 0 ----
#     def _safe_numeric_fill(frame: pd.DataFrame) -> pd.DataFrame:
#         f = frame.copy()
#         # replace inf with NaN everywhere first
#         f.replace([np.inf, -np.inf], np.nan, inplace=True)
#         # fill only numeric columns with 0
#         num_cols = f.select_dtypes(include=[np.number]).columns
#         if len(num_cols) > 0:
#             f[num_cols] = f[num_cols].fillna(0)
#         return f

#     # ---------- tiny helper: choose a chart hint for the FRONTEND ----------
#     def _decide_chart_type(task: str, dims_used: List[str], asked_yoy: bool, brand_group: bool) -> Optional[str]:
#         dims_used = dims_used or []
#         if "date" in dims_used:
#             return "line"
#         if task == "chart":
#             if any(d in dims_used for d in ("brand", "category", "market", "channel", "segment", "manufacturer")):
#                 return "bar"
#         if task == "topn":
#             return "bar"
#         if asked_yoy and (brand_group or any(d in dims_used for d in ("brand", "category", "market", "channel"))):
#             return "bar"
#         return None

#     # ---------- normalize ----------
#     measure               = (intent.get("measures") or ["value_sales"])
#     measure               = measure[0] if isinstance(measure, list) else measure
#     dims                  = intent.get("dims") or []
#     filters               = dict(intent.get("filters") or {})
#     _topn_raw             = intent.get("top_n")
#     top_n                 = int(_topn_raw) if _topn_raw is not None else 5
#     time                  = intent.get("time_range") or {}
#     mode                  = (time.get("mode") or "").upper()
#     brand_group           = bool(intent.get("brand_group"))
#     has_brand_filter      = bool(intent.get("has_brand_filter"))
#     asked_yoy             = bool(intent.get("is_yoy"))
#     task                  = intent.get("task") or "table"
#     raw_text              = (intent.get("raw_text") or "").lower()

#     # If grouping by brand, drop any brand filter (avoid double restriction)
#     if brand_group and "brand" in filters:
#         filters.pop("brand", None)

#     # ---------- date column ----------
#     df = df.copy()
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     df["date"] = pd.to_datetime(df["date"])
#     dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

#     # ---------- choose window for ordinary (single) runs ----------
#     if mode == "MAT":
#         start, end = compute_mat_window(df)  # unchanged
#     elif mode == "YTD":
#         system_today  = pd.Timestamp.today()
#         prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
#         end   = min(prev_full_end, dataset_last_full)
#         start = pd.Timestamp(f"{end.year}-01-01")
#     elif "start" in time and "end" in time:
#         start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
#         end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
#         end   = min(end, dataset_last_full)
#     else:
#         start = df["date"].min().to_period("M").to_timestamp(how="start")
#         end   = dataset_last_full

#     # ---------- base frame ----------
#     base = apply_filters(df, filters)

#     # ===================== MAT COMPARISON BRANCH (unchanged logic) =====================
#     # ===================== MAT COMPARISON BRANCH =====================
#     def _extract_mat_years(text: str) -> List[int]:
#         years = []
#         for y in re.findall(r"\bmat[\s\-]?((?:20)?\d{2})\b", text):
#             y = int(y)
#             if y < 100:
#                 y = 2000 + y
#             years.append(y)
#         seen, ordered = set(), []
#         for y in years:
#             if y not in seen:
#                 ordered.append(y); seen.add(y)
#         return ordered

#     mat_years = _extract_mat_years(raw_text)
#     has_compare_tokens = any(tok in raw_text for tok in ["compare", "vs", "versus", "comparison"])
#     is_mat_compare_query = ("mat" in raw_text) and (has_compare_tokens or len(mat_years) >= 2)

#     if is_mat_compare_query:
#         system_prev_end = (pd.Timestamp.today().to_period("M") - 1).to_timestamp(how="end")
#         anchor_month = system_prev_end.month
#         if not mat_years:
#             mat_years = [system_prev_end.year, system_prev_end.year - 1]

#         measures_list = intent.get("measures") or []
#         use_unit = "unit_sales" in measures_list or measure == "unit_sales"
#         base_measure = "unit_sales" if use_unit else "value_sales"

#         dims_for_cmp = [d for d in (dims or []) if d != "date"]
#         dims_for_cmp = [d for d in dims_for_cmp if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_cmp = [d for d in dims_for_cmp if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         frames, labels = [], []
#         # track overall min start / max end so we can populate meta["window"]
#         overall_start, overall_end = None, None

#         for y in mat_years:
#             cmp_end = pd.Timestamp(year=y, month=anchor_month, day=1).to_period("M").to_timestamp(how="end")
#             cmp_end = min(cmp_end, dataset_last_full)
#             cmp_start = (cmp_end.to_period("M") - 11).to_timestamp(how="start")

#             # track span
#             overall_start = cmp_start if overall_start is None else min(overall_start, cmp_start)
#             overall_end   = cmp_end   if overall_end   is None else max(overall_end,   cmp_end)

#             mask = (base["date"] >= cmp_start) & (base["date"] <= cmp_end)
#             agg = _agg(base.loc[mask], dims_for_cmp, base_measure)
#             label = f"MAT {y}"
#             agg.insert(0, "mat_label", label)
#             frames.append(agg); labels.append(label)

#         out = pd.concat(frames, axis=0, ignore_index=True) if frames else pd.DataFrame(columns=(["mat_label"] + dims_for_cmp + [base_measure]))
#         if "mat_label" in out.columns and labels:
#             out["mat_label"] = pd.Categorical(out["mat_label"], categories=labels, ordered=True)

#         out = _safe_numeric_fill(out)

#         return {
#             "data": out,
#             "meta": {
#                 "mat_compare": {
#                     "anchor_month": anchor_month,
#                     "years": mat_years,
#                     "labels": labels,
#                 },
#                 # ✅ add a synthetic window so callers like main.py can safely read it
#                 "window": {
#                     "start": (overall_start.date().isoformat() if overall_start is not None else None),
#                     "end":   (overall_end.date().isoformat()   if overall_end   is not None else None),
#                 },
#                 "dims": (["mat_label"] + dims_for_cmp),
#                 "measure": base_measure,
#                 "filters": filters,
#                 "mode": "MAT_COMPARE",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": "bar",
#             },
#         }
# # =================== END: MAT COMPARISON BRANCH ===================


#     # ===================== MoM BRANCH (left unchanged) =====================
#     measures_list = intent.get("measures") or []
#     need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
#     if need_mom:
#         # ... your existing MoM logic lives here ...
#         pass

#     # ===================== YoY BRANCH (unchanged math) =====================
#     if asked_yoy:
#         use_unit     = "unit_sales" in (intent.get("measures") or [])
#         base_measure = "unit_sales" if use_unit else "value_sales"
#         curr_col     = f"{base_measure}_curr"
#         prev_col     = f"{base_measure}_prev"
#         yoy_col      = "unit_yoy" if use_unit else "value_yoy"

#         dims_for_yoy = [d for d in (dims or []) if d != "date"]
#         dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         cur_mask = (base["date"] >= start) & (base["date"] <= end)
#         sliced   = base.loc[cur_mask]
#         cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})

#         prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#         prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#         prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
#                         .rename(columns={base_measure: prev_col})

#         out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
#                else pd.concat([cur_agg, prev_agg], axis=1))

#         prev_vals = out[prev_col]
#         cur_vals  = out[curr_col]
#         with np.errstate(divide="ignore", invalid="ignore"):
#             out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

#         if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
#             out = out.sort_values(yoy_col, ascending=False, na_position="last")
#             if brand_group and "brand" in out.columns:
#                 out = out.drop_duplicates(subset=["brand"], keep="first")
#             out = out.head(top_n)

#         out = _safe_numeric_fill(out)

#         chart_type = _decide_chart_type(task, dims_for_yoy, asked_yoy=True, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
#                 "dims": dims_for_yoy,
#                 "measure": yoy_col,
#                 "filters": filters,
#                 "mode": mode or "CUSTOM",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ===================== Non-MoM/YoY =====================
#     work = base.loc[(base["date"] >= start) & (base["date"] <= end)]

#     if intent.get("task") == "topn":
#         preferred_dim = None
#         if brand_group and "brand" in df.columns:
#             preferred_dim = "brand"
#         else:
#             candidates = [d for d in (dims or []) if d != "date" and d not in filters]
#             preferred_dim = candidates[0] if candidates else None

#         if preferred_dim is None:
#             out = aggregate(work, dims=[], measure_col=measure)
#             for lbl in ("category", "market", "channel", "brand"):
#                 if lbl in filters:
#                     out[lbl] = filters[lbl]
#             label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#             out = out[label_cols + [c for c in out.columns if c not in label_cols]]

#             out = _safe_numeric_fill(out)

#             chart_type = _decide_chart_type("topn", [], asked_yoy=False, brand_group=brand_group)
#             return {
#                 "data": out,
#                 "meta": {
#                     "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                     "dims": [],
#                     "measure": measure,
#                     "filters": filters,
#                     "mode": mode or None,
#                     "rowcount": int(out.shape[0]),
#                     "chart_type": chart_type,
#                 },
#             }

#         out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
#         if preferred_dim == "brand" and "brand" in out.columns:
#             out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
#         else:
#             out = out.head(top_n)

#         out = _safe_numeric_fill(out)

#         chart_type = _decide_chart_type("topn", [preferred_dim], asked_yoy=False, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "dims": [preferred_dim],
#                 "measure": measure,
#                 "filters": filters,
#                 "mode": mode or None,
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # normal aggregate / chart
#     if not ("date" in dims and intent.get("task") == "chart"):
#         dims = [d for d in (dims or []) if d != "date"]
#     if not brand_group:
#         dims = [d for d in dims if d != "brand"]

#     out = aggregate(work, dims=dims, measure_col=measure)
#     if not dims:
#         for lbl in ("category", "market", "channel", "brand"):
#             if lbl in filters:
#                 out[lbl] = filters[lbl]
#         label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#         out = out[label_cols + [c for c in out.columns if c not in label_cols]]

#     out = _safe_numeric_fill(out)

#     chart_type = _decide_chart_type(task, dims, asked_yoy=False, brand_group=brand_group)
#     return {
#         "data": out,
#         "meta": {
#             "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#             "dims": dims,
#             "measure": measure,
#             "filters": filters,
#             "mode": mode or None,
#             "rowcount": int(out.shape[0]),
#             "chart_type": chart_type,
#         },
#     }





#Working code Line trends by brand, YoY MAT,etc working






# import pandas as pd
# import numpy as np
# from typing import Dict, Any, List, Optional, Tuple


# # near the top of run_pandas_intent (after imports inside the function)
# def _safe_numeric_fill(df: pd.DataFrame) -> pd.DataFrame:
#     df = df.copy(
#     df.replace([np.inf, -np.inf], np.nan, inplace=True)
#     num_cols = df.select_dtypes(include=[np.number]).columns
#     if len(num_cols) > 0:
#         df[num_cols] = df[num_cols].fillna(0)
#     return df

# # ---------- helpers ----------
# def _suggest_chart_type(task: str,
#                         dims: list,
#                         measure: str,
#                         rowcount: int,
#                         is_time: bool) -> str:
#     """
#     Heuristic chart chooser.
#     Returns one of: "line", "bar", "pie", "table"
#     """
#     # Explicit chart task with date → line
#     if task == "chart" and is_time:
#         return "line"

#     # If date present in result → line (timeseries)
#     if is_time:
#         return "line"

#     # Single categorical dim, small N → pie; larger N → bar
#     if len(dims) == 1 and dims[0] != "date":
#         if rowcount <= 8:
#             return "pie"
#         return "bar"

#     # Multiple categorical dims → bar (stack/group handled by front-end)
#     if len(dims) >= 2 and "date" not in dims:
#         return "bar"

#     # Fallbacks
#     if task == "chart":
#         return "bar"
#     return "table"

# def _system_last_full_month_end(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
#     now = now or pd.Timestamp.today()
#     return (now.to_period("M") - 1).to_timestamp(how="end")

# def _month_bounds_from_end(month_end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return (month_start, month_end) for the given month_end (normalized to month)."""
#     me = month_end.to_period("M").to_timestamp(how="end")
#     ms = me.to_period("M").to_timestamp(how="start")
#     return ms, me

# def _prev_month_end(month_end: pd.Timestamp) -> pd.Timestamp:
#     """End of the immediately previous month."""
#     return (month_end.to_period("M") - 1).to_timestamp(how="end")

# def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return the previous-year window aligned to the same months."""
#     prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#     prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#     return prev_start, prev_end

# def _aggregate(df: pd.DataFrame, dims: List[str], measure_col: str):
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True, dropna=False)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return df.groupby(gcols, dropna=False)[measure_col].sum().reset_index()

# def periods_from_system_now(now: Optional[pd.Timestamp] = None) -> Dict[str, pd.Timestamp]:
#     """System-time aware anchors (used for YTD fallback)."""
#     now = now or pd.Timestamp.today()
#     ytd_start = pd.Timestamp(f"{now.year}-01-01")
#     ytd_end   = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
#     mat_end   = ytd_end
#     mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

# def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT = last 12 complete months ending at the previous full month (by system time),
#     clamped to the latest full month that exists in the dataset.
#     Returns (start, end) as month-start and month-end timestamps.
#     """
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     dates = pd.to_datetime(df["date"])
#     system_today   = system_today or pd.Timestamp.today()
#     prev_full_end  = (system_today.to_period("M") - 1).to_timestamp(how="end")
#     dataset_last   = dates.max().to_period("M").to_timestamp(how="end")
#     mat_end        = min(prev_full_end, dataset_last)
#     mat_start      = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return mat_start.normalize(), mat_end.normalize()

# # ---------- core compute ----------

# def apply_filters(df, filters):
#     out = df.copy()
#     for col, val in (filters or {}).items():
#         if col not in out.columns:
#             continue

#         # Normalize the column to lower/trimmed strings for case-insensitive matching
#         col_series = out[col].astype(str).str.strip().str.lower()

#         # Multiple values (e.g., ["alpha", "beta"] or set/tuple) → IN filter
#         if isinstance(val, (list, tuple, set)):
#             norm_vals = {str(v).strip().lower() for v in val if v is not None and str(v).strip() != ""}
#             if not norm_vals:
#                 continue  # nothing to filter on
#             out = out[col_series.isin(norm_vals)]
#             continue

#         # Single value (skip None/empty)
#         if val is None or (isinstance(val, str) and val.strip() == ""):
#             continue
#         v = str(val).strip().lower()
#         out = out[col_series == v]

#     return out


# def aggregate(df: pd.DataFrame, dims: List[str], measure_col: str = "value_sales") -> pd.DataFrame:
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return (
#         df.groupby(gcols, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#     )

# def compute_topN(df: pd.DataFrame, dim: str, measure_col: str, n: int) -> pd.DataFrame:
#     return (
#         df.groupby(dim, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#           .head(n)
#     )

# # ------------------------------ main entry ------------------------------


# def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     intent dict:
#       - task: "topn" | "table" | "chart"
#       - dims: list (e.g., ["brand"])
#       - measures: list or str (default "value_sales")
#       - filters: dict (e.g., {"category":"Biscuits","market":"India"})
#       - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
#       - top_n: int
#       - mom: bool
#       - is_yoy: bool
#       - brand_group: bool
#       - has_brand_filter: bool
#       - raw_text: original user question (string)
#     """
#     import numpy as np
#     import re
#     from typing import List, Optional

#     # ---- numeric-only sanitizer (avoid categorical fill with 0) ----
#     def _safe_numeric_fill(frame: pd.DataFrame) -> pd.DataFrame:
#         f = frame.copy()
#         f.replace([np.inf, -np.inf], np.nan, inplace=True)
#         num_cols = f.select_dtypes(include=[np.number]).columns
#         if len(num_cols) > 0:
#             f[num_cols] = f[num_cols].fillna(0)
#         return f

#     # ---------- tiny helper: choose a chart hint for the FRONTEND ----------
#     def _decide_chart_type(task: str, dims_used: List[str], asked_yoy: bool, brand_group: bool) -> Optional[str]:
#         dims_used = dims_used or []
#         if "date" in dims_used:
#             return "line"
#         if task == "chart":
#             if any(d in dims_used for d in ("brand", "category", "market", "channel", "segment", "manufacturer")):
#                 return "bar"
#         if task == "topn":
#             return "bar"
#         if asked_yoy and (brand_group or any(d in dims_used for d in ("brand", "category", "market", "channel"))):
#             return "bar"
#         return None

#     # ---------- normalize ----------
#     measure               = (intent.get("measures") or ["value_sales"])
#     measure               = measure[0] if isinstance(measure, list) else measure
#     dims                  = intent.get("dims") or []
#     filters               = dict(intent.get("filters") or {})
#     _topn_raw             = intent.get("top_n")
#     top_n                 = int(_topn_raw) if _topn_raw is not None else 5
#     time                  = intent.get("time_range") or {}
#     mode                  = (time.get("mode") or "").upper()
#     brand_group           = bool(intent.get("brand_group"))
#     has_brand_filter      = bool(intent.get("has_brand_filter"))
#     asked_yoy             = bool(intent.get("is_yoy"))
#     task                  = intent.get("task") or "table"
#     raw_text              = (intent.get("raw_text") or "").lower()

#     # ---------- date column ----------
#     df = df.copy()
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     df["date"] = pd.to_datetime(df["date"])
#     dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

#     # ---------- NEW: extract multi-brand from the raw text when NLP didn't set filters ----------
#     # (keeps existing behavior if filters.brand is already present)
#     if ("brand" not in filters) or (not filters["brand"]):
#         if "brand" in df.columns and raw_text:
#             # normalize helper
#             def _norm(s: str) -> str:
#                 return re.sub(r"[^a-z0-9]+", "", str(s).lower())
#             text_norm = _norm(raw_text)

#             # try to read explicit lists after "brand"/"brands"
#             explicit_tokens: List[str] = []
#             for m in re.findall(r"brands?\s*[:\-]?\s*([a-z0-9 /,&+\-]+)", raw_text):
#                 parts = re.split(r"\s*(?:,|and|&|\+|vs|versus)\s*", m)
#                 explicit_tokens.extend([p for p in parts if p.strip()])

#             uniq_brands = pd.Series(df["brand"].astype(str).str.strip()).dropna().unique()
#             # inverse map for fuzzy token match
#             inv = {_norm(b): b for b in uniq_brands}

#             chosen: List[str] = []

#             if explicit_tokens:
#                 for tok in explicit_tokens:
#                     key = _norm(tok)
#                     if key in inv and inv[key] not in chosen:
#                         chosen.append(inv[key])
#             else:
#                 # fallback: scan all brands inside the question
#                 for b in uniq_brands:
#                     if _norm(b) and _norm(b) in text_norm and b not in chosen:
#                         chosen.append(b)

#             if chosen:
#                 filters["brand"] = chosen
#                 if len(chosen) > 1:
#                     brand_group = True

#     # --- keep your old splitter for a single brand string like "Alpha, Beta" in filters ---
#     bval = filters.get("brand")
#     if isinstance(bval, str):
#         parts = [p.strip() for p in re.split(r"\s*(?:,|and|&|\+)\s*", bval, flags=re.I) if p.strip()]
#         if len(parts) > 1:
#             filters["brand"] = parts
#             brand_group = True

#     # If grouping by brand, drop a single fixed brand (avoid double restriction)
#     if brand_group and "brand" in filters:
#         is_single = not isinstance(filters["brand"], (list, tuple, set)) or len(filters["brand"]) <= 1
#         if is_single:
#             filters.pop("brand", None)

#     # ---------- choose window for ordinary (single) runs ----------
#     if mode == "MAT":
#         start, end = compute_mat_window(df)  # unchanged
#     elif mode == "YTD":
#         system_today  = pd.Timestamp.today()
#         prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
#         end   = min(prev_full_end, dataset_last_full)
#         start = pd.Timestamp(f"{end.year}-01-01")
#     elif "start" in time and "end" in time:
#         start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
#         end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
#         end   = min(end, dataset_last_full)
#     else:
#         start = df["date"].min().to_period("M").to_timestamp(how="start")
#         end   = dataset_last_full

#     # ---------- base frame ----------
#     base = apply_filters(df, filters)

#     # ===================== MAT COMPARISON BRANCH (unchanged) =====================
#     def _extract_mat_years(text: str) -> List[int]:
#         years = []
#         for y in re.findall(r"\bmat[\s\-]?((?:20)?\d{2})\b", text):
#             y = int(y)
#             if y < 100:
#                 y = 2000 + y
#             years.append(y)
#         seen, ordered = set(), []
#         for y in years:
#             if y not in seen:
#                 ordered.append(y); seen.add(y)
#         return ordered

#     mat_years = _extract_mat_years(raw_text)
#     has_compare_tokens = any(tok in raw_text for tok in ["compare", "vs", "versus", "comparison"])
#     is_mat_compare_query = ("mat" in raw_text) and (has_compare_tokens or len(mat_years) >= 2)

#     if is_mat_compare_query:
#         system_prev_end = (pd.Timestamp.today().to_period("M") - 1).to_timestamp(how="end")
#         anchor_month = system_prev_end.month
#         if not mat_years:
#             mat_years = [system_prev_end.year, system_prev_end.year - 1]
#         measures_list = intent.get("measures") or []
#         use_unit = "unit_sales" in measures_list or measure == "unit_sales"
#         base_measure = "unit_sales" if use_unit else "value_sales"

#         dims_for_cmp = [d for d in (dims or []) if d != "date"]
#         dims_for_cmp = [d for d in dims_for_cmp if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_cmp = [d for d in dims_for_cmp if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         frames, labels = [], []
#         overall_start, overall_end = None, None
#         for y in mat_years:
#             cmp_end = pd.Timestamp(year=y, month=anchor_month, day=1).to_period("M").to_timestamp(how="end")
#             cmp_end = min(cmp_end, dataset_last_full)
#             cmp_start = (cmp_end.to_period("M") - 11).to_timestamp(how="start")
#             overall_start = cmp_start if overall_start is None else min(overall_start, cmp_start)
#             overall_end   = cmp_end   if overall_end   is None else max(overall_end,   cmp_end)
#             mask = (base["date"] >= cmp_start) & (base["date"] <= cmp_end)
#             agg = _agg(base.loc[mask], dims_for_cmp, base_measure)
#             label = f"MAT {y}"
#             agg.insert(0, "mat_label", label)
#             frames.append(agg); labels.append(label)

#         out = pd.concat(frames, axis=0, ignore_index=True) if frames else pd.DataFrame(columns=(["mat_label"] + dims_for_cmp + [base_measure]))
#         if "mat_label" in out.columns and labels:
#             out["mat_label"] = pd.Categorical(out["mat_label"], categories=labels, ordered=True)

#         out = _safe_numeric_fill(out)
#         return {
#             "data": out,
#             "meta": {
#                 "mat_compare": {"anchor_month": anchor_month, "years": mat_years, "labels": labels},
#                 "window": {
#                     "start": (overall_start.date().isoformat() if overall_start is not None else None),
#                     "end":   (overall_end.date().isoformat()   if overall_end   is not None else None),
#                 },
#                 "dims": (["mat_label"] + dims_for_cmp),
#                 "measure": base_measure,
#                 "filters": filters,
#                 "mode": "MAT_COMPARE",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": "bar",
#             },
#         }

#     # ===================== MoM BRANCH (your code unchanged) =====================
#     measures_list = intent.get("measures") or []
#     need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
#     if need_mom:
#         # ... your existing MoM logic ...
#         pass

#     # ===================== YoY BRANCH (unchanged math) =====================
#     if asked_yoy:
#         use_unit     = "unit_sales" in (intent.get("measures") or [])
#         base_measure = "unit_sales" if use_unit else "value_sales"
#         curr_col     = f"{base_measure}_curr"
#         prev_col     = f"{base_measure}_prev"
#         yoy_col      = "unit_yoy" if use_unit else "value_yoy"

#         dims_for_yoy = [d for d in (dims or []) if d != "date"]
#         dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         cur_mask = (base["date"] >= start) & (base["date"] <= end)
#         sliced   = base.loc[cur_mask]
#         cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})
#         prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#         prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#         prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
#                         .rename(columns={base_measure: prev_col})

#         out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
#                else pd.concat([cur_agg, prev_agg], axis=1))

#         prev_vals = out[prev_col]; cur_vals = out[curr_col]
#         with np.errstate(divide="ignore", invalid="ignore"):
#             out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

#         if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
#             out = out.sort_values(yoy_col, ascending=False, na_position="last")
#             if brand_group and "brand" in out.columns:
#                 out = out.drop_duplicates(subset=["brand"], keep="first")
#             out = out.head(top_n)

#         out = _safe_numeric_fill(out)
#         chart_type = _decide_chart_type(task, dims_for_yoy, asked_yoy=True, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
#                 "dims": dims_for_yoy,
#                 "measure": yoy_col,
#                 "filters": filters,
#                 "mode": mode or "CUSTOM",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ===================== Non-MoM/YoY =====================
#     work = base.loc[(base["date"] >= start) & (base["date"] <= end)]

#     if intent.get("task") == "topn":
#         preferred_dim = None
#         if brand_group and "brand" in df.columns:
#             preferred_dim = "brand"
#         else:
#             candidates = [d for d in (dims or []) if d != "date" and d not in filters]
#             preferred_dim = candidates[0] if candidates else None

#         if preferred_dim is None:
#             out = aggregate(work, dims=[], measure_col=measure)
#             for lbl in ("category", "market", "channel", "brand"):
#                 if lbl in filters:
#                     out[lbl] = filters[lbl]
#             label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#             out = out[label_cols + [c for c in out.columns if c not in label_cols]]
#             out = _safe_numeric_fill(out)
#             chart_type = _decide_chart_type("topn", [], asked_yoy=False, brand_group=brand_group)
#             return {
#                 "data": out,
#                 "meta": {
#                     "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                     "dims": [],
#                     "measure": measure,
#                     "filters": filters,
#                     "mode": mode or None,
#                     "rowcount": int(out.shape[0]),
#                     "chart_type": chart_type,
#                 },
#             }

#         out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
#         if preferred_dim == "brand" and "brand" in out.columns:
#             out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
#         else:
#             out = out.head(top_n)
#         out = _safe_numeric_fill(out)
#         chart_type = _decide_chart_type("topn", [preferred_dim], asked_yoy=False, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "dims": [preferred_dim],
#                 "measure": measure,
#                 "filters": filters,
#                 "mode": mode or None,
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ---------- normal aggregate / chart ----------
#     # NEW: if it's a time-series chart and multiple brands were requested (or brand_group=True),
#     # ensure 'brand' stays in dims so the frontend gets one line per brand.
#     multi_brand = isinstance(filters.get("brand"), (list, tuple, set)) and len(filters["brand"]) > 1
#     if intent.get("task") == "chart" and ("date" in (dims or [])) and (multi_brand or brand_group):
#         if "brand" not in dims:
#             dims = [*dims, "brand"]

#     # your existing pruning rules
#     if not ("date" in dims and intent.get("task") == "chart"):
#         dims = [d for d in (dims or []) if d != "date"]
#     if not brand_group:
#         dims = [d for d in dims if d != "brand"]

#     out = aggregate(work, dims=dims, measure_col=measure)
#     if not dims:
#         for lbl in ("category", "market", "channel", "brand"):
#             if lbl in filters:
#                 out[lbl] = filters[lbl]
#         label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#         out = out[label_cols + [c for c in out.columns if c not in label_cols]]

#     out = _safe_numeric_fill(out)
#     chart_type = _decide_chart_type(task, dims, asked_yoy=False, brand_group=brand_group)
#     return {
#         "data": out,
#         "meta": {
#             "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#             "dims": dims,
#             "measure": measure,
#             "filters": filters,
#             "mode": mode or None,
#             "rowcount": int(out.shape[0]),
#             "chart_type": chart_type,
#         },
#     }











#Working code bad insights




#Final Intent parser rule based working code
# import pandas as pd
# import numpy as np
# from typing import Dict, Any, List, Optional, Tuple


# # near the top of run_pandas_intent (after imports inside the function)
# def _safe_numeric_fill(df: pd.DataFrame) -> pd.DataFrame:
#     df = df.copy()
#     df.replace([np.inf, -np.inf], np.nan, inplace=True)
#     num_cols = df.select_dtypes(include=[np.number]).columns
#     if len(num_cols) > 0:
#         df[num_cols] = df[num_cols].fillna(0)
#     return df

# # ---------- helpers ----------


# import random

# def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:
#     insights = []
#     if df.empty:
#         return ["No data available to generate insights."]

#     # Find measure
#     measure = meta.get("measure") or "value_sales"
#     if measure not in df.columns:
#         # fallback: first numeric col
#         num_cols = df.select_dtypes(include="number").columns
#         if len(num_cols) == 0:
#             return ["No numeric data found."]
#         measure = num_cols[0]

#     # Pick a categorical dimension if present
#     dims = meta.get("dims") or []
#     cat_dim = None
#     for d in ["brand","category","market","channel","segment","manufacturer"]:
#         if d in df.columns:
#             cat_dim = d
#             break

#     if cat_dim:
#         top_row = df.sort_values(measure, ascending=False).iloc[0]
#         insights.append(f"🏆 {top_row[cat_dim]} leads with {measure.replace('_',' ')} of {top_row[measure]:,.0f}.")
#         if len(df) > 1:
#             second = df.sort_values(measure, ascending=False).iloc[1]
#             insights.append(f"👉 {second[cat_dim]} follows with {second[measure]:,.0f}.")
#         if len(df) >= 3:
#             bottom = df.sort_values(measure, ascending=True).iloc[0]
#             insights.append(f"⬇️ Lowest is {bottom[cat_dim]} at {bottom[measure]:,.0f}.")
#     else:
#         total = df[measure].sum()
#         insights.append(f"📊 Total {measure.replace('_',' ')}: {total:,.0f}.")
#         avg = df[measure].mean()
#         insights.append(f"📈 Average {measure.replace('_',' ')}: {avg:,.0f}.")

#     # Randomize to keep variety
#     random.shuffle(insights)
#     return insights[:3]

# def _suggest_chart_type(task: str,
#                         dims: list,
#                         measure: str,
#                         rowcount: int,
#                         is_time: bool) -> str:
#     """
#     Heuristic chart chooser.
#     Returns one of: "line", "bar", "pie", "table"
#     """
#     # Explicit chart task with date → line
#     if task == "chart" and is_time:
#         return "line"

#     # If date present in result → line (timeseries)
#     if is_time:
#         return "line"

#     # Single categorical dim, small N → pie; larger N → bar
#     if len(dims) == 1 and dims[0] != "date":
#         if rowcount <= 8:
#             return "pie"
#         return "bar"

#     # Multiple categorical dims → bar (stack/group handled by front-end)
#     if len(dims) >= 2 and "date" not in dims:
#         return "bar"

#     # Fallbacks
#     if task == "chart":
#         return "bar"
#     return "table"

# def _system_last_full_month_end(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
#     now = now or pd.Timestamp.today()
#     return (now.to_period("M") - 1).to_timestamp(how="end")

# def _month_bounds_from_end(month_end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return (month_start, month_end) for the given month_end (normalized to month)."""
#     me = month_end.to_period("M").to_timestamp(how="end")
#     ms = me.to_period("M").to_timestamp(how="start")
#     return ms, me

# def _prev_month_end(month_end: pd.Timestamp) -> pd.Timestamp:
#     """End of the immediately previous month."""
#     return (month_end.to_period("M") - 1).to_timestamp(how="end")

# def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """Return the previous-year window aligned to the same months."""
#     prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#     prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#     return prev_start, prev_end

# def _aggregate(df: pd.DataFrame, dims: List[str], measure_col: str):
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True, dropna=False)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return df.groupby(gcols, dropna=False)[measure_col].sum().reset_index()

# def periods_from_system_now(now: Optional[pd.Timestamp] = None) -> Dict[str, pd.Timestamp]:
#     """System-time aware anchors (used for YTD fallback)."""
#     now = now or pd.Timestamp.today()
#     ytd_start = pd.Timestamp(f"{now.year}-01-01")
#     ytd_end   = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
#     mat_end   = ytd_end
#     mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

# def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT = last 12 complete months ending at the previous full month (by system time),
#     clamped to the latest full month that exists in the dataset.
#     Returns (start, end) as month-start and month-end timestamps.
#     """
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     dates = pd.to_datetime(df["date"])
#     system_today   = system_today or pd.Timestamp.today()
#     prev_full_end  = (system_today.to_period("M") - 1).to_timestamp(how="end")
#     dataset_last   = dates.max().to_period("M").to_timestamp(how="end")
#     mat_end        = min(prev_full_end, dataset_last)
#     mat_start      = (mat_end.to_period("M") - 11).to_timestamp(how="start")
#     return mat_start.normalize(), mat_end.normalize()

# # ---------- core compute ----------

# def apply_filters(df, filters):
#     out = df.copy()
#     for col, val in (filters or {}).items():
#         if col not in out.columns:
#             continue

#         # Normalize the column to lower/trimmed strings for case-insensitive matching
#         col_series = out[col].astype(str).str.strip().str.lower()

#         # Multiple values (e.g., ["alpha", "beta"] or set/tuple) → IN filter
#         if isinstance(val, (list, tuple, set)):
#             norm_vals = {str(v).strip().lower() for v in val if v is not None and str(v).strip() != ""}
#             if not norm_vals:
#                 continue  # nothing to filter on
#             out = out[col_series.isin(norm_vals)]
#             continue

#         # Single value (skip None/empty)
#         if val is None or (isinstance(val, str) and val.strip() == ""):
#             continue
#         v = str(val).strip().lower()
#         out = out[col_series == v]

#     return out


# def aggregate(df: pd.DataFrame, dims: List[str], measure_col: str = "value_sales") -> pd.DataFrame:
#     gcols = [c for c in (dims or []) if c in df.columns]
#     if not gcols:
#         return df.groupby(lambda _: True)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
#     return (
#         df.groupby(gcols, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#     )

# def compute_topN(df: pd.DataFrame, dim: str, measure_col: str, n: int) -> pd.DataFrame:
#     return (
#         df.groupby(dim, dropna=False)[measure_col]
#           .sum()
#           .reset_index()
#           .sort_values(measure_col, ascending=False)
#           .head(n)
#     )

# # ------------------------------ main entry ------------------------------


# def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     intent dict:
#       - task: "topn" | "table" | "chart"
#       - dims: list (e.g., ["brand"])
#       - measures: list or str (default "value_sales")
#       - filters: dict (e.g., {"category":"Biscuits","market":"India"})
#       - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
#       - top_n: int
#       - mom: bool
#       - is_yoy: bool
#       - brand_group: bool
#       - has_brand_filter: bool
#       - raw_text: original user question (string)
#     """
#     import numpy as np
#     import re
#     from typing import List, Optional

#     # ---- numeric-only sanitizer (avoid categorical fill with 0) ----
#     def _safe_numeric_fill(frame: pd.DataFrame) -> pd.DataFrame:
#         f = frame.copy()
#         f.replace([np.inf, -np.inf], np.nan, inplace=True)
#         num_cols = f.select_dtypes(include=[np.number]).columns
#         if len(num_cols) > 0:
#             f[num_cols] = f[num_cols].fillna(0)
#         return f

#     # ---------- tiny helper: choose a chart hint for the FRONTEND ----------
#     def _decide_chart_type(task: str, dims_used: List[str], asked_yoy: bool, brand_group: bool) -> Optional[str]:
#         dims_used = dims_used or []
#         if "date" in dims_used:
#             return "line"
#         if task == "chart":
#             if any(d in dims_used for d in ("brand", "category", "market", "channel", "segment", "manufacturer")):
#                 return "bar"
#         if task == "topn":
#             return "bar"
#         if asked_yoy and (brand_group or any(d in dims_used for d in ("brand", "category", "market", "channel"))):
#             return "bar"
#         return None

#     # ---------- normalize ----------
#     measure               = (intent.get("measures") or ["value_sales"])
#     measure               = measure[0] if isinstance(measure, list) else measure
#     dims                  = intent.get("dims") or []
#     filters               = dict(intent.get("filters") or {})
#     _topn_raw             = intent.get("top_n")
#     top_n                 = int(_topn_raw) if _topn_raw is not None else 5
#     time                  = intent.get("time_range") or {}
#     mode                  = (time.get("mode") or "").upper()
#     brand_group           = bool(intent.get("brand_group"))
#     has_brand_filter      = bool(intent.get("has_brand_filter"))
#     asked_yoy             = bool(intent.get("is_yoy"))
#     task                  = intent.get("task") or "table"
#     raw_text              = (intent.get("raw_text") or "").lower()

#     # ---------- date column ----------
#     df = df.copy()
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     df["date"] = pd.to_datetime(df["date"])
#     dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

#     # ---------- NEW: extract multi-brand from the raw text when NLP didn't set filters ----------
#     # (keeps existing behavior if filters.brand is already present)
#     if ("brand" not in filters) or (not filters["brand"]):
#         if "brand" in df.columns and raw_text:
#             # normalize helper
#             def _norm(s: str) -> str:
#                 return re.sub(r"[^a-z0-9]+", "", str(s).lower())
#             text_norm = _norm(raw_text)

#             # try to read explicit lists after "brand"/"brands"
#             explicit_tokens: List[str] = []
#             for m in re.findall(r"brands?\s*[:\-]?\s*([a-z0-9 /,&+\-]+)", raw_text):
#                 parts = re.split(r"\s*(?:,|and|&|\+|vs|versus)\s*", m)
#                 explicit_tokens.extend([p for p in parts if p.strip()])

#             uniq_brands = pd.Series(df["brand"].astype(str).str.strip()).dropna().unique()
#             # inverse map for fuzzy token match
#             inv = {_norm(b): b for b in uniq_brands}

#             chosen: List[str] = []

#             if explicit_tokens:
#                 for tok in explicit_tokens:
#                     key = _norm(tok)
#                     if key in inv and inv[key] not in chosen:
#                         chosen.append(inv[key])
#             else:
#                 # fallback: scan all brands inside the question
#                 for b in uniq_brands:
#                     if _norm(b) and _norm(b) in text_norm and b not in chosen:
#                         chosen.append(b)

#             if chosen:
#                 filters["brand"] = chosen
#                 if len(chosen) > 1:
#                     brand_group = True

#     # --- keep your old splitter for a single brand string like "Alpha, Beta" in filters ---
#     bval = filters.get("brand")
#     if isinstance(bval, str):
#         parts = [p.strip() for p in re.split(r"\s*(?:,|and|&|\+)\s*", bval, flags=re.I) if p.strip()]
#         if len(parts) > 1:
#             filters["brand"] = parts
#             brand_group = True

#     # If grouping by brand, drop a single fixed brand (avoid double restriction)
#     if brand_group and "brand" in filters:
#         is_single = not isinstance(filters["brand"], (list, tuple, set)) or len(filters["brand"]) <= 1
#         if is_single:
#             filters.pop("brand", None)

#     # ---------- choose window for ordinary (single) runs ----------
#     if mode == "MAT":
#         start, end = compute_mat_window(df)  # unchanged
#     elif mode == "YTD":
#         system_today  = pd.Timestamp.today()
#         prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
#         end   = min(prev_full_end, dataset_last_full)
#         start = pd.Timestamp(f"{end.year}-01-01")
#     elif "start" in time and "end" in time:
#         start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
#         end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
#         end   = min(end, dataset_last_full)
#     else:
#         start = df["date"].min().to_period("M").to_timestamp(how="start")
#         end   = dataset_last_full

#     # ---------- base frame ----------
#     base = apply_filters(df, filters)

#     # ===================== MAT COMPARISON BRANCH (unchanged) =====================
#     def _extract_mat_years(text: str) -> List[int]:
#         years = []
#         for y in re.findall(r"\bmat[\s\-]?((?:20)?\d{2})\b", text):
#             y = int(y)
#             if y < 100:
#                 y = 2000 + y
#             years.append(y)
#         seen, ordered = set(), []
#         for y in years:
#             if y not in seen:
#                 ordered.append(y); seen.add(y)
#         return ordered

#     mat_years = _extract_mat_years(raw_text)
#     has_compare_tokens = any(tok in raw_text for tok in ["compare", "vs", "versus", "comparison"])
#     is_mat_compare_query = ("mat" in raw_text) and (has_compare_tokens or len(mat_years) >= 2)

#     if is_mat_compare_query:
#         system_prev_end = (pd.Timestamp.today().to_period("M") - 1).to_timestamp(how="end")
#         anchor_month = system_prev_end.month
#         if not mat_years:
#             mat_years = [system_prev_end.year, system_prev_end.year - 1]
#         measures_list = intent.get("measures") or []
#         use_unit = "unit_sales" in measures_list or measure == "unit_sales"
#         base_measure = "unit_sales" if use_unit else "value_sales"

#         dims_for_cmp = [d for d in (dims or []) if d != "date"]
#         dims_for_cmp = [d for d in dims_for_cmp if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_cmp = [d for d in dims_for_cmp if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         frames, labels = [], []
#         overall_start, overall_end = None, None
#         for y in mat_years:
#             cmp_end = pd.Timestamp(year=y, month=anchor_month, day=1).to_period("M").to_timestamp(how="end")
#             cmp_end = min(cmp_end, dataset_last_full)
#             cmp_start = (cmp_end.to_period("M") - 11).to_timestamp(how="start")
#             overall_start = cmp_start if overall_start is None else min(overall_start, cmp_start)
#             overall_end   = cmp_end   if overall_end   is None else max(overall_end,   cmp_end)
#             mask = (base["date"] >= cmp_start) & (base["date"] <= cmp_end)
#             agg = _agg(base.loc[mask], dims_for_cmp, base_measure)
#             label = f"MAT {y}"
#             agg.insert(0, "mat_label", label)
#             frames.append(agg); labels.append(label)

#         out = pd.concat(frames, axis=0, ignore_index=True) if frames else pd.DataFrame(columns=(["mat_label"] + dims_for_cmp + [base_measure]))
#         if "mat_label" in out.columns and labels:
#             out["mat_label"] = pd.Categorical(out["mat_label"], categories=labels, ordered=True)

#         out = _safe_numeric_fill(out)
#         return {
#             "data": out,
#             "meta": {
#                 "mat_compare": {"anchor_month": anchor_month, "years": mat_years, "labels": labels},
#                 "window": {
#                     "start": (overall_start.date().isoformat() if overall_start is not None else None),
#                     "end":   (overall_end.date().isoformat()   if overall_end   is not None else None),
#                 },
#                 "dims": (["mat_label"] + dims_for_cmp),
#                 "measure": base_measure,
#                 "filters": filters,
#                 "mode": "MAT_COMPARE",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": "bar",
#             },
#         }

#     # ===================== MoM BRANCH (your code unchanged) =====================
#     measures_list = intent.get("measures") or []
#     need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
#     if need_mom:
#         # ... your existing MoM logic ...
#         pass

#     # ===================== YoY BRANCH (unchanged math) =====================
#     if asked_yoy:
#         use_unit     = "unit_sales" in (intent.get("measures") or [])
#         base_measure = "unit_sales" if use_unit else "value_sales"
#         curr_col     = f"{base_measure}_curr"
#         prev_col     = f"{base_measure}_prev"
#         yoy_col      = "unit_yoy" if use_unit else "value_yoy"

#         dims_for_yoy = [d for d in (dims or []) if d != "date"]
#         dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
#         if not brand_group:
#             dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

#         def _agg(frame, gcols, col):
#             if gcols:
#                 return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
#             return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

#         cur_mask = (base["date"] >= start) & (base["date"] <= end)
#         sliced   = base.loc[cur_mask]
#         cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})
#         prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
#         prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
#         prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
#                         .rename(columns={base_measure: prev_col})

#         out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
#                else pd.concat([cur_agg, prev_agg], axis=1))

#         prev_vals = out[prev_col]; cur_vals = out[curr_col]
#         with np.errstate(divide="ignore", invalid="ignore"):
#             out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

#         if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
#             out = out.sort_values(yoy_col, ascending=False, na_position="last")
#             if brand_group and "brand" in out.columns:
#                 out = out.drop_duplicates(subset=["brand"], keep="first")
#             out = out.head(top_n)

#         out = _safe_numeric_fill(out)
#         chart_type = _decide_chart_type(task, dims_for_yoy, asked_yoy=True, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
#                 "dims": dims_for_yoy,
#                 "measure": yoy_col,
#                 "filters": filters,
#                 "mode": mode or "CUSTOM",
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ===================== Non-MoM/YoY =====================
#     work = base.loc[(base["date"] >= start) & (base["date"] <= end)]

#     if intent.get("task") == "topn":
#         preferred_dim = None
#         if brand_group and "brand" in df.columns:
#             preferred_dim = "brand"
#         else:
#             candidates = [d for d in (dims or []) if d != "date" and d not in filters]
#             preferred_dim = candidates[0] if candidates else None

#         if preferred_dim is None:
#             out = aggregate(work, dims=[], measure_col=measure)
#             for lbl in ("category", "market", "channel", "brand"):
#                 if lbl in filters:
#                     out[lbl] = filters[lbl]
#             label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#             out = out[label_cols + [c for c in out.columns if c not in label_cols]]
#             out = _safe_numeric_fill(out)
#             chart_type = _decide_chart_type("topn", [], asked_yoy=False, brand_group=brand_group)
#             return {
#                 "data": out,
#                 "meta": {
#                     "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                     "dims": [],
#                     "measure": measure,
#                     "filters": filters,
#                     "mode": mode or None,
#                     "rowcount": int(out.shape[0]),
#                     "chart_type": chart_type,
#                 },
#             }

#         out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
#         if preferred_dim == "brand" and "brand" in out.columns:
#             out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
#         else:
#             out = out.head(top_n)
#         out = _safe_numeric_fill(out)
#         chart_type = _decide_chart_type("topn", [preferred_dim], asked_yoy=False, brand_group=brand_group)
#         return {
#             "data": out,
#             "meta": {
#                 "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#                 "dims": [preferred_dim],
#                 "measure": measure,
#                 "filters": filters,
#                 "mode": mode or None,
#                 "rowcount": int(out.shape[0]),
#                 "chart_type": chart_type,
#             },
#         }

#     # ---------- normal aggregate / chart ----------
#     # NEW: if it's a time-series chart and multiple brands were requested (or brand_group=True),
#     # ensure 'brand' stays in dims so the frontend gets one line per brand.
#     multi_brand = isinstance(filters.get("brand"), (list, tuple, set)) and len(filters["brand"]) > 1
#     if intent.get("task") == "chart" and ("date" in (dims or [])) and (multi_brand or brand_group):
#         if "brand" not in dims:
#             dims = [*dims, "brand"]

#     # your existing pruning rules
#     if not ("date" in dims and intent.get("task") == "chart"):
#         dims = [d for d in (dims or []) if d != "date"]
#     if not brand_group:
#         dims = [d for d in dims if d != "brand"]

#     out = aggregate(work, dims=dims, measure_col=measure)
#     if not dims:
#         for lbl in ("category", "market", "channel", "brand"):
#             if lbl in filters:
#                 out[lbl] = filters[lbl]
#         label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
#         out = out[label_cols + [c for c in out.columns if c not in label_cols]]

#     out = _safe_numeric_fill(out)
#     chart_type = _decide_chart_type(task, dims, asked_yoy=False, brand_group=brand_group)
#     return {
#         "data": out,
#         "meta": {
#             "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#             "dims": dims,
#             "measure": measure,
#             "filters": filters,
#             "mode": mode or None,
#             "rowcount": int(out.shape[0]),
#             "chart_type": chart_type,
#         },
#     }











import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple


# near the top of run_pandas_intent (after imports inside the function)
def _safe_numeric_fill(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) > 0:
        df[num_cols] = df[num_cols].fillna(0)
    return df

# ---------- helpers ----------


import random

def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:
    insights = []
    if df.empty:
        return ["No data available to generate insights."]

    # Find measure
    measure = meta.get("measure") or "value_sales"
    if measure not in df.columns:
        # fallback: first numeric col
        num_cols = df.select_dtypes(include="number").columns
        if len(num_cols) == 0:
            return ["No numeric data found."]
        measure = num_cols[0]

    # Pick a categorical dimension if present
    dims = meta.get("dims") or []
    cat_dim = None
    for d in ["brand","category","market","channel","segment","manufacturer"]:
        if d in df.columns:
            cat_dim = d
            break

    if cat_dim:
        top_row = df.sort_values(measure, ascending=False).iloc[0]
        insights.append(f"🏆 {top_row[cat_dim]} leads with {measure.replace('_',' ')} of {top_row[measure]:,.0f}.")
        if len(df) > 1:
            second = df.sort_values(measure, ascending=False).iloc[1]
            insights.append(f"👉 {second[cat_dim]} follows with {second[measure]:,.0f}.")
        if len(df) >= 3:
            bottom = df.sort_values(measure, ascending=True).iloc[0]
            insights.append(f"⬇️ Lowest is {bottom[cat_dim]} at {bottom[measure]:,.0f}.")
    else:
        total = df[measure].sum()
        insights.append(f"📊 Total {measure.replace('_',' ')}: {total:,.0f}.")
        avg = df[measure].mean()
        insights.append(f"📈 Average {measure.replace('_',' ')}: {avg:,.0f}.")

    # Randomize to keep variety
    random.shuffle(insights)
    return insights[:3]

def _suggest_chart_type(task: str,
                        dims: list,
                        measure: str,
                        rowcount: int,
                        is_time: bool) -> str:
    """
    Heuristic chart chooser.
    Returns one of: "line", "bar", "pie", "table"
    """
    # Explicit chart task with date → line
    if task == "chart" and is_time:
        return "line"

    # If date present in result → line (timeseries)
    if is_time:
        return "line"

    # Single categorical dim, small N → pie; larger N → bar
    if len(dims) == 1 and dims[0] != "date":
        if rowcount <= 8:
            return "pie"
        return "bar"

    # Multiple categorical dims → bar (stack/group handled by front-end)
    if len(dims) >= 2 and "date" not in dims:
        return "bar"

    # Fallbacks
    if task == "chart":
        return "bar"
    return "table"

def _system_last_full_month_end(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
    now = now or pd.Timestamp.today()
    return (now.to_period("M") - 1).to_timestamp(how="end")

def _month_bounds_from_end(month_end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Return (month_start, month_end) for the given month_end (normalized to month)."""
    me = month_end.to_period("M").to_timestamp(how="end")
    ms = me.to_period("M").to_timestamp(how="start")
    return ms, me

def _prev_month_end(month_end: pd.Timestamp) -> pd.Timestamp:
    """End of the immediately previous month."""
    return (month_end.to_period("M") - 1).to_timestamp(how="end")

def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Return the previous-year window aligned to the same months."""
    prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
    prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
    return prev_start, prev_end

def _aggregate(df: pd.DataFrame, dims: List[str], measure_col: str):
    gcols = [c for c in (dims or []) if c in df.columns]
    if not gcols:
        return df.groupby(lambda _: True, dropna=False)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
    return df.groupby(gcols, dropna=False)[measure_col].sum().reset_index()

def periods_from_system_now(now: Optional[pd.Timestamp] = None) -> Dict[str, pd.Timestamp]:
    """System-time aware anchors (used for YTD fallback)."""
    now = now or pd.Timestamp.today()
    ytd_start = pd.Timestamp(f"{now.year}-01-01")
    ytd_end   = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
    mat_end   = ytd_end
    mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
    return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    MAT = last 12 complete months ending at the previous full month (by system time),
    clamped to the latest full month that exists in the dataset.
    Returns (start, end) as month-start and month-end timestamps.
    """
    if "date" not in df.columns:
        raise ValueError("Data must have a 'date' column.")
    dates = pd.to_datetime(df["date"])
    system_today   = system_today or pd.Timestamp.today()
    prev_full_end  = (system_today.to_period("M") - 1).to_timestamp(how="end")
    dataset_last   = dates.max().to_period("M").to_timestamp(how="end")
    mat_end        = min(prev_full_end, dataset_last)
    mat_start      = (mat_end.to_period("M") - 11).to_timestamp(how="start")
    return mat_start.normalize(), mat_end.normalize()

# ---------- core compute ----------

def apply_filters(df, filters):
    out = df.copy()
    for col, val in (filters or {}).items():
        if col not in out.columns:
            continue

        # Normalize the column to lower/trimmed strings for case-insensitive matching
        col_series = out[col].astype(str).str.strip().str.lower()

        # Multiple values (e.g., ["alpha", "beta"] or set/tuple) → IN filter
        if isinstance(val, (list, tuple, set)):
            norm_vals = {str(v).strip().lower() for v in val if v is not None and str(v).strip() != ""}
            if not norm_vals:
                continue  # nothing to filter on
            out = out[col_series.isin(norm_vals)]
            continue

        # Single value (skip None/empty)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            continue
        v = str(val).strip().lower()
        out = out[col_series == v]

    return out


def aggregate(df: pd.DataFrame, dims: List[str], measure_col: str = "value_sales") -> pd.DataFrame:
    gcols = [c for c in (dims or []) if c in df.columns]
    if not gcols:
        return df.groupby(lambda _: True)[measure_col].sum().reset_index(drop=True).to_frame(measure_col)
    return (
        df.groupby(gcols, dropna=False)[measure_col]
          .sum()
          .reset_index()
          .sort_values(measure_col, ascending=False)
    )

def compute_topN(df: pd.DataFrame, dim: str, measure_col: str, n: int) -> pd.DataFrame:
    return (
        df.groupby(dim, dropna=False)[measure_col]
          .sum()
          .reset_index()
          .sort_values(measure_col, ascending=False)
          .head(n)
    )

# ------------------------------ main entry ------------------------------


def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    intent dict:
      - task: "topn" | "table" | "chart"
      - dims: list (e.g., ["brand"])
      - measures: list or str (default "value_sales")
      - filters: dict (e.g., {"category":"Biscuits","market":"India"})
      - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
      - top_n: int
      - mom: bool
      - is_yoy: bool
      - brand_group: bool
      - has_brand_filter: bool
      - raw_text: original user question (string)
    """
    import numpy as np
    import re
    from typing import List, Optional

    # ---- numeric-only sanitizer (avoid categorical fill with 0) ----
    def _safe_numeric_fill(frame: pd.DataFrame) -> pd.DataFrame:
        f = frame.copy()
        f.replace([np.inf, -np.inf], np.nan, inplace=True)
        num_cols = f.select_dtypes(include=[np.number]).columns
        if len(num_cols) > 0:
            f[num_cols] = f[num_cols].fillna(0)
        return f

    # ---------- tiny helper: choose a chart hint for the FRONTEND ----------
    def _decide_chart_type(task: str, dims_used: List[str], asked_yoy: bool, brand_group: bool) -> Optional[str]:
        dims_used = dims_used or []
        if "date" in dims_used:
            return "line"
        if task == "chart":
            if any(d in dims_used for d in ("brand", "category", "market", "channel", "segment", "manufacturer")):
                return "bar"
        if task == "topn":
            return "bar"
        if asked_yoy and (brand_group or any(d in dims_used for d in ("brand", "category", "market", "channel"))):
            return "bar"
        return None

    # ---------- normalize ----------
    measure               = (intent.get("measures") or ["value_sales"])
    measure               = measure[0] if isinstance(measure, list) else measure
    dims                  = intent.get("dims") or []
    filters               = dict(intent.get("filters") or {})
    _topn_raw             = intent.get("top_n")
    top_n                 = int(_topn_raw) if _topn_raw is not None else 5
    time                  = intent.get("time_range") or {}
    mode                  = (time.get("mode") or "").upper()
    brand_group           = bool(intent.get("brand_group"))
    has_brand_filter      = bool(intent.get("has_brand_filter"))
    asked_yoy             = bool(intent.get("is_yoy"))
    task                  = intent.get("task") or "table"
    raw_text              = (intent.get("raw_text") or "").lower()

    # ---------- date column ----------
    df = df.copy()
    if "date" not in df.columns:
        raise ValueError("Data must have a 'date' column.")
    df["date"] = pd.to_datetime(df["date"])
    dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

    # ---------- NEW: extract multi-brand from the raw text when NLP didn't set filters ----------
    # (keeps existing behavior if filters.brand is already present)
    if ("brand" not in filters) or (not filters["brand"]):
        if "brand" in df.columns and raw_text:
            # normalize helper
            def _norm(s: str) -> str:
                return re.sub(r"[^a-z0-9]+", "", str(s).lower())
            text_norm = _norm(raw_text)

            # try to read explicit lists after "brand"/"brands"
            explicit_tokens: List[str] = []
            for m in re.findall(r"brands?\s*[:\-]?\s*([a-z0-9 /,&+\-]+)", raw_text):
                parts = re.split(r"\s*(?:,|and|&|\+|vs|versus)\s*", m)
                explicit_tokens.extend([p for p in parts if p.strip()])

            uniq_brands = pd.Series(df["brand"].astype(str).str.strip()).dropna().unique()
            # inverse map for fuzzy token match
            inv = {_norm(b): b for b in uniq_brands}

            chosen: List[str] = []

            if explicit_tokens:
                for tok in explicit_tokens:
                    key = _norm(tok)
                    if key in inv and inv[key] not in chosen:
                        chosen.append(inv[key])
            else:
                # fallback: scan all brands inside the question
                for b in uniq_brands:
                    if _norm(b) and _norm(b) in text_norm and b not in chosen:
                        chosen.append(b)

            if chosen:
                filters["brand"] = chosen
                if len(chosen) > 1:
                    brand_group = True

    # --- keep your old splitter for a single brand string like "Alpha, Beta" in filters ---
    bval = filters.get("brand")
    if isinstance(bval, str):
        parts = [p.strip() for p in re.split(r"\s*(?:,|and|&|\+)\s*", bval, flags=re.I) if p.strip()]
        if len(parts) > 1:
            filters["brand"] = parts
            brand_group = True

    # If grouping by brand, drop a single fixed brand (avoid double restriction)
    if brand_group and "brand" in filters:
        is_single = not isinstance(filters["brand"], (list, tuple, set)) or len(filters["brand"]) <= 1
        if is_single:
            filters.pop("brand", None)

    # ---------- choose window for ordinary (single) runs ----------
    if mode == "MAT":
        start, end = compute_mat_window(df)  # unchanged
    elif mode == "YTD":
        system_today  = pd.Timestamp.today()
        prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
        end   = min(prev_full_end, dataset_last_full)
        start = pd.Timestamp(f"{end.year}-01-01")
    elif "start" in time and "end" in time:
        start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
        end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
        end   = min(end, dataset_last_full)
    else:
        start = df["date"].min().to_period("M").to_timestamp(how="start")
        end   = dataset_last_full

    # ---------- base frame ----------
    base = apply_filters(df, filters)

    # ===================== MAT COMPARISON BRANCH (unchanged) =====================
    def _extract_mat_years(text: str) -> List[int]:
        years = []
        for y in re.findall(r"\bmat[\s\-]?((?:20)?\d{2})\b", text):
            y = int(y)
            if y < 100:
                y = 2000 + y
            years.append(y)
        seen, ordered = set(), []
        for y in years:
            if y not in seen:
                ordered.append(y); seen.add(y)
        return ordered

    mat_years = _extract_mat_years(raw_text)
    has_compare_tokens = any(tok in raw_text for tok in ["compare", "vs", "versus", "comparison"])
    is_mat_compare_query = ("mat" in raw_text) and (has_compare_tokens or len(mat_years) >= 2)

    if is_mat_compare_query:
        system_prev_end = (pd.Timestamp.today().to_period("M") - 1).to_timestamp(how="end")
        anchor_month = system_prev_end.month
        if not mat_years:
            mat_years = [system_prev_end.year, system_prev_end.year - 1]
        measures_list = intent.get("measures") or []
        use_unit = "unit_sales" in measures_list or measure == "unit_sales"
        base_measure = "unit_sales" if use_unit else "value_sales"

        dims_for_cmp = [d for d in (dims or []) if d != "date"]
        dims_for_cmp = [d for d in dims_for_cmp if d not in (filters or {}) or (brand_group and d == "brand")]
        if not brand_group:
            dims_for_cmp = [d for d in dims_for_cmp if d != "brand"]

        def _agg(frame, gcols, col):
            if gcols:
                return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
            return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

        frames, labels = [], []
        periods=[]
        overall_start, overall_end = None, None
        for y in mat_years:
            cmp_end = pd.Timestamp(year=y, month=anchor_month, day=1).to_period("M").to_timestamp(how="end")
            cmp_end = min(cmp_end, dataset_last_full)
            cmp_start = (cmp_end.to_period("M") - 11).to_timestamp(how="start")
            overall_start = cmp_start if overall_start is None else min(overall_start, cmp_start)
            overall_end   = cmp_end   if overall_end   is None else max(overall_end,   cmp_end)
            mask = (base["date"] >= cmp_start) & (base["date"] <= cmp_end)
            agg = _agg(base.loc[mask], dims_for_cmp, base_measure)
            label = f"MAT {y}"
            agg.insert(0, "mat_label", label)
            frames.append(agg); labels.append(label)
            periods.append({"mat_label":f"MAT {y}","start":cmp_start.date().strftime("%Y-%m-%d"),"end":cmp_end.date().strftime("%Y-%m-%d")})
            # print(frames)
        # print(periods)

        out = pd.concat(frames, axis=0, ignore_index=True) if frames else pd.DataFrame(columns=(["mat_label"] + dims_for_cmp + [base_measure]))
        if "mat_label" in out.columns and labels:
            out["mat_label"] = pd.Categorical(out["mat_label"], categories=labels, ordered=True)
        

        meta= {
                "mat_compare": {"anchor_month": anchor_month, "years": mat_years, "labels": labels},
                "window": {
                    "start": (overall_start.date().isoformat() if overall_start is not None else None),
                    "end":   (overall_end.date().isoformat()   if overall_end   is not None else None),
                },
                "dims": (["mat_label"] + dims_for_cmp),
                "measure": base_measure,
                "filters": filters,
                "mode": "MAT_COMPARE",
                # "category":filt
                "rowcount": int(out.shape[0]),
                "chart_type": "bar",
            }
        # print(meta)

        out = _safe_numeric_fill(out)
        # print(filters)
        return {
            "data": out,
            "meta": {
                "mat_compare": {"anchor_month": anchor_month, "years": mat_years, "labels": labels},
                "window": {
                    "start": (overall_start.date().isoformat() if overall_start is not None else None),
                    "end":   (overall_end.date().isoformat()   if overall_end   is not None else None),
                },
                "dims": (["mat_label"] + dims_for_cmp),
                "measure": base_measure,
                "filters": filters,
                "mode": "MAT_COMPARE",
                # "category":filt
                "rowcount": int(out.shape[0]),
                "chart_type": "bar",
                "periods":periods

            },
        }
    


    # ===================== YoY BRANCH (unchanged math) =====================
    if asked_yoy:
        use_unit     = "unit_sales" in (intent.get("measures") or [])
        base_measure = "unit_sales" if use_unit else "value_sales"
        curr_col     = f"{base_measure}_curr"
        prev_col     = f"{base_measure}_prev"
        yoy_col      = "unit_yoy" if use_unit else "value_yoy"

        dims_for_yoy = [d for d in (dims or []) if d != "date"]
        dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
        if not brand_group:
            dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

        def _agg(frame, gcols, col):
            if gcols:
                return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
            return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

        cur_mask = (base["date"] >= start) & (base["date"] <= end)
        sliced   = base.loc[cur_mask]
        cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})
        prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
        prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
        prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
                        .rename(columns={base_measure: prev_col})

        out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
               else pd.concat([cur_agg, prev_agg], axis=1))

        prev_vals = out[prev_col]; cur_vals = out[curr_col]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

        if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
            out = out.sort_values(yoy_col, ascending=False, na_position="last")
            if brand_group and "brand" in out.columns:
                out = out.drop_duplicates(subset=["brand"], keep="first")
            out = out.head(top_n)

        out = _safe_numeric_fill(out)
        chart_type = _decide_chart_type(task, dims_for_yoy, asked_yoy=True, brand_group=brand_group)
        mode=mode+"_yoy"
        meta={
            "data": out,
           
                "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
                "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
                "dims": dims_for_yoy,
                "measure": yoy_col,
                "filters": filters,
                "mode": mode or "CUSTOM",
                "rowcount": int(out.shape[0]),
                "chart_type": chart_type,
            }
        # print(meta)
        return {
            "data": out,
            "meta": {
                "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
                "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
                "dims": dims_for_yoy,
                "measure": yoy_col,
                "filters": filters,
                "mode": mode or "CUSTOM",
                "rowcount": int(out.shape[0]),
                "chart_type": chart_type,
            },
        }

        # ===================== MoM BRANCH (SERIES) =====================
    measures_list = intent.get("measures") or []
    need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
    if need_mom:
        # 1) pick measure
        use_unit     = ("unit_sales" in measures_list) or (measure == "unit_sales")
        base_measure = "unit_sales" if use_unit else "value_sales"
        mom_col      = "unit_mom" if use_unit else "value_mom"

        # 2) dims to keep (no 'date' as a dim column; we’ll keep date as the x-axis)
        dims_for_mom = [d for d in (dims or []) if d != "date"]
        dims_for_mom = [d for d in dims_for_mom if d not in (filters or {}) or (brand_group and d == "brand")]
        if not brand_group:
            dims_for_mom = [d for d in dims_for_mom if d != "brand"]

        # 3) restrict to requested window
        work = base.loc[(base["date"] >= start) & (base["date"] <= end)].copy()

        # 4) normalize to monthly grain and aggregate monthly totals
        work["date"] = work["date"].dt.to_period("M").dt.to_timestamp(how="start")
        gcols = (["date"] + dims_for_mom) if dims_for_mom else ["date"]
        monthly = (
            work.groupby(gcols, dropna=False)[base_measure]
                .sum()
                .reset_index()
                .sort_values("date")
        )
        # print(f"monthly:{monthly}")
        # print(work)
        # print(base_measure)
        # print(dims_for_mom)
        # print(mom_col)
        # 5) compute month-over-month % change **within each group**
        if dims_for_mom:
            monthly[mom_col] = (
                monthly
                .groupby(dims_for_mom, dropna=False)[base_measure]
                .pct_change(periods=1)
            )
        else:
            monthly[mom_col] = monthly[base_measure].pct_change(periods=1)
        # print(base_measure)
        df_brand=pd.concat([work,work.groupby(["brand"])[base_measure].pct_change(periods=1)],axis=1,join="inner")
        df_brand=df_brand.fillna(0)
        df_brand.columns.values[-1]=mom_col
        # print(df_brand)
        # print(df_brand)
        
        # df_brand["month_year"]=df_brand["date"].dt.strftime("%b %Y")
        # print(mom_col)
        df_brand=df_brand[["date","brand",base_measure,df_brand.columns.values[-1]]]
        # print(df_brand)
        # print(df_brand)
        # print(base_measure)
        # print(df_brand)
        # 6) pretty month label for charts/tables
        monthly["month_year"] = monthly["date"].dt.strftime("%b %Y")

        # 7) If Top-N was asked, choose top groups by **latest** MoM
        if intent.get("task") == "topn" and dims_for_mom:
            last_m = monthly["date"].max()
            snap = (
                monthly[monthly["date"] == last_m]
                .sort_values(mom_col, ascending=False, na_position="last")
            )
            # keep top groups only
            keys = snap[dims_for_mom].drop_duplicates().head(top_n)
            monthly = monthly.merge(keys, on=dims_for_mom, how="inner")


        # 8) choose a chart hint (line over time)
        chart_type = "line"
        # Ensure brand stays if grouping by brand so the frontend draws one line per brand
        # (we already kept dims_for_mom above)

        # out = monthly.copy()
        out = df_brand.copy()
        # print(out)
        # print(out)
        # print(out)
        out = _safe_numeric_fill(out)
        # print(filters)
        mode="mom"
        dict1={
            "data": out,
            "meta": {
                "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
                "dims": (["date"] + dims_for_mom),  # time dimension is present for a trend
                "measure": mom_col,                 # value_mom or unit_mom
                "base_measure": base_measure,       # optional: helpful for the frontend
                "filters": filters,
                "mode": (mode or "CUSTOM"),
                "rowcount": int(out.shape[0]),
                "chart_type": chart_type,
            },
        }
        # print(dict1)
    
        return {
            "data": out,
            "meta": {
                "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
                "dims": (["date"] + dims_for_mom),  # time dimension is present for a trend
                "measure": mom_col,                 # value_mom or unit_mom
                "base_measure": base_measure,       # optional: helpful for the frontend
                "filters": filters,
                "mode": (mode or "CUSTOM"),
                "rowcount": int(out.shape[0]),
                "chart_type": chart_type,
            },
        }
    # ===================== Non-MoM/YoY =====================
    work = base.loc[(base["date"] >= start) & (base["date"] <= end)]

    if intent.get("task") == "topn":
        preferred_dim = None
        if brand_group and "brand" in df.columns:
            preferred_dim = "brand"
        else:
            candidates = [d for d in (dims or []) if d != "date" and d not in filters]
            preferred_dim = candidates[0] if candidates else None

        if preferred_dim is None:
            out = aggregate(work, dims=[], measure_col=measure)
            for lbl in ("category", "market", "channel", "brand"):
                if lbl in filters:
                    out[lbl] = filters[lbl]
            label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
            out = out[label_cols + [c for c in out.columns if c not in label_cols]]
            out = _safe_numeric_fill(out)
            chart_type = _decide_chart_type("topn", [], asked_yoy=False, brand_group=brand_group)
            return {
                "data": out,
                "meta": {
                    "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
                    "dims": [],
                    "measure": measure,
                    "filters": filters,
                    "mode": mode or None,
                    "rowcount": int(out.shape[0]),
                    "chart_type": chart_type,
                },
            }

        out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
        if preferred_dim == "brand" and "brand" in out.columns:
            out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
        else:
            out = out.head(top_n)
        out = _safe_numeric_fill(out)
        chart_type = _decide_chart_type("topn", [preferred_dim], asked_yoy=False, brand_group=brand_group)
        return {
            "data": out,
            "meta": {
                "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
                "dims": [preferred_dim],
                "measure": measure,
                "filters": filters,
                "mode": mode or None,
                "rowcount": int(out.shape[0]),
                "chart_type": chart_type,
            },
        }

    # ---------- normal aggregate / chart ----------
    # NEW: if it's a time-series chart and multiple brands were requested (or brand_group=True),
    # ensure 'brand' stays in dims so the frontend gets one line per brand.
    
    multi_brand = isinstance(filters.get("brand"), (list, tuple, set)) and len(filters["brand"]) > 1
    if intent.get("task") == "chart" and ("date" in (dims or [])) and (multi_brand or brand_group):
        if "brand" not in dims:
            dims = [*dims, "brand"]

    # your existing pruning rules
    if not ("date" in dims and intent.get("task") == "chart"):
        dims = [d for d in (dims or []) if d != "date"]
    if not brand_group:
        dims = [d for d in dims if d != "brand"]

    out = aggregate(work, dims=dims, measure_col=measure)
    if not dims:
        for lbl in ("category", "market", "channel", "brand"):
            if lbl in filters:
                out[lbl] = filters[lbl]
        label_cols = [c for c in ("category","market","channel","brand") if c in out.columns]
        out = out[label_cols + [c for c in out.columns if c not in label_cols]]
    # print(f"DIMS:{dims}")
    # print(filters["brand"])
    if len(filters.get("brand",[]))==1:
        out["brand"]=filters["brand"][0]
        
    

    out = _safe_numeric_fill(out)
    
    # print(out)
    mode=f"total {measure.replace("_sales","")} sales"
    chart_type = _decide_chart_type(task, dims, asked_yoy=False, brand_group=brand_group)
    return {
        "data": out,
        "meta": {
            "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
            "dims": dims,
            "measure": measure,
            "filters": filters,
            "mode": mode or None,
            "rowcount": int(out.shape[0]),
            "chart_type": chart_type,
        },
    }









