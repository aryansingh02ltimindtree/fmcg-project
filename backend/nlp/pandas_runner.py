# Working code MAT YoY,YTD, TopN, Brand Grouping
# backend/nlp/pandas_runner.py
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

# ---------- helpers ----------

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
      - is_yoy: bool (explicit YoY request)
      - brand_group: bool (explicit "by brand" request)
      - has_brand_filter: bool (explicit brand fixed by filter)
    """
    import numpy as np

    # ---------- normalize ----------
    measure = (intent.get("measures") or ["value_sales"])
    measure = measure[0] if isinstance(measure, list) else measure
    dims             = intent.get("dims") or []
    filters          = dict(intent.get("filters") or {})
    # normalize top_n robustly
    _topn_raw = intent.get("top_n")
    top_n = int(_topn_raw) if _topn_raw is not None else 5

    time            = intent.get("time_range") or {}
    mode            = (time.get("mode") or "").upper()
    brand_group     = bool(intent.get("brand_group"))
    has_brand_filter= bool(intent.get("has_brand_filter"))
    asked_yoy       = bool(intent.get("is_yoy"))

    # If grouping by brand, drop any brand filter (avoid double restriction)
    if brand_group and "brand" in filters:
        filters.pop("brand", None)

    # ---------- date column ----------
    df = df.copy()
    if "date" not in df.columns:
        raise ValueError("Data must have a 'date' column.")
    df["date"] = pd.to_datetime(df["date"])
    dataset_last_full = df["date"].max().to_period("M").to_timestamp(how="end")

    # ---------- choose window ----------
    if mode == "MAT":
        start, end = compute_mat_window(df)
    elif mode == "YTD":
        system_today  = pd.Timestamp.today()
        prev_full_end = (system_today.to_period("M") - 1).to_timestamp(how="end")
        end   = min(prev_full_end, dataset_last_full)
        start = pd.Timestamp(f"{end.year}-01-01")
    elif "start" in time and "end" in time:
        # custom period support
        start = pd.to_datetime(str(time["start"]) + "-01") if len(str(time["start"])) == 7 else pd.to_datetime(time["start"])
        end   = pd.to_datetime(str(time["end"]) + "-01").to_period("M").to_timestamp(how="end") if len(str(time["end"])) == 7 else pd.to_datetime(time["end"])
        end   = min(end, dataset_last_full)
    else:
        start = df["date"].min().to_period("M").to_timestamp(how="start")
        end   = dataset_last_full

    # ---------- base frame ----------
    base = apply_filters(df, filters)

    # ===================== MoM BRANCH =====================
    measures_list = intent.get("measures") or []
    need_mom = bool(intent.get("mom")) or ("value_mom" in measures_list) or (intent.get("sort_by") == "value_mom")
    if need_mom:
        # (left intentionally unchanged per your request)
        pass

    # ===================== YoY BRANCH (MAT / YTD / CUSTOM supported) =====================
    if asked_yoy:
        use_unit     = "unit_sales" in (intent.get("measures") or [])
        base_measure = "unit_sales" if use_unit else "value_sales"
        curr_col     = f"{base_measure}_curr"
        prev_col     = f"{base_measure}_prev"
        yoy_col      = "unit_yoy" if use_unit else "value_yoy"

        # dims for YoY (drop date; keep brand only if brand_group=True)
        dims_for_yoy = [d for d in (dims or []) if d != "date"]
        dims_for_yoy = [d for d in dims_for_yoy if d not in (filters or {}) or (brand_group and d == "brand")]
        if not brand_group:
            dims_for_yoy = [d for d in dims_for_yoy if d != "brand"]

        def _agg(frame, gcols, col):
            if gcols:
                return frame.groupby(gcols, dropna=False)[col].sum().reset_index()
            return frame.groupby(lambda _: True, dropna=False)[col].sum().reset_index(drop=True).to_frame(col)

        # current period
        cur_mask = (base["date"] >= start) & (base["date"] <= end)
        sliced   = base.loc[cur_mask]
        cur_agg  = _agg(sliced, dims_for_yoy, base_measure).rename(columns={base_measure: curr_col})

        # aligned previous period (shift -12 months)
        prev_start = (start.to_period("M") - 12).to_timestamp(how="start")
        prev_end   = (end.to_period("M")   - 12).to_timestamp(how="end")
        prev_agg   = _agg(base[(base["date"] >= prev_start) & (base["date"] <= prev_end)], dims_for_yoy, base_measure)\
                        .rename(columns={base_measure: prev_col})

        out = (cur_agg.merge(prev_agg, on=dims_for_yoy, how="left") if dims_for_yoy
               else pd.concat([cur_agg, prev_agg], axis=1))

        prev_vals = out[prev_col]
        cur_vals  = out[curr_col]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[yoy_col] = np.where((prev_vals.isna()) | (prev_vals == 0), np.nan, (cur_vals / prev_vals) - 1)

        # --- Top-N cut for YoY (no logic change; only post-process sorting & truncation) ---
        if intent.get("task") == "topn" or intent.get("sort_by") in (yoy_col, "value_yoy", "unit_yoy"):
            out = out.sort_values(yoy_col, ascending=False, na_position="last")
            # If grouping by brand, ensure distinct brands before cutting
            if brand_group and "brand" in out.columns:
                out = out.drop_duplicates(subset=["brand"], keep="first")
            out = out.head(top_n)

        out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
        return {"data": out, "meta": {
            "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
            "prev_window": {"start": prev_start.date().isoformat(), "end": prev_end.date().isoformat()},
            "dims": dims_for_yoy,
            "measure": yoy_col,
            "filters": filters,
            "mode": mode or "CUSTOM",
            "rowcount": int(out.shape[0]),
        }}

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
            out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
            return {"data": out, "meta": {
                "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
                "dims": [],
                "measure": measure,
                "filters": filters,
                "mode": mode or None,
                "rowcount": int(out.shape[0]),
            }}

        out = compute_topN(work, dim=preferred_dim, measure_col=measure, n=top_n)
        # Defensive: ensure unique brand rows if ranking by brand
        if preferred_dim == "brand" and "brand" in out.columns:
            out = out.drop_duplicates(subset=["brand"], keep="first").head(top_n)
        else:
            out = out.head(top_n)

        out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
        return {"data": out, "meta": {
            "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
            "dims": [preferred_dim],
            "measure": measure,
            "filters": filters,
            "mode": mode or None,
            "rowcount": int(out.shape[0]),
        }}

    # normal aggregate / chart
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

    out = out.replace([np.inf, -np.inf], np.nan).fillna(0)
    return {"data": out, "meta": {
        "window": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        "dims": dims,
        "measure": measure,
        "filters": filters,
        "mode": mode or None,
        "rowcount": int(out.shape[0]),
    }}


