import pandas as pd
from typing import Dict, Any, List

def build_insights_payload(df: pd.DataFrame, meta: Dict[str, Any], max_points: int = 200) -> Dict[str, Any]:
    """
    Normalize the result DataFrame + meta into a compact, LLM-friendly payload.
    Works for charts (line/bar), tables, and top-N.

    Returns a dict you can JSON-serialize and send to the LLM (or to the UI).
    """
    meta = meta or {}
    payload: Dict[str, Any] = {
        "measure": meta.get("measure"),
        "dims": meta.get("dims") or [],
        "filters": meta.get("filters") or {},
        "window": meta.get("window") or {},
        "mode": meta.get("mode"),
        "chart_type": meta.get("chart_type"),
        "rowcount": int(meta.get("rowcount") or len(df)),
    }

    # Make a copy to format dates/labels without breaking upstream
    d = df.copy()

    # Time/label normalization for series
    time_cols = [c for c in ["month_year", "month", "date"] if c in d.columns]
    time_col = time_cols[0] if time_cols else None
    if time_col == "date":
        try:
            d["__label"] = pd.to_datetime(d["date"]).dt.strftime("%b %Y")
        except Exception:
            d["__label"] = d["date"].astype(str)
    elif time_col:
        d["__label"] = d[time_col].astype(str)

    # Identify a primary category (to split lines/bars)
    cat_cols = [c for c in ["brand", "category", "market", "channel", "segment", "manufacturer"] if c in d.columns]
    cat_col = cat_cols[0] if cat_cols else None

    # Find a y/metric column
    pref = ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]
    num_cols = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
    y_col = next((c for c in pref if c in d.columns), (num_cols[0] if num_cols else None))
    payload["y_col"] = y_col
    payload["cat_col"] = cat_col
    payload["time_col"] = time_col

    # Reduce size: sort by time if we have it, then cap rows
    if "__label" in d.columns:
        # try a stable chronological sort
        if time_col == "date":
            try:
                d = d.sort_values("date")
            except Exception:
                pass
        d = d.tail(max_points)

    # Build series data (for line/bar with a category) or a flat table
    if y_col:
        # Round numeric output for readability
        def _round(x):
            try:
                return round(float(x), 4)
            except Exception:
                return x

        if "__label" in d.columns:  # time series or time-indexed bars
            if cat_col and cat_col in d.columns:
                series: List[Dict[str, Any]] = []
                for k, g in d.groupby(cat_col, dropna=False):
                    rows = [{"x": r["__label"], "y": _round(r[y_col])} for _, r in g.iterrows()]
                    series.append({"name": str(k), "points": rows})
                payload["series"] = series
            else:
                rows = [{"x": r["__label"], "y": _round(r[y_col])} for _, r in d.iterrows()]
                payload["series"] = [{"name": "Overall", "points": rows}]
        else:
            # no time axis; send category/value pairs or plain rows
            if cat_col and cat_col in d.columns:
                grp = d.groupby(cat_col, dropna=False)[y_col].sum().reset_index()
                grp[y_col] = grp[y_col].map(_round)
                payload["categories"] = [
                    {"name": str(r[cat_col]), "value": r[y_col]} for _, r in grp.iterrows()
                ][:max_points]
            else:
                # fallback: first 50 rows as key/value records
                payload["rows"] = d.head(50).to_dict(orient="records")
    else:
        payload["rows"] = d.head(50).to_dict(orient="records")

    # lightweight totals/topN hints
    if y_col:
        try:
            payload["total"] = float(d[y_col].sum())
        except Exception:
            pass
        if cat_col and y_col in d.columns:
            top = (
                d.groupby(cat_col, dropna=False)[y_col]
                  .sum()
                  .reset_index()
                  .sort_values(y_col, ascending=False)
                  .head(5)
            )
            payload["topN"] = top.to_dict(orient="records")

    return payload


# Optional: simple fallback insights if LLM is unavailable
def generate_fallback_insights(payload: Dict[str, Any]) -> List[str]:
    tips: List[str] = []
    y = payload.get("y_col")
    if not y:
        return tips

    # If we have series, comment on last change and leader
    series = payload.get("series") or []
    if series:
        # Merge all series' last points to compare leaders
        last_points = []
        for s in series:
            if s.get("points"):
                last_points.append((s["name"], s["points"][-1]["y"]))
        if last_points:
            leader = max(last_points, key=lambda t: (t[1] if t[1] is not None else float("-inf")))
            tips.append(f"Latest leader by {y}: {leader[0]} ({leader[1]}).")

        # If any series has 2+ points, describe trend
        for s in series:
            pts = s.get("points") or []
            if len(pts) >= 2 and isinstance(pts[-1]["y"], (int, float)) and isinstance(pts[-2]["y"], (int, float)):
                delta = pts[-1]["y"] - pts[-2]["y"]
                dir_ = "up" if delta > 0 else "down" if delta < 0 else "flat"
                tips.append(f"{s['name']} moved {dir_} last period ({delta:+}).")
                break
        return tips

    # If we have categories (no time)
    cats = payload.get("categories") or []
    if cats:
        leader = max(cats, key=lambda r: (r["value"] if r["value"] is not None else float("-inf")))
        tips.append(f"Top {payload.get('cat_col')} by {y}: {leader['name']} ({leader['value']}).")
    return tips