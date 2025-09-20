# backend/nlp/pandas_runner.py
import pandas as pd
from typing import Dict, Any, List, Optional

# ---------- helpers ----------
# --- ADD: helpers (place near other helpers) ---------------------------------
def _prev_year_window(start: pd.Timestamp, end: pd.Timestamp):
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
    """System-time aware anchors (still used for YTD fallback)."""
    now = now or pd.Timestamp.today()
    ytd_start = pd.Timestamp(f"{now.year}-01-01")
    ytd_end = (now.to_period("M") - 1).to_timestamp(how="end")  # end of previous full month
    mat_end = ytd_end
    mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")
    return {"ytd_start": ytd_start, "ytd_end": ytd_end, "mat_start": mat_start, "mat_end": mat_end}

def compute_mat_window(df: pd.DataFrame, system_today: Optional[pd.Timestamp] = None):
    """
    MAT = last 12 complete months ending at the previous full month (by system time),
    clamped to the latest full month that exists in the dataset.
    Returns (start, end) as month-start and month-end timestamps.
    """
    if "date" not in df.columns:
        raise ValueError("Data must have a 'date' column.")
    dates = pd.to_datetime(df["date"])

    # previous full month from system time
    system_today = system_today or pd.Timestamp.today()
    prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")

    # dataset’s last full month
    dataset_last_full = dates.max().to_period("M").to_timestamp(how="end")

    # choose the earlier of the two for the MAT end
    mat_end = min(prev_full_end, dataset_last_full)

    # robust month start: exactly 11 months before mat_end, at month start
    mat_start = (mat_end.to_period("M") - 11).to_timestamp(how="start")

    return mat_start.normalize(), mat_end.normalize()

# ---------- core compute ----------
def apply_filters(df, filters):
    out = df.copy()
    for col, val in (filters or {}).items():
        if col not in out.columns:
            continue
        # case-insensitive, trimmed comparisons
        if isinstance(val, list):
            vals = [str(v).strip().lower() for v in val]
            out = out[out[col].astype(str).str.strip().str.lower().isin(vals)]
        else:
            v = str(val).strip().lower()
            out = out[out[col].astype(str).str.strip().str.lower() == v]
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

# ---------- public API ----------
# def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     intent dict:
#       - task: "topn" | "table" | "chart"
#       - dims: list (e.g., ["brand"])
#       - measures: list or str (default "value_sales")
#       - filters: dict (e.g., {"category":"Biscuits","market":"India"})
#       - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
#       - top_n: int
#     """
#     # normalize
#     measure = (intent.get("measures") or ["value_sales"])
#     measure = measure[0] if isinstance(measure, list) else measure
#     dims = intent.get("dims") or []
#     filters = intent.get("filters") or {}
#     top_n = intent.get("top_n") or 5
#     time = intent.get("time_range") or {}
#     mode = (time.get("mode") or "").upper()

#     # date column
#     df = df.copy()
#     if "date" not in df.columns:
#         raise ValueError("Data must have a 'date' column.")
#     df["date"] = pd.to_datetime(df["date"])

#     # dataset last full month
#     dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

#     # ---- choose window (and clamp to dataset) ----
#     if mode == "MAT":
#         start, end = compute_mat_window(df)  # ✅ same MAT window for all measures
#     elif mode == "YTD":
#         # previous full month by system time, clamped to dataset
#         system_today = pd.Timestamp.today()
#         prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
#         end = min(prev_full_end, dataset_last_full)
#         start = pd.Timestamp(f"{end.year}-01-01")
#     elif "start" in time and "end" in time:
#         # explicit yyyy-mm (or yyyy-mm-dd)
#         start = (
#             pd.to_datetime(str(time["start"]) + "-01")
#             if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
#         )
#         end = (
#             pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end")
#             if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
#         )
#         end = min(end, dataset_last_full)  # defensive clamp
#     else:
#         # all-time within dataset up to last full month
#         start, end = df["date"].min().to_period("M").to_timestamp(how="start"), dataset_last_full

#     # slice by date
#     mask = (df["date"] >= start) & (df["date"] <= end)
#     sliced = df.loc[mask]

#     # fallback: if empty for YTD/MAT (asking ahead of data), re-anchor to dataset
#     if sliced.empty and mode in {"YTD", "MAT"}:
#         end = dataset_last_full
#         if mode == "YTD":
#             start = pd.Timestamp(f"{end.year}-01-01")
#         else:  # MAT
#             start = (end.to_period("M") - 11).to_timestamp(how="start")
#         mask = (df["date"] >= start) & (df["date"] <= end)
#         sliced = df.loc[mask]

#     # apply filters
#     df = apply_filters(sliced, filters)

#     # compute
#     if intent.get("task") == "topn":
#         dim = next((d for d in (dims or []) if d != "date"), "brand")
#         out = compute_topN(df, dim=dim, measure_col=measure, n=top_n)
#     else:
#         if not ("date" in dims and intent.get("task") == "chart"):
#             dims = [d for d in dims if d != "date"]
#         out = aggregate(df, dims=dims, measure_col=measure)

#     # metadata + debug
#     meta = {
#         "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
#         "dims": dims,
#         "measure": measure,
#         "filters": filters,
#         "mode": mode or None,
#         "rowcount": int(out.shape[0]),
#         "debug": {
#             "dataset_last_full": dataset_last_full.date().isoformat(),
#             "slice_min_date": df["date"].min().date().isoformat() if not df.empty else None,
#             "slice_max_date": df["date"].max().date().isoformat() if not df.empty else None,
#         }
#     }
#     return {"data": out, "meta": meta}


def run_pandas_intent(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    intent dict:
      - task: "topn" | "table" | "chart"
      - dims: list (e.g., ["brand"])
      - measures: list or str (default "value_sales")
      - filters: dict (e.g., {"category":"Biscuits","market":"India"})
      - time_range: {"mode":"YTD"|"MAT"} or {"start":"YYYY-MM","end":"YYYY-MM"}
      - top_n: int
    """
    # normalize
    measure = (intent.get("measures") or ["value_sales"])
    measure = measure[0] if isinstance(measure, list) else measure
    dims = intent.get("dims") or []
    filters = intent.get("filters") or {}
    top_n = intent.get("top_n") or 5
    time = intent.get("time_range") or {}
    mode = (time.get("mode") or "").upper()

    # date column
    df = df.copy()
    if "date" not in df.columns:
        raise ValueError("Data must have a 'date' column.")
    df["date"] = pd.to_datetime(df["date"])

    # dataset last full month
    dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

    # ---- choose window (and clamp to dataset) ----
    if mode == "MAT":
        start, end = compute_mat_window(df)  # ✅ same MAT window for all measures
    elif mode == "YTD":
        # previous full month by system time, clamped to dataset
        system_today = pd.Timestamp.today()
        prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
        end = min(prev_full_end, dataset_last_full)
        start = pd.Timestamp(f"{end.year}-01-01")
    elif "start" in time and "end" in time:
        # explicit yyyy-mm (or yyyy-mm-dd)
        start = (
            pd.to_datetime(str(time["start"]) + "-01")
            if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
        )
        end = (
            pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end")
            if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
        )
        end = min(end, dataset_last_full)  # defensive clamp
    else:
        # all-time within dataset up to last full month
        start, end = df["date"].min().to_period("M").to_timestamp(how="start"), dataset_last_full
        # ----- slice current window -----
        # ----- build a base frame filtered by dims (NO time slicing yet) -----
    base = apply_filters(df, filters)  # only categorical filters applied

    # ----- slice current window from base -----
    mask = (base["date"] >= start) & (base["date"] <= end)
    sliced = base.loc[mask]

    # ----- fallback: if empty for YTD/MAT (asking ahead of data), re-anchor to dataset -----
    if sliced.empty and mode in {"YTD", "MAT"}:
        end = dataset_last_full
        if mode == "YTD":
            start = pd.Timestamp(f"{end.year}-01-01")
        else:  # MAT
            start = (end.to_period("M") - 11).to_timestamp(how="start")
        mask = (base["date"] >= start) & (base["date"] <= end)
        sliced = base.loc[mask]
    # ===================== YoY BRANCH (value OR unit) =====================
# Trigger YoY if measure requested or sorting by YoY
    need_yoy = (
        measure == "value_yoy"
        or "value_yoy" in (intent.get("measures") or [])
        or (intent.get("sort_by") == "value_yoy")
    )

    if need_yoy:
        import numpy as np

        measures_list = intent.get("measures") or []

        # If user mentioned unit sales, compute YoY on unit_sales; else value_sales
        use_unit = "unit_sales" in measures_list
        base_measure = "unit_sales" if use_unit else "value_sales"
        curr_col = f"{base_measure}_curr"
        prev_col = f"{base_measure}_prev"
        yoy_col  = "unit_yoy" if use_unit else "value_yoy"

        # YoY dims: drop 'date' unless it's an explicit chart
        dims_for_yoy = [d for d in (dims or []) if d != "date"]

        def _agg(frame, gcols, col):
            if gcols:
                return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
            # whole slice (no dims)
            return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

        # ---- Build a base frame filtered by category/market/etc. (NO time yet)

            # ---------- build a base frame filtered by dims (NO time slicing yet) ----------
    base = apply_filters(df, filters)  # categorical filters only

    # ---------- slice current window from base ----------
    cur_mask = (base["date"] >= start) & (base["date"] <= end)
    sliced = base.loc[cur_mask]

    # fallback: if empty for YTD/MAT (asking ahead of data), re-anchor to dataset
    if sliced.empty and mode in {"YTD", "MAT"}:
        end = dataset_last_full
        if mode == "YTD":
            start = pd.Timestamp(f"{end.year}-01-01")
        else:  # MAT
            start = (end.to_period("M") - 11).to_timestamp(how="start")
        cur_mask = (base["date"] >= start) & (base["date"] <= end)
        sliced = base.loc[cur_mask]

    # ===================== YoY BRANCH (value OR unit) =====================
    need_yoy = (
        measure == "value_yoy"
        or "value_yoy" in (intent.get("measures") or [])
        or (intent.get("sort_by") == "value_yoy")
    )
    if need_yoy:
        import numpy as np

        measures_list = intent.get("measures") or []
        use_unit = "unit_sales" in measures_list  # if user mentioned units, compute unit YoY
        base_measure = "unit_sales" if use_unit else "value_sales"
        curr_col = f"{base_measure}_curr"
        prev_col = f"{base_measure}_prev"
        yoy_col  = "unit_yoy" if use_unit else "value_yoy"

        dims_for_yoy = [d for d in (dims or []) if d != "date"]

        def _agg(frame, gcols, col):
            if gcols:
                return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
            return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

        # current window aggregate (slice from base)
        cur_agg = _agg(base[(base["date"] >= start) & (base["date"] <= end)], dims_for_yoy, base_measure)
        cur_agg = cur_agg.rename(columns={base_measure: curr_col})

        # previous aligned window (slice from the same base)
        prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
        prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
        prev_agg = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)
        prev_agg = prev_agg.rename(columns={base_measure: prev_col})

        # join & compute YoY
        out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
               else pd.concat([cur_agg, prev_agg], axis=1))

        prev = out[prev_col]
        curv = out[curr_col]
        with np.errstate(divide="ignore", invalid="ignore"):
            yoy_vals = np.where((prev.isna()) | (prev == 0), np.nan, (curv / prev) - 1)
        out[yoy_col] = yoy_vals

        # sort/limit if requested
        if intent.get("task") == "topn" or intent.get("sort_by") == "value_yoy":
            out = out.sort_values(yoy_col, ascending=False, na_position="last")
            n = intent.get("top_n") or 5
            out = out.head(n)

        # JSON-safe numbers: keep YoY as null when undefined; totals as 0
        out = out.replace([np.inf, -np.inf], np.nan)
        out[curr_col] = out[curr_col].fillna(0)
        out[prev_col] = out[prev_col].fillna(0)

        meta = {
            "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
            "dims": dims_for_yoy,
            "measure": yoy_col,  # "value_yoy" or "unit_yoy"
            "filters": filters,
            "mode": mode or None,
            "rowcount": int(out.shape[0]),
            "debug": {"prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()}},
        }
        return {"data": out, "meta": meta}
    # =================== END YOY BRANCH ===================

    # ---------------------- NON-YoY PATHS (ALWAYS RETURN) ----------------------
    # Use 'sliced' (current-window rows from base) for normal compute
    work = sliced

    if intent.get("task") == "topn":
        # pick the best non-date dimension; fallback to brand
        dim = next((d for d in (dims or []) if d != "date"), "brand")
        out = compute_topN(work, dim=dim, measure_col=measure, n=top_n)
    else:
        # drop date unless explicitly asked for chart
        if not ("date" in dims and intent.get("task") == "chart"):
            dims = [d for d in (dims or []) if d != "date"]
        out = aggregate(work, dims=dims, measure_col=measure)

    # JSON-safe sanitize
    import numpy as np
    out = out.replace([np.inf, -np.inf], np.nan).fillna(0)

    meta = {
        "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        "dims": dims,
        "measure": measure,
        "filters": filters,
        "mode": mode or None,
        "rowcount": int(out.shape[0]),
    }
    return {"data": out, "meta": meta}

        # base = apply_filters(df, filters)

        # # Current window aggregate
        # cur_agg = _agg(base[(base["date"] >= start) & (base["date"] <= end)], dims_for_yoy, base_measure)
        # cur_agg = cur_agg.rename(columns={base_measure: curr_col})

        # # Previous aligned window (shift both boundaries by 12 months)
        # prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
        # prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
        # prev_agg = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)
        # prev_agg = prev_agg.rename(columns={base_measure: prev_col})

        # # Join & compute YoY
        # out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
        #     else pd.concat([cur_agg, prev_agg], axis=1))

        # prev = out[prev_col]
        # cur = out[curr_col]
        # with np.errstate(divide="ignore", invalid="ignore"):
        #     yoy_vals = np.where((prev.isna()) | (prev == 0), np.nan, (cur / prev) - 1)
        # out[yoy_col] = yoy_vals

        # # Sort/limit if Top-N or sort by YoY was requested
        # if intent.get("task") == "topn" or intent.get("sort_by") == "value_yoy":
        #     out = out.sort_values(yoy_col, ascending=False, na_position="last")
        #     n = intent.get("top_n") or 5
        #     out = out.head(n)

        # # JSON-safe: keep YoY as null when undefined; numeric totals as 0 when missing
        # out = out.replace([np.inf, -np.inf], np.nan)
        # out[curr_col] = out[curr_col].fillna(0)
        # out[prev_col] = out[prev_col].fillna(0)

        # meta = {
        #     "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        #     "dims": dims_for_yoy,
        #     "measure": yoy_col,  # "value_yoy" or "unit_yoy"
        #     "filters": filters,
        #     "mode": mode or None,
        #     "rowcount": int(out.shape[0]),
        #     "debug": {
        #         "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
        #     },
        # }
        # return {"data": out, "meta": meta}
# =================== END YOY BRANCH ===================


    # ===================== YoY BRANCH =====================
    # need_yoy = (
    #     measure == "value_yoy"
    #     or "value_yoy" in (intent.get("measures") or [])
    #     or (intent.get("sort_by") == "value_yoy")
    # )
    # if need_yoy:
    #     import numpy as np

    #     base_measure = "value_sales"  # YoY defined on value_sales
    #     dims_for_yoy = [d for d in (dims or []) if d != "date"]

    #     def _agg(frame, gcols, col):
    #         if gcols:
    #             return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
    #         # whole slice (no dims)
    #         return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

    #     # current window aggregate (slice from base)
    #     cur_agg = _agg(base[(base["date"] >= start) & (base["date"] <= end)], dims_for_yoy, base_measure)
    #     cur_agg = cur_agg.rename(columns={base_measure: "value_sales_curr"})

    #     # previous aligned window (slice from the same base)
    #     prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
    #     prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
    #     prev_agg = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)
    #     prev_agg = prev_agg.rename(columns={base_measure: "value_sales_prev"})

    #     # join and compute YoY
    #     out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
    #            else pd.concat([cur_agg, prev_agg], axis=1))

    #     # YoY: if prev is 0/NaN -> None (not 0) to avoid misleading zeros
    #     prev = out["value_sales_prev"]
    #     cur = out["value_sales_curr"]
    #     with np.errstate(divide="ignore", invalid="ignore"):
    #         yoy = np.where((prev.isna()) | (prev == 0), np.nan, (cur / prev) - 1)
    #     out["value_yoy"] = yoy

    #     # sort/limit if requested
    #     if intent.get("task") == "topn" or intent.get("sort_by") == "value_yoy":
    #         out = out.sort_values("value_yoy", ascending=False, na_position="last")
    #         n = intent.get("top_n") or 5
    #         out = out.head(n)

    #     # JSON-safe numbers: keep YoY as null when undefined, but 0 for numeric totals
    #     out = out.replace([np.inf, -np.inf], np.nan)
    #     for col in ["value_sales_curr", "value_sales_prev"]:
    #         out[col] = out[col].fillna(0)

    #     meta = {
    #         "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
    #         "dims": dims_for_yoy,
    #         "measure": "value_yoy",
    #         "filters": filters,
    #         "mode": mode or None,
    #         "rowcount": int(out.shape[0]),
    #         "debug": {
    #             "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
    #         },
    #     }
    #     return {"data": out, "meta": meta}
    # =================== END YOY BRANCH ===================

    # ----- continue with regular compute paths below this point -----
    # use 'sliced' (current-window rows from base) for non-YoY paths
    df = sliced
