#Original code working
# # backend/insights.py

# from __future__ import annotations

# import numpy as np

# import pandas as pd

# CAT_CANDS = ["brand", "category", "market", "channel", "segment", "manufacturer"]

# def _first_numeric(df: pd.DataFrame) -> str | None:

#     for c in df.columns:

#         if pd.api.types.is_numeric_dtype(df[c]):

#             return c

#     return None

# def _pick_measure_col(df: pd.DataFrame, meta: dict) -> str | None:

#     # Prefer meta.measure if it exists and is numeric

#     m = (meta or {}).get("measure")

#     if isinstance(m, str) and m in df.columns and pd.api.types.is_numeric_dtype(df[m]):

#         return m

#     # Else try common names

#     for cand in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:

#         if cand in df.columns and pd.api.types.is_numeric_dtype(df[cand]):

#             return cand

#     # Else first numeric

#     return _first_numeric(df)

# def _pick_cat_dim(df: pd.DataFrame) -> str | None:

#     for c in CAT_CANDS:

#         if c in df.columns:

#             return c

#     return None

# def _format_num(x: float) -> str:

#     try:

#         if abs(x) >= 1_000_000:

#             return f"{x/1_000_000:.1f}M"

#         if abs(x) >= 1_000:

#             return f"{x/1_000:.1f}K"

#         return f"{x:.0f}"

#     except Exception:

#         return str(x)

# def _format_pct(x: float) -> str:

#     return f"{x*100:.1f}%"

# def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:

#     """

#     Heuristic, lightweight insights that never fail silently.

#     Works for table/bar/line; time or no time; any dim.

#     """

#     insights: list[str] = []

#     # --- guardrails ---

#     if df is None or not isinstance(df, pd.DataFrame) or df.empty:

#         return ["No data to analyze."]

#     # DEBUG (keep if helpful)

#     # print("DEBUG INSIGHTS >>> cols:", df.columns.tolist())

#     # print("DEBUG INSIGHTS >>> meta:", meta)
    

#     # Choose measure (y)s

#     y = _pick_measure_col(df, meta)

#     if y is None:

#         # No numeric measure → at least say something

#         insights.append("No numeric measure returned, so only structural results are shown.")

#         return insights

#     # Pick a categorical dim if present

#     cat = _pick_cat_dim(df)

#     # Detect time

#     has_date = "date" in df.columns

#     has_month = "month_year" in df.columns

#     # Normalize copy for safe ops

#     d = df.copy()

#     # ---------------- TIME-SERIES INSIGHTS ----------------

#     if has_month or has_date:

#         # prefer month_year string for readability

#         if has_date:

#             try:

#                 d["__dt"] = pd.to_datetime(d["date"])

#             except Exception:

#                 d["__dt"] = pd.to_datetime(d["date"], errors="coerce")

#         else:

#             # build a sortable month from month_year

#             parsed = pd.to_datetime(d["month_year"], errors="coerce")

#             d["__dt"] = parsed.dt.to_period("M").dt.to_timestamp()

#         # If categorical exists (e.g., brand lines), focus on top line at the end

#         if cat and cat in d.columns:

#             # last month in the result

#             last_t = d["__dt"].max()

#             cur = d[d["__dt"] == last_t]

#             # If multiple brands, find top latest and compare to previous point

#             grp = cur.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)

#             if not grp.empty:

#                 top_brand = grp.index[0]

#                 top_val = grp.iloc[0]

#                 # Compute previous value for that brand (prev timestamp)

#                 prev_t = d["__dt"].sort_values().unique()

#                 prev_t = prev_t[-2] if len(prev_t) >= 2 else None

#                 if prev_t is not None:

#                     prev_val = d[(d[cat] == top_brand) & (d["__dt"] == prev_t)][y].sum()

#                     if pd.notna(prev_val) and prev_val != 0:

#                         chg = (top_val - prev_val) / prev_val

#                         dir_word = "up" if chg >= 0 else "down"

#                         insights.append(

#                             f"{top_brand} leads most recently with {_format_num(top_val)} {y.replace('_',' ')} "

#                             f"({dir_word} {_format_pct(abs(chg))} vs previous point)."

#                         )

#                 # Gap to #2 at the last point

#                 if len(grp) >= 2:

#                     gap = grp.iloc[0] - grp.iloc[1]

#                     insights.append(

#                         f"Gap between {grp.index[0]} and {grp.index[1]} is {_format_num(gap)} on the latest point."

#                     )

#         else:

#             # No categorical: describe overall trend last vs prev

#             last_t = d["__dt"].max()

#             prev_times = d["__dt"].sort_values().unique()

#             prev_t = prev_times[-2] if len(prev_times) >= 2 else None

#             last_val = d.loc[d["__dt"] == last_t, y].sum()

#             if prev_t is not None:

#                 prev_val = d.loc[d["__dt"] == prev_t, y].sum()

#                 if pd.notna(prev_val) and prev_val != 0:

#                     chg = (last_val - prev_val) / prev_val

#                     dir_word = "up" if chg >= 0 else "down"

#                     insights.append(

#                         f"Latest {_format_num(last_val)} {y.replace('_',' ')}; {dir_word} {_format_pct(abs(chg))} vs previous point."

#                     )

#     # ---------------- CATEGORICAL INSIGHTS ----------------

#     if cat and cat in d.columns:

#         grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)

#         if not grp.empty:

#             top_k = grp.head(3)

#             names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())

#             insights.append(f"Top {cat}s by {y.replace('_',' ')}: {names}.")

#             if grp.sum() > 0:

#                 shares = (grp / grp.sum()).head(3)

#                 share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())

#                 insights.append(f"Share of total {y.replace('_',' ')}: {share_txt}.")

#     # ---------------- FALLBACK / TOTAL ----------------

#     if not insights:

#         total = pd.to_numeric(d[y], errors="coerce").sum()

#         insights.append(f"Total {y.replace('_',' ')} in the shown result: {_format_num(total)}.")
#     # print(insights)

#     # Cap to 3 neat bullets

#     return insights[:3]









#Working insights code backend- frontend




# # backend/insights.py

# from __future__ import annotations

# import math
# from datetime import datetime
# from typing import Dict, Any, List, Optional, Tuple

# import numpy as np
# import pandas as pd

# CAT_CANDS = ["brand", "category", "market", "channel", "segment", "manufacturer"]

# # =============================================================================
# # EXISTING HELPERS (kept as-is)
# # =============================================================================

# def _first_numeric(df: pd.DataFrame) -> str | None:
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     return None

# def _pick_measure_col(df: pd.DataFrame, meta: dict) -> str | None:
#     # Prefer meta.measure if it exists and is numeric
#     m = (meta or {}).get("measure")
#     if isinstance(m, str) and m in df.columns and pd.api.types.is_numeric_dtype(df[m]):
#         return m
#     # Else try common names
#     for cand in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if cand in df.columns and pd.api.types.is_numeric_dtype(df[cand]):
#             return cand
#     # Else first numeric
#     return _first_numeric(df)

# def _pick_cat_dim(df: pd.DataFrame) -> str | None:
#     for c in CAT_CANDS:
#         if c in df.columns:
#             return c
#     return None

# def _format_num(x: float) -> str:
#     try:
#         if abs(x) >= 1_000_000:
#             return f"{x/1_000_000:.1f}M"
#         if abs(x) >= 1_000:
#             return f"{x/1_000:.1f}K"
#         return f"{x:.0f}"
#     except Exception:
#         return str(x)

# def _format_pct(x: float) -> str:
#     try:
#         return f"{x*100:.1f}%"
#     except Exception:
#         return "NA"

# def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Heuristic, lightweight insights that never fail silently.
#     Works for table/bar/line; time or no time; any dim.
#     """
#     insights: list[str] = []

#     # --- guardrails ---
#     if df is None or not isinstance(df, pd.DataFrame) or df.empty:
#         return ["No data to analyze."]

#     # Choose measure (y)s
#     y = _pick_measure_col(df, meta)
#     if y is None:
#         insights.append("No numeric measure returned, so only structural results are shown.")
#         return insights

#     # Pick a categorical dim if present
#     cat = _pick_cat_dim(df)

#     # Detect time
#     has_date = "date" in df.columns
#     has_month = "month_year" in df.columns

#     # Normalize copy for safe ops
#     d = df.copy()

#     # ---------------- TIME-SERIES INSIGHTS ----------------
#     if has_month or has_date:
#         # prefer month_year string for readability
#         if has_date:
#             try:
#                 d["__dt"] = pd.to_datetime(d["date"])
#             except Exception:
#                 d["__dt"] = pd.to_datetime(d["date"], errors="coerce")
#         else:
#             # build a sortable month from month_year
#             parsed = pd.to_datetime(d["month_year"], errors="coerce")
#             d["__dt"] = parsed.dt.to_period("M").dt.to_timestamp()

#         # If categorical exists (e.g., brand lines), focus on top line at the end
#         if cat and cat in d.columns:
#             # last month in the result
#             last_t = d["__dt"].max()
#             cur = d[d["__dt"] == last_t]

#             # If multiple brands, find top latest and compare to previous point
#             grp = cur.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#             if not grp.empty:
#                 top_brand = grp.index[0]
#                 top_val = grp.iloc[0]

#                 # Compute previous value for that brand (prev timestamp)
#                 prev_t = d["__dt"].sort_values().unique()
#                 prev_t = prev_t[-2] if len(prev_t) >= 2 else None

#                 if prev_t is not None:
#                     prev_val = d[(d[cat] == top_brand) & (d["__dt"] == prev_t)][y].sum()
#                     if pd.notna(prev_val) and prev_val != 0:
#                         chg = (top_val - prev_val) / prev_val
#                         dir_word = "up" if chg >= 0 else "down"
#                         insights.append(
#                             f"{top_brand} leads most recently with {_format_num(top_val)} {y.replace('_',' ')} "
#                             f"({dir_word} {_format_pct(abs(chg))} vs previous point)."
#                         )

#                 # Gap to #2 at the last point
#                 if len(grp) >= 2:
#                     gap = grp.iloc[0] - grp.iloc[1]
#                     insights.append(
#                         f"Gap between {grp.index[0]} and {grp.index[1]} is {_format_num(gap)} on the latest point."
#                     )
#         else:
#             # No categorical: describe overall trend last vs prev
#             last_t = d["__dt"].max()
#             prev_times = d["__dt"].sort_values().unique()
#             prev_t = prev_times[-2] if len(prev_times) >= 2 else None
#             last_val = d.loc[d["__dt"] == last_t, y].sum()
#             if prev_t is not None:
#                 prev_val = d.loc[d["__dt"] == prev_t, y].sum()
#                 if pd.notna(prev_val) and prev_val != 0:
#                     chg = (last_val - prev_val) / prev_val
#                     dir_word = "up" if chg >= 0 else "down"
#                     insights.append(
#                         f"Latest {_format_num(last_val)} {y.replace('_',' ')}; {dir_word} {_format_pct(abs(chg))} vs previous point."
#                     )

#     # ---------------- CATEGORICAL INSIGHTS ----------------
#     if cat and cat in d.columns:
#         grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#         if not grp.empty:
#             top_k = grp.head(3)
#             names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
#             insights.append(f"Top {cat}s by {y.replace('_',' ')}: {names}.")
#             if grp.sum() > 0:
#                 shares = (grp / grp.sum()).head(3)
#                 share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
#                 insights.append(f"Share of total {y.replace('_',' ')}: {share_txt}.")

#     # ---------------- FALLBACK / TOTAL ----------------
#     if not insights:
#         total = pd.to_numeric(d[y], errors="coerce").sum()
#         insights.append(f"Total {y.replace('_',' ')} in the shown result: {_format_num(total)}.")

#     return insights[:3]

# # =============================================================================
# # NEW: PAYLOAD-AWARE INSIGHTS (for your ITEMSSSSS JSON)
# # =============================================================================

# def _pct_to_str(p: Optional[float], signed: bool = True, decimals: int = 2) -> str:
#     if p is None or (isinstance(p, float) and (math.isnan(p) or math.isinf(p))):
#         return "NA"
#     pct = p * 100.0
#     s = f"{pct:.{decimals}f}%"
#     if signed and pct > 0:
#         s = "+" + s
#     return s

# def _rupees_compact(n: Optional[float]) -> str:
#     # keep it simple and neutral (no locale lib)
#     try:
#         n = float(n)
#     except Exception:
#         return "NA"
#     if abs(n) >= 1_00_00_000:   # 10M+
#         return f"₹{n/1_00_00_000:.2f}Cr"
#     if abs(n) >= 1_00_000:      # 100k+
#         return f"₹{n/1_00_000:.2f}L"
#     return f"₹{n:,.0f}"

# def _months_inclusive(start_str: str, end_str: str) -> int:
#     try:
#         s = datetime.fromisoformat(start_str[:10])
#         e = datetime.fromisoformat(end_str[:10])
#     except Exception:
#         return 0
#     return (e.year - s.year) * 12 + (e.month - s.month) + 1

# def _safe_get(d: Dict[str, Any], path: List[str], default=None):
#     cur = d
#     for key in path:
#         if isinstance(cur, dict) and key in cur:
#             cur = cur[key]
#         else:
#             return default
#     return cur

# def _calc_growth(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
#     try:
#         if curr is None or prev is None or prev == 0:
#             return None
#         return (curr - prev) / prev
#     except Exception:
#         return None

# def _calc_cagr(v0: Optional[float], vN: Optional[float], years: float) -> Optional[float]:
#     try:
#         if v0 is None or vN is None or v0 <= 0 or years <= 0:
#             return None
#         return (vN / v0) ** (1.0 / years) - 1.0
#     except Exception:
#         return None

# # ---------- per-mode insight builders ----------

# def _insight_mat_compare(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # accept either payload['mat_compare']['periods'] or nested variant
#     periods: List[Dict[str, Any]] = (
#         _safe_get(payload, ["mat_compare", "periods"], [])
#         or _safe_get(payload, ["mat_compare", "mat_compare", "periods"], [])
#         or []
#     )
#     if not periods:
#         return {"bullets": ["No MAT periods available to compare."]}

#     # sort by rank if available; else keep given order
#     periods_sorted = sorted(periods, key=lambda x: x.get("rank", 9999))
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # Headline on top period
#     top = periods_sorted[0]
#     top_label = top.get("mat_label", "Latest")
#     top_val = top.get("value_sales")
#     bullets.append(f"{top_label} value sales reached {_rupees_compact(top_val)} (rank #1 among shown periods).")

#     # Pairwise growth
#     if len(periods_sorted) >= 2:
#         g_10 = _calc_growth(periods_sorted[0].get("value_sales"), periods_sorted[1].get("value_sales"))
#         if g_10 is not None:
#             bullets.append(f"{periods_sorted[0].get('mat_label','P1')} vs {periods_sorted[1].get('mat_label','P2')}: {_pct_to_str(g_10)}.")
#             derived["growth_p1_vs_p2_pct"] = round(g_10 * 100, 6)
#     if len(periods_sorted) >= 3:
#         g_21 = _calc_growth(periods_sorted[1].get("value_sales"), periods_sorted[2].get("value_sales"))
#         if g_21 is not None:
#             bullets.append(f"{periods_sorted[1].get('mat_label','P2')} vs {periods_sorted[2].get('mat_label','P3')}: {_pct_to_str(g_21)}.")
#             derived["growth_p2_vs_p3_pct"] = round(g_21 * 100, 6)

#         # 2-year CAGR (assuming 1 year spacing)
#         cagr = _calc_cagr(periods_sorted[2].get("value_sales"), periods_sorted[0].get("value_sales"), years=2.0)
#         if cagr is not None:
#             bullets.append(f"Two-year CAGR across shown MATs: {_pct_to_str(cagr, signed=False)}.")
#             derived["cagr_2y_pct"] = round(cagr * 100, 6)

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# def _insight_yoy(payload: Dict[str, Any]) -> Dict[str, Any]:
#     yoy_items: List[Dict[str, Any]] = _safe_get(payload, ["yoy", "items"], []) or []
#     measure_type = _safe_get(payload, ["yoy", "measure_type"], "measure")
#     if not yoy_items:
#         return {"bullets": ["No YoY items available."]}

#     # If brand present, rank by yoy_pct
#     branded = [it for it in yoy_items if "brand" in it]
#     bullets: List[str] = []

#     if branded:
#         branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)
#         lead = branded[0]
#         bullets.append(f"{str(lead.get('brand')).title()} leads {measure_type} YoY at {_pct_to_str(lead.get('yoy_pct', 0.0))}.")
#         if len(branded) >= 2:
#             second = branded[1]
#             bullets.append(f"Next is {str(second.get('brand')).title()} at {_pct_to_str(second.get('yoy_pct', 0.0))}.")
#         pos_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) > 0)
#         neg_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) < 0)
#         if pos_cnt and not neg_cnt:
#             bullets.append("All tracked brands are growing YoY.")
#         elif neg_cnt and not pos_cnt:
#             bullets.append("All tracked brands are declining YoY.")
#         else:
#             bullets.append(f"{pos_cnt} brand(s) growing, {neg_cnt} declining YoY.")
#         return {"bullets": bullets}

#     # single total (no brand)
#     g = yoy_items[0].get("yoy_pct", 0.0)
#     bullets.append(f"YoY change is {_pct_to_str(g)}.")
#     return {"bullets": bullets}

# def _insight_totals(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # Handle single total in bar.items (e.g., total unit_sales for a brand)
#     bar_items = _safe_get(payload, ["bar", "items"], [])
#     measure = str(payload.get("measure", "")).lower()
#     if not isinstance(bar_items, list) or len(bar_items) != 1:
#         return {"bullets": ["No single total found."]}

#     item = bar_items[0]
#     label = item.get("label", "Total")
#     # value may live in "value" or under measure name
#     total = item.get("value", None)
#     if total is None:
#         total = item.get(measure, None)

#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     if measure == "unit_sales":
#         bullets.append(f"{label} sold a total of {_format_num(total)} units in the selected period.")
#     elif measure == "value_sales":
#         bullets.append(f"{label} value sales totaled {_rupees_compact(total)} in the selected period.")
#     else:
#         bullets.append(f"{label} total for {measure} is {_format_num(total)}.")

#     # optional monthly average if window present
#     win = payload.get("window", {})
#     start, end = win.get("start"), win.get("end")
#     months = _months_inclusive(start, end) if (start and end) else 0
#     if months > 0 and isinstance(total, (int, float)):
#         avg = total / months
#         if measure == "unit_sales":
#             bullets.append(f"~{_format_num(avg)} units per month on average.")
#         elif measure == "value_sales":
#             bullets.append(f"~{_rupees_compact(avg)} per month on average.")
#         derived["avg_per_month"] = avg
#         derived["months"] = months

#     out = {"bullets": bullets}
#     if derived:
#         out["derived"] = derived
#     return out

# def _insight_trend_line(payload: Dict[str, Any]) -> Dict[str, Any]:
#     trend = payload.get("trend", {})
#     overall = trend.get("overall", {})
#     by_brand = trend.get("by_brand", [])
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # Overall peak/trough messaging
#     omax = overall.get("max", {})
#     omin = overall.get("min", {})
#     if "value" in omax and "value" in omin and omax.get("value") and omin.get("value"):
#         bullets.append(f"Overall peak in {omax.get('label','peak')} and trough in {omin.get('label','trough')}.")
#         drop = (omax["value"] - omin["value"]) / omax["value"] if omax["value"] else None
#         if drop is not None:
#             derived["overall_peak_to_trough_drop_pct"] = round(drop * 100, 6)

#     # Brand-wise peak→trough ranges
#     ranges: List[str] = []
#     for b in by_brand or []:
#         name = b.get("brand", "")
#         vmax = _safe_get(b, ["max", "value"], None)
#         vmin = _safe_get(b, ["min", "value"], None)
#         if vmax and vmin and vmax > 0:
#             drop = (vmax - vmin) / vmax
#             derived[f"{name.lower()}_peak_to_trough_drop_pct"] = round(drop * 100, 6)
#             ranges.append(f"{name} ~{int(round(drop*100))}%")

#     if ranges:
#         bullets.append("Peak→trough range (approx): " + ", ".join(ranges) + ".")

#     # Seasonality hint if multiple brands share trough label
#     trough_labels = [b.get("min", {}).get("label") for b in (by_brand or []) if b.get("min")]
#     if trough_labels:
#         common = max(set(trough_labels), key=trough_labels.count)
#         if trough_labels.count(common) >= 2:
#             bullets.append(f"Multiple brands trough around {common}, indicating seasonality.")

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# # ---------- public router ----------

# def attach_insights(payload: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Appends an 'insights' block to your ITEMSSSSS payload without changing existing keys.
#     Supports:
#       - MAT_COMPARE (payload['mat_compare'])
#       - YOY / YTD_YOY (payload['yoy'])
#       - LINE trend (payload['trend'])
#       - Totals (single BAR item, e.g., total unit_sales)
#     """
#     try:
#         mode = str(payload.get("mode", "")).upper()

#         insights_block: Optional[Dict[str, Any]] = None

#         # Prefer explicit structures
#         if mode == "MAT_COMPARE" or "mat_compare" in payload:
#             insights_block = _insight_mat_compare(payload)

#         if insights_block is None and "trend" in payload:
#             insights_block = _insight_trend_line(payload)

#         if insights_block is None and "yoy" in payload:
#             insights_block = _insight_yoy(payload)

#         if insights_block is None and mode == "BAR":
#             bar_items = _safe_get(payload, ["bar", "items"], [])
#             if isinstance(bar_items, list) and len(bar_items) == 1:
#                 insights_block = _insight_totals(payload)

#         if insights_block is None:
#             insights_block = {"bullets": ["No insight template matched this response."]}

#         out = dict(payload)
#         out["insights"] = insights_block
#         return out

#     except Exception as e:
#         out = dict(payload)
#         out["insights"] = {"bullets": [f"Insight generation failed: {e}"]}
#         return out

# # =============================================================================
# # OPTIONAL: quick manual test
# # =============================================================================
# if __name__ == "__main__":
#     # paste any of your ITEMSSSSS samples below to verify
#     sample = {
#         "mode": "MAT_COMPARE",
#         "measure": "value_sales",
#         "mat_compare": {
#             "periods": [
#                 {"mat_label": "MAT 2025", "value_sales": 56315997.11, "rank": 1},
#                 {"mat_label": "MAT 2024", "value_sales": 55090425.83, "rank": 2},
#                 {"mat_label": "MAT 2023", "value_sales": 54262187.76, "rank": 3},
#             ]
#         }
#     }
#     print(attach_insights(sample))





#Generating natural language insights with variations, no peaks for line chart , ytd/mat yoy window not showing no normal yoy ytd, top 2 brands only not n








# backend/insights.py

# from __future__ import annotations

# import math
# import random
# from datetime import datetime
# from typing import Dict, Any, List, Optional, Tuple

# import numpy as np
# import pandas as pd

# CAT_CANDS = ["brand", "category", "market", "channel", "segment", "manufacturer"]

# # =============================================================================
# # EXISTING HELPERS (kept as-is)
# # =============================================================================

# def _first_numeric(df: pd.DataFrame) -> str | None:
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     return None

# def _pick_measure_col(df: pd.DataFrame, meta: dict) -> str | None:
#     # Prefer meta.measure if it exists and is numeric
#     m = (meta or {}).get("measure")
#     if isinstance(m, str) and m in df.columns and pd.api.types.is_numeric_dtype(df[m]):
#         return m
#     # Else try common names
#     for cand in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if cand in df.columns and pd.api.types.is_numeric_dtype(df[cand]):
#             return cand
#     # Else first numeric
#     return _first_numeric(df)

# def _pick_cat_dim(df: pd.DataFrame) -> str | None:
#     for c in CAT_CANDS:
#         if c in df.columns:
#             return c
#     return None

# def _format_num(x: float) -> str:
#     try:
#         if abs(x) >= 1_000_000:
#             return f"{x/1_000_000:.1f}M"
#         if abs(x) >= 1_000:
#             return f"{x/1_000:.1f}K"
#         return f"{x:.0f}"
#     except Exception:
#         return str(x)

# def _format_pct(x: float) -> str:
#     try:
#         return f"{x*100:.1f}%"
#     except Exception:
#         return "NA"

# def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Heuristic, lightweight insights that never fail silently.
#     Works for table/bar/line; time or no time; any dim.
#     """
#     insights: list[str] = []

#     # --- guardrails ---
#     if df is None or not isinstance(df, pd.DataFrame) or df.empty:
#         return ["No data to analyze."]

#     # Choose measure (y)s
#     y = _pick_measure_col(df, meta)
#     if y is None:
#         insights.append("No numeric measure returned, so only structural results are shown.")
#         return insights

#     # Pick a categorical dim if present
#     cat = _pick_cat_dim(df)

#     # Detect time
#     has_date = "date" in df.columns
#     has_month = "month_year" in df.columns

#     # Normalize copy for safe ops
#     d = df.copy()

#     # ---------------- TIME-SERIES INSIGHTS ----------------
#     if has_month or has_date:
#         # prefer month_year string for readability
#         if has_date:
#             try:
#                 d["__dt"] = pd.to_datetime(d["date"])
#             except Exception:
#                 d["__dt"] = pd.to_datetime(d["date"], errors="coerce")
#         else:
#             # build a sortable month from month_year
#             parsed = pd.to_datetime(d["month_year"], errors="coerce")
#             d["__dt"] = parsed.dt.to_period("M").dt.to_timestamp()

#         # If categorical exists (e.g., brand lines), focus on top line at the end
#         if cat and cat in d.columns:
#             # last month in the result
#             last_t = d["__dt"].max()
#             cur = d[d["__dt"] == last_t]

#             # If multiple brands, find top latest and compare to previous point
#             grp = cur.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#             if not grp.empty:
#                 top_brand = grp.index[0]
#                 top_val = grp.iloc[0]

#                 # Compute previous value for that brand (prev timestamp)
#                 prev_t = d["__dt"].sort_values().unique()
#                 prev_t = prev_t[-2] if len(prev_t) >= 2 else None

#                 if prev_t is not None:
#                     prev_val = d[(d[cat] == top_brand) & (d["__dt"] == prev_t)][y].sum()
#                     if pd.notna(prev_val) and prev_val != 0:
#                         chg = (top_val - prev_val) / prev_val
#                         dir_word = "up" if chg >= 0 else "down"
#                         # 4–5 variations
#                         variations = [
#                             "{brand} leads the latest with {val} {metric} ({dir} {chg} vs previous).",
#                             "Most recent leader: {brand} at {val} {metric} ({dir} {chg} vs last point).",
#                             "{brand} tops the newest period at {val} {metric} ({dir} {chg} vs prior).",
#                             "Latest snapshot: {brand} is #1 with {val} {metric} ({dir} {chg} m/m).",
#                             "{brand} holds the lead currently — {val} {metric} ({dir} {chg} vs prev).",
#                         ]
#                         insights.append(
#                             random.choice(variations).format(
#                                 brand=top_brand,
#                                 val=_format_num(top_val),
#                                 metric=y.replace("_", " "),
#                                 dir=dir_word,
#                                 chg=_format_pct(abs(chg)),
#                             )
#                         )

#                 # Gap to #2 at the last point
#                 if len(grp) >= 2:
#                     gap = grp.iloc[0] - grp.iloc[1]
#                     variations_gap = [
#                         "Gap to #{rank2} {b2}: {gap} on the latest point.",
#                         "Lead over {b2} stands at {gap} (most recent period).",
#                         "Current spread vs {b2}: {gap}.",
#                         "Latest margin vs {b2}: {gap}.",
#                         "The distance to {b2} right now is {gap}.",
#                     ]
#                     insights.append(
#                         random.choice(variations_gap).format(
#                             rank2=2, b2=grp.index[1], gap=_format_num(gap)
#                         )
#                     )
#         else:
#             # No categorical: describe overall trend last vs prev
#             last_t = d["__dt"].max()
#             prev_times = d["__dt"].sort_values().unique()
#             prev_t = prev_times[-2] if len(prev_times) >= 2 else None
#             last_val = d.loc[d["__dt"] == last_t, y].sum()
#             if prev_t is not None:
#                 prev_val = d.loc[d["__dt"] == prev_t, y].sum()
#                 if pd.notna(prev_val) and prev_val != 0:
#                     chg = (last_val - prev_val) / prev_val
#                     dir_word = "up" if chg >= 0 else "down"
#                     variations_line = [
#                         "Latest {metric}: {val}; {dir} {chg} vs previous.",
#                         "{metric} now at {val} — {dir} {chg} vs last period.",
#                         "Most recent {metric} is {val} ({dir} {chg} m/m).",
#                         "{metric} prints {val} in the latest period ({dir} {chg} vs prior).",
#                         "Current {metric} of {val} is {dir} {chg} against previous.",
#                     ]
#                     insights.append(
#                         random.choice(variations_line).format(
#                             metric=y.replace("_", " "),
#                             val=_format_num(last_val),
#                             dir=dir_word,
#                             chg=_format_pct(abs(chg)),
#                         )
#                     )

#     # ---------------- CATEGORICAL INSIGHTS ----------------
#     if cat and cat in d.columns:
#         grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#         if not grp.empty:
#             top_k = grp.head(3)
#             names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
#             variations_top = [
#                 "Top {cat}s by {metric}: {names}.",
#                 "Leaders on {metric}: {names}.",
#                 "Ranking by {metric}: {names}.",
#                 "Highest {metric}: {names}.",
#                 "Top performers ({metric}): {names}.",
#             ]
#             insights.append(
#                 random.choice(variations_top).format(
#                     cat=cat, metric=y.replace("_", " "), names=names
#                 )
#             )
#             if grp.sum() > 0:
#                 shares = (grp / grp.sum()).head(3)
#                 share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
#                 variations_share = [
#                     "Share of total {metric}: {share}.",
#                     "Contribution split ({metric}): {share}.",
#                     "Within shown total {metric}, shares are: {share}.",
#                     "{metric} mix: {share}.",
#                     "Top-3 share breakdown ({metric}): {share}.",
#                 ]
#                 insights.append(
#                     random.choice(variations_share).format(
#                         metric=y.replace("_", " "), share=share_txt
#                     )
#                 )

#     # ---------------- FALLBACK / TOTAL ----------------
#     if not insights:
#         total = pd.to_numeric(d[y], errors="coerce").sum()
#         variations_total = [
#             "Total {metric} in the result: {val}.",
#             "Aggregate {metric}: {val}.",
#             "Combined {metric} across rows: {val}.",
#             "Overall {metric} sums to {val}.",
#             "Sum of {metric}: {val}.",
#         ]
#         insights.append(
#             random.choice(variations_total).format(
#                 metric=y.replace("_", " "), val=_format_num(total)
#             )
#         )

#     return insights[:3]

# # =============================================================================
# # NEW: PAYLOAD-AWARE INSIGHTS (for your ITEMSSSSS JSON)
# # =============================================================================

# def _pct_to_str(p: Optional[float], signed: bool = True, decimals: int = 2) -> str:
#     if p is None or (isinstance(p, float) and (math.isnan(p) or math.isinf(p))):
#         return "NA"
#     pct = p * 100.0
#     s = f"{pct:.{decimals}f}%"
#     if signed and pct > 0:
#         s = "+" + s
#     return s

# def _rupees_compact(n: Optional[float]) -> str:
#     # keep it simple and neutral (no locale lib)
#     try:
#         n = float(n)
#     except Exception:
#         return "NA"
#     if abs(n) >= 1_00_00_000:   # 10M+
#         return f"₹{n/1_00_00_000:.2f}Cr"
#     if abs(n) >= 1_00_000:      # 100k+
#         return f"₹{n/1_00_000:.2f}L"
#     return f"₹{n:,.0f}"

# def _months_inclusive(start_str: str, end_str: str) -> int:
#     try:
#         s = datetime.fromisoformat(start_str[:10])
#         e = datetime.fromisoformat(end_str[:10])
#     except Exception:
#         return 0
#     return (e.year - s.year) * 12 + (e.month - s.month) + 1

# def _safe_get(d: Dict[str, Any], path: List[str], default=None):
#     cur = d
#     for key in path:
#         if isinstance(cur, dict) and key in cur:
#             cur = cur[key]
#         else:
#             return default
#     return cur

# def _calc_growth(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
#     try:
#         if curr is None or prev is None or prev == 0:
#             return None
#         return (curr - prev) / prev
#     except Exception:
#         return None

# def _calc_cagr(v0: Optional[float], vN: Optional[float], years: float) -> Optional[float]:
#     try:
#         if v0 is None or vN is None or v0 <= 0 or years <= 0:
#             return None
#         return (vN / v0) ** (1.0 / years) - 1.0
#     except Exception:
#         return None

# # ---------- per-mode insight builders with variations ----------

# def _insight_mat_compare(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # accept either payload['mat_compare']['periods'] or nested variant
#     periods: List[Dict[str, Any]] = (
#         _safe_get(payload, ["mat_compare", "periods"], [])
#         or _safe_get(payload, ["mat_compare", "mat_compare", "periods"], [])
#         or []
#     )
#     if not periods:
#         return {"bullets": ["No MAT periods available to compare."]}

#     # sort by rank if available; else keep given order
#     periods_sorted = sorted(periods, key=lambda x: x.get("rank", 9999))
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # Headline on top period
#     top = periods_sorted[0]
#     top_label = top.get("mat_label", "Latest")
#     top_val = top.get("value_sales")

#     variations_headline = [
#         "{label} value sales reached {val} (rank #1 among shown periods).",
#         "{label} comes out on top with {val} in value sales.",
#         "Highest value sales in the set: {label} at {val}.",
#         "{label} leads the comparison, posting {val} in value sales.",
#         "{label} prints the peak value sales at {val}.",
#     ]
#     bullets.append(
#         random.choice(variations_headline).format(
#             label=top_label, val=_rupees_compact(top_val)
#         )
#     )

#     # Pairwise growth
#     if len(periods_sorted) >= 2:
#         p1 = periods_sorted[0]
#         p2 = periods_sorted[1]
#         g_10 = _calc_growth(p1.get("value_sales"), p2.get("value_sales"))
#         if g_10 is not None:
#             variations_pair = [
#                 "{p1} vs {p2}: {g}.",
#                 "Change from {p2} to {p1}: {g}.",
#                 "Step-up {p2}→{p1}: {g}.",
#                 "{p1} relative to {p2}: {g}.",
#                 "Delta {p1} over {p2}: {g}.",
#             ]
#             bullets.append(
#                 random.choice(variations_pair).format(
#                     p1=p1.get("mat_label", "P1"),
#                     p2=p2.get("mat_label", "P2"),
#                     g=_pct_to_str(g_10),
#                 )
#             )
#             derived["growth_p1_vs_p2_pct"] = round(g_10 * 100, 6)

#     if len(periods_sorted) >= 3:
#         p2 = periods_sorted[1]
#         p3 = periods_sorted[2]
#         g_21 = _calc_growth(p2.get("value_sales"), p3.get("value_sales"))
#         if g_21 is not None:
#             variations_pair2 = [
#                 "{p2} vs {p3}: {g}.",
#                 "From {p3} to {p2}: {g}.",
#                 "Lift {p3}→{p2}: {g}.",
#                 "{p2} compared with {p3}: {g}.",
#                 "Delta {p2} over {p3}: {g}.",
#             ]
#             bullets.append(
#                 random.choice(variations_pair2).format(
#                     p2=p2.get("mat_label", "P2"),
#                     p3=p3.get("mat_label", "P3"),
#                     g=_pct_to_str(g_21),
#                 )
#             )
#             derived["growth_p2_vs_p3_pct"] = round(g_21 * 100, 6)

#         # 2-year CAGR (assuming 1 year spacing)
#         cagr = _calc_cagr(p3.get("value_sales"), periods_sorted[0].get("value_sales"), years=2.0)
#         if cagr is not None:
#             variations_cagr = [
#                 "Two-year CAGR across shown MATs: {c}.",
#                 "2Y CAGR (MAT set): {c}.",
#                 "CAGR over the last two MATs: {c}.",
#                 "Across the two-year span, CAGR is {c}.",
#                 "Two-year compounded growth: {c}.",
#             ]
#             bullets.append(random.choice(variations_cagr).format(c=_pct_to_str(cagr, signed=False)))
#             derived["cagr_2y_pct"] = round(cagr * 100, 6)

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# def _insight_yoy(payload: Dict[str, Any]) -> Dict[str, Any]:
#     yoy_items: List[Dict[str, Any]] = _safe_get(payload, ["yoy", "items"], []) or []
#     measure_type = _safe_get(payload, ["yoy", "measure_type"], "measure")
#     if not yoy_items:
#         return {"bullets": ["No YoY items available."]}

#     # If brand present, rank by yoy_pct
#     branded = [it for it in yoy_items if "brand" in it]
#     bullets: List[str] = []

#     if branded:
#         branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)
#         lead = branded[0]
#         lead_name = str(lead.get("brand")).title()
#         lead_pct = _pct_to_str(lead.get("yoy_pct", 0.0))
#         variations_lead = [
#             "{brand} leads {mt} YoY at {pct}.",
#             "Top YoY mover on {mt}: {brand} ({pct}).",
#             "{brand} shows the strongest YoY on {mt} at {pct}.",
#             "{brand} is ahead on {mt} YoY with {pct}.",
#             "Leading YoY growth ({mt}): {brand} at {pct}.",
#         ]
#         bullets.append(random.choice(variations_lead).format(brand=lead_name, mt=measure_type, pct=lead_pct))

#         if len(branded) >= 2:
#             second = branded[1]
#             second_name = str(second.get("brand")).title()
#             second_pct = _pct_to_str(second.get("yoy_pct", 0.0))
#             variations_second = [
#                 "Next is {brand} at {pct}.",
#                 "Runner-up: {brand} ({pct}).",
#                 "Followed by {brand} at {pct}.",
#                 "Then comes {brand} with {pct}.",
#                 "{brand} follows at {pct}.",
#             ]
#             bullets.append(random.choice(variations_second).format(brand=second_name, pct=second_pct))

#         pos_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) > 0)
#         neg_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) < 0)
#         if pos_cnt and not neg_cnt:
#             variations_allpos = [
#                 "All tracked brands are growing YoY.",
#                 "Every brand in scope shows YoY growth.",
#                 "YoY is positive across the board.",
#                 "All brands post positive YoY.",
#                 "Universal YoY growth among tracked brands.",
#             ]
#             bullets.append(random.choice(variations_allpos))
#         elif neg_cnt and not pos_cnt:
#             variations_allneg = [
#                 "All tracked brands are declining YoY.",
#                 "Every brand in scope shows a YoY decline.",
#                 "YoY is negative across the board.",
#                 "All brands post YoY contraction.",
#                 "Universal YoY decline among tracked brands.",
#             ]
#             bullets.append(random.choice(variations_allneg))
#         else:
#             variations_mix = [
#                 "{p} brand(s) growing, {n} declining YoY.",
#                 "Mixed picture: {p} up and {n} down YoY.",
#                 "YoY is split — {p} positive, {n} negative.",
#                 "{p} brands up YoY; {n} down.",
#                 "Growth is uneven: {p} positive vs {n} negative YoY.",
#             ]
#             bullets.append(random.choice(variations_mix).format(p=pos_cnt, n=neg_cnt))
#         return {"bullets": bullets}

#     # single total (no brand)
#     g = yoy_items[0].get("yoy_pct", 0.0)
#     variations_total = [
#         "YoY change is {g}.",
#         "Overall YoY stands at {g}.",
#         "Aggregate YoY movement: {g}.",
#         "Headline YoY shift: {g}.",
#         "Total YoY delta: {g}.",
#     ]
#     bullets.append(random.choice(variations_total).format(g=_pct_to_str(g)))
#     return {"bullets": bullets}

# def _insight_totals(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # Handle single total in bar.items (e.g., total unit_sales for a brand)
#     bar_items = _safe_get(payload, ["bar", "items"], [])
#     measure = str(payload.get("measure", "")).lower()
#     if not isinstance(bar_items, list) or len(bar_items) != 1:
#         return {"bullets": ["No single total found."]}

#     item = bar_items[0]
#     label = item.get("label", "Total")
#     # value may live in "value" or under measure name
#     total = item.get("value", None)
#     if total is None:
#         total = item.get(measure, None)

#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     if measure == "unit_sales":
#         variations_units = [
#             "{label} sold a total of {val} units in the selected period.",
#             "Total units for {label}: {val}.",
#             "{label} accumulated {val} units over the window.",
#             "Across the period, {label} reached {val} units.",
#             "Units summed for {label}: {val}.",
#         ]
#         bullets.append(random.choice(variations_units).format(label=label, val=_format_num(total)))
#     elif measure == "value_sales":
#         variations_value = [
#             "{label} value sales totaled {val} in the selected period.",
#             "Total value sales for {label}: {val}.",
#             "{label} posted {val} in value sales across the window.",
#             "Aggregate value sales for {label} come to {val}.",
#             "Cumulative value sales for {label}: {val}.",
#         ]
#         bullets.append(random.choice(variations_value).format(label=label, val=_rupees_compact(total)))
#     else:
#         variations_other = [
#             "{label} total for {metric} is {val}.",
#             "Aggregate {metric} for {label}: {val}.",
#             "{label} recorded {val} on {metric}.",
#             "Combined {metric} for {label}: {val}.",
#             "Overall {metric} ({label}): {val}.",
#         ]
#         bullets.append(random.choice(variations_other).format(label=label, metric=measure, val=_format_num(total)))

#     # optional monthly average if window present
#     win = payload.get("window", {})
#     start, end = win.get("start"), win.get("end")
#     months = _months_inclusive(start, end) if (start and end) else 0
#     if months > 0 and isinstance(total, (int, float)):
#         avg = total / months
#         if measure == "unit_sales":
#             variations_avg = [
#                 "~{avg} units per month on average.",
#                 "Monthly run-rate ~{avg} units.",
#                 "That’s roughly {avg} units/month.",
#                 "Avg monthly volume ~{avg} units.",
#                 "Per-month average is ~{avg} units.",
#             ]
#             bullets.append(random.choice(variations_avg).format(avg=_format_num(avg)))
#         elif measure == "value_sales":
#             variations_avg_val = [
#                 "~{avg} per month on average.",
#                 "Monthly run-rate ~{avg}.",
#                 "That’s roughly {avg} each month.",
#                 "Avg monthly value ~{avg}.",
#                 "Per-month average is ~{avg}.",
#             ]
#             bullets.append(random.choice(variations_avg_val).format(avg=_rupees_compact(avg)))
#         derived["avg_per_month"] = avg
#         derived["months"] = months

#     out = {"bullets": bullets}
#     if derived:
#         out["derived"] = derived
#     return out

# def _insight_trend_line(payload: Dict[str, Any]) -> Dict[str, Any]:
#     trend = payload.get("trend", {})
#     overall = trend.get("overall", {})
#     by_brand = trend.get("by_brand", [])
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # Overall peak/trough messaging
#     omax = overall.get("max", {})
#     omin = overall.get("min", {})
#     if "value" in omax and "value" in omin and omax.get("value") and omin.get("value"):
#         variations_overall = [
#             "Overall peak in {peak} and trough in {trough}.",
#             "The series peaks around {peak} and bottoms near {trough}.",
#             "Top reading: {peak}; lowest: {trough}.",
#             "Peak appears in {peak}, while the trough is {trough}.",
#             "High watermark at {peak}; low at {trough}.",
#         ]
#         bullets.append(
#             random.choice(variations_overall).format(
#                 peak=omax.get("label", "peak"),
#                 trough=omin.get("label", "trough"),
#             )
#         )
#         drop = (omax["value"] - omin["value"]) / omax["value"] if omax["value"] else None
#         if drop is not None:
#             derived["overall_peak_to_trough_drop_pct"] = round(drop * 100, 6)

#     # Brand-wise peak→trough ranges
#     ranges: List[str] = []
#     for b in by_brand or []:
#         name = b.get("brand", "")
#         vmax = _safe_get(b, ["max", "value"], None)
#         vmin = _safe_get(b, ["min", "value"], None)
#         if vmax and vmin and vmax > 0:
#             drop = (vmax - vmin) / vmax
#             derived[f"{name.lower()}_peak_to_trough_drop_pct"] = round(drop * 100, 6)
#             ranges.append(f"{name} ~{int(round(drop*100))}%")

#     if ranges:
#         variations_ranges = [
#             "Peak→trough range (approx): {list}.",
#             "Approximate drawdowns: {list}.",
#             "Peak-to-bottom swings: {list}.",
#             "Volatility snapshot (peak→trough): {list}.",
#             "Range from highs to lows: {list}.",
#         ]
#         bullets.append(random.choice(variations_ranges).format(list=", ".join(ranges)))

#     # Seasonality hint if multiple brands share trough label
#     trough_labels = [b.get("min", {}).get("label") for b in (by_brand or []) if b.get("min")]
#     if trough_labels:
#         common = max(set(trough_labels), key=trough_labels.count)
#         if trough_labels.count(common) >= 2:
#             variations_season = [
#                 "Multiple brands trough around {label}, hinting at seasonality.",
#                 "Common trough near {label} — seasonal pattern likely.",
#                 "Several brands dip around {label}, indicating seasonality.",
#                 "Shared low point around {label} suggests seasonal effects.",
#                 "Trough clustering at {label} points to seasonality.",
#             ]
#             bullets.append(random.choice(variations_season).format(label=common))

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# # ---------- public router ----------

# def attach_insights(payload: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Appends an 'insights' block to your ITEMSSSSS payload without changing existing keys.
#     Supports:
#       - MAT_COMPARE (payload['mat_compare'])
#       - YOY / YTD_YOY (payload['yoy'])
#       - LINE trend (payload['trend'])
#       - Totals (single BAR item, e.g., total unit_sales)
#     """
#     try:
#         mode = str(payload.get("mode", "")).upper()

#         insights_block: Optional[Dict[str, Any]] = None

#         # Prefer explicit structures
#         if mode == "MAT_COMPARE" or "mat_compare" in payload:
#             insights_block = _insight_mat_compare(payload)

#         if insights_block is None and "trend" in payload:
#             insights_block = _insight_trend_line(payload)

#         if insights_block is None and "yoy" in payload:
#             insights_block = _insight_yoy(payload)

#         if insights_block is None and mode == "BAR":
#             bar_items = _safe_get(payload, ["bar", "items"], [])
#             if isinstance(bar_items, list) and len(bar_items) == 1:
#                 insights_block = _insight_totals(payload)

#         if insights_block is None:
#             insights_block = {"bullets": ["No insight template matched this response."]}

#         out = dict(payload)
#         out["insights"] = insights_block
#         return out

#     except Exception as e:
#         out = dict(payload)
#         out["insights"] = {"bullets": [f"Insight generation failed: {e}"]}
#         return out

# # =============================================================================
# # OPTIONAL: quick manual test
# # =============================================================================
# if __name__ == "__main__":
#     # paste any of your ITEMSSSSS samples below to verify
#     sample = {
#         "mode": "MAT_COMPARE",
#         "measure": "value_sales",
#         "mat_compare": {
#             "periods": [
#                 {"mat_label": "MAT 2025", "value_sales": 56315997.11, "rank": 1},
#                 {"mat_label": "MAT 2024", "value_sales": 55090425.83, "rank": 2},
#                 {"mat_label": "MAT 2023", "value_sales": 54262187.76, "rank": 3},
#             ]
#         }
#     }
#     print(attach_insights(sample))














#Working code for top n brands ,includes windows , peaks for line chart  



# # backend/insights.py

# from __future__ import annotations

# import math
# import random
# from datetime import datetime
# from typing import Dict, Any, List, Optional, Tuple

# import numpy as np
# import pandas as pd

# CAT_CANDS = ["brand", "category", "market", "channel", "segment", "manufacturer"]

# # =============================================================================
# # EXISTING HELPERS (kept as-is)
# # =============================================================================

# def _first_numeric(df: pd.DataFrame) -> str | None:
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     return None

# def _pick_measure_col(df: pd.DataFrame, meta: dict) -> str | None:
#     # Prefer meta.measure if it exists and is numeric
#     m = (meta or {}).get("measure")
#     if isinstance(m, str) and m in df.columns and pd.api.types.is_numeric_dtype(df[m]):
#         return m
#     # Else try common names
#     for cand in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if cand in df.columns and pd.api.types.is_numeric_dtype(df[cand]):
#             return cand
#     # Else first numeric
#     return _first_numeric(df)

# def _pick_cat_dim(df: pd.DataFrame) -> str | None:
#     for c in CAT_CANDS:
#         if c in df.columns:
#             return c
#     return None

# def _format_num(x: float) -> str:
#     try:
#         if abs(x) >= 1_000_000:
#             return f"{x/1_000_000:.1f}M"
#         if abs(x) >= 1_000:
#             return f"{x/1_000:.1f}K"
#         return f"{x:.0f}"
#     except Exception:
#         return str(x)

# def _format_pct(x: float) -> str:
#     try:
#         return f"{x*100:.1f}%"
#     except Exception:
#         return "NA"

# def _format_period(start: Optional[str], end: Optional[str]) -> Optional[str]:
#     if not start or not end:
#         return None
#     # Keep ISO compact; consistent with your API
#     try:
#         s = datetime.fromisoformat(start[:10]).date().isoformat()
#         e = datetime.fromisoformat(end[:10]).date().isoformat()
#         return f"{s} → {e}"
#     except Exception:
#         return f"{start} → {end}"

# def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Heuristic, lightweight insights that never fail silently.
#     Works for table/bar/line; time or no time; any dim.
#     """
#     insights: list[str] = []

#     # --- guardrails ---
#     if df is None or not isinstance(df, pd.DataFrame) or df.empty:
#         return ["No data to analyze."]

#     # Choose measure (y)s
#     y = _pick_measure_col(df, meta)
#     if y is None:
#         insights.append("No numeric measure returned, so only structural results are shown.")
#         return insights

#     # Pick a categorical dim if present
#     cat = _pick_cat_dim(df)

#     # Detect time
#     has_date = "date" in df.columns
#     has_month = "month_year" in df.columns or "month" in df.columns

#     # Normalize copy for safe ops
#     d = df.copy()

#     # ---------------- TIME-SERIES INSIGHTS ----------------
#     if has_month or has_date:
#         # prefer month_year string for readability
#         if has_date:
#             try:
#                 d["__dt"] = pd.to_datetime(d["date"])
#             except Exception:
#                 d["__dt"] = pd.to_datetime(d["date"], errors="coerce")
#         else:
#             # build a sortable month from month_year or month
#             month_col = "month_year" if "month_year" in d.columns else "month"
#             parsed = pd.to_datetime(d[month_col], errors="coerce")
#             d["__dt"] = parsed.dt.to_period("M").dt.to_timestamp()

#         # If categorical exists (e.g., brand lines), focus on top line at the end
#         if cat and cat in d.columns:
#             # last month in the result
#             last_t = d["__dt"].max()
#             cur = d[d["__dt"] == last_t]

#             # If multiple brands, find top latest and compare to previous point
#             grp = cur.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#             if not grp.empty:
#                 top_brand = grp.index[0]
#                 top_val = grp.iloc[0]

#                 # Compute previous value for that brand (prev timestamp)
#                 prev_t = d["__dt"].sort_values().unique()
#                 prev_t = prev_t[-2] if len(prev_t) >= 2 else None

#                 if prev_t is not None:
#                     prev_val = d[(d[cat] == top_brand) & (d["__dt"] == prev_t)][y].sum()
#                     if pd.notna(prev_val) and prev_val != 0:
#                         chg = (top_val - prev_val) / prev_val
#                         dir_word = "up" if chg >= 0 else "down"
#                         variations = [
#                             "{brand} leads the latest with {val} {metric} ({dir} {chg} vs previous).",
#                             "Most recent leader: {brand} at {val} {metric} ({dir} {chg} vs last point).",
#                             "{brand} tops the newest period at {val} {metric} ({dir} {chg} vs prior).",
#                             "Latest snapshot: {brand} is #1 with {val} {metric} ({dir} {chg} m/m).",
#                             "{brand} holds the lead currently — {val} {metric} ({dir} {chg} vs prev).",
#                         ]
#                         insights.append(
#                             random.choice(variations).format(
#                                 brand=top_brand,
#                                 val=_format_num(top_val),
#                                 metric=y.replace("_", " "),
#                                 dir=dir_word,
#                                 chg=_format_pct(abs(chg)),
#                             )
#                         )

#                 # Gap to #2 at the last point
#                 if len(grp) >= 2:
#                     gap = grp.iloc[0] - grp.iloc[1]
#                     variations_gap = [
#                         "Gap to #{rank2} {b2}: {gap} on the latest point.",
#                         "Lead over {b2} stands at {gap} (most recent period).",
#                         "Current spread vs {b2}: {gap}.",
#                         "Latest margin vs {b2}: {gap}.",
#                         "The distance to {b2} right now is {gap}.",
#                     ]
#                     insights.append(
#                         random.choice(variations_gap).format(
#                             rank2=2, b2=grp.index[1], gap=_format_num(gap)
#                         )
#                     )
#                 # NEW: explicitly mention #3 when present
#                 if len(grp) >= 3:
#                     third_name = grp.index[2]
#                     third_val = grp.iloc[2]
#                     third_variants = [
#                         "In third place: {b3} at {v3}.",
#                         "Completing the top-3 is {b3} with {v3}.",
#                         "Third spot: {b3} ({v3}).",
#                         "{b3} rounds out the top-3 at {v3}.",
#                         "Also noteworthy at #3: {b3} with {v3}.",
#                     ]
#                     insights.append(
#                         random.choice(third_variants).format(
#                             b3=third_name, v3=_format_num(third_val)
#                         )
#                     )
#         else:
#             # No categorical: describe overall trend last vs prev
#             last_t = d["__dt"].max()
#             prev_times = d["__dt"].sort_values().unique()
#             prev_t = prev_times[-2] if len(prev_times) >= 2 else None
#             last_val = d.loc[d["__dt"] == last_t, y].sum()
#             if prev_t is not None:
#                 prev_val = d.loc[d["__dt"] == prev_t, y].sum()
#                 if pd.notna(prev_val) and prev_val != 0:
#                     chg = (last_val - prev_val) / prev_val
#                     dir_word = "up" if chg >= 0 else "down"
#                     variations_line = [
#                         "Latest {metric}: {val}; {dir} {chg} vs previous.",
#                         "{metric} now at {val} — {dir} {chg} vs last period.",
#                         "Most recent {metric} is {val} ({dir} {chg} m/m).",
#                         "{metric} prints {val} in the latest period ({dir} {chg} vs prior).",
#                         "Current {metric} of {val} is {dir} {chg} against previous.",
#                     ]
#                     insights.append(
#                         random.choice(variations_line).format(
#                             metric=y.replace("_", " "),
#                             val=_format_num(last_val),
#                             dir=dir_word,
#                             chg=_format_pct(abs(chg)),
#                         )
#                     )

#         # NEW: peak month callout (overall)
#         try:
#             # Aggregate overall by month and pick the peak
#             by_month = d.groupby(d["__dt"])[y].sum().sort_index()
#             if not by_month.empty:
#                 peak_t = by_month.idxmax()
#                 peak_v = by_month.max()
#                 peak_label = peak_t.strftime("%b %Y")
#                 peak_variants = [
#                     "Peak {metric} occurs in {label} at {val}.",
#                     "Highest {metric}: {label} ({val}).",
#                     "The series peaks in {label} with {val}.",
#                     "Top month is {label} at {val} on {metric}.",
#                     "{label} marks the peak for {metric} ({val}).",
#                 ]
#                 insights.append(
#                     random.choice(peak_variants).format(
#                         metric=y.replace("_", " "), label=peak_label, val=_format_num(peak_v)
#                     )
#                 )
#         except Exception:
#             pass

#         # NEW: show period range when present in meta
#         win = (meta or {}).get("window") or {}
#         pr = _format_period(win.get("start"), win.get("end"))
#         if pr:
#             period_variants = [
#                 "Period window: {pr}.",
#                 "Window considered: {pr}.",
#                 "Date range: {pr}.",
#                 "Coverage: {pr}.",
#                 "Time span in view: {pr}.",
#             ]
#             insights.append(random.choice(period_variants).format(pr=pr))

#     # ---------------- CATEGORICAL INSIGHTS ----------------
#     # if cat and cat in d.columns:
#     #     grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#     #     if not grp.empty:
#     #         top_k = grp.head(3)
#     #         names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
#     #         variations_top = [
#     #             "Top {cat}s by {metric}: {names}.",
#     #             "Leaders on {metric}: {names}.",
#     #             "Ranking by {metric}: {names}.",
#     #             "Highest {metric}: {names}.",
#     #             "Top performers ({metric}): {names}.",
#     #         ]
#     #         insights.append(
#     #             random.choice(variations_top).format(
#     #                 cat=cat, metric=y.replace("_", " "), names=names
#     #             )
#     #         )
#     #         if grp.sum() > 0:
#     #             shares = (grp / grp.sum()).head(3)
#     #             share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
#     #             variations_share = [
#     #                 "Share of total {metric}: {share}.",
#     #                 "Contribution split ({metric}): {share}.",
#     #                 "Within shown total {metric}, shares are: {share}.",
#     #                 "{metric} mix: {share}.",
#     #                 "Top-3 share breakdown ({metric}): {share}.",
#     #             ]
#     #             insights.append(
#     #                 random.choice(variations_share).format(
#     #                     metric=y.replace("_", " "), share=share_txt
#     #                 )
#     #             )

# # ---------------- CATEGORICAL INSIGHTS ----------------
#     if cat and cat in d.columns:
#         grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#         if not grp.empty:
#             N = min(len(grp), 10)  # cap long lists for readability
#             top_k = grp.head(N)
#             names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
#             insights.append(
#                 random.choice([
#                     "Top {n} {cat}s by {metric}: {names}.",
#                     "Leaders on {metric} (Top {n}): {names}.",
#                     "Ranking by {metric} — Top {n}: {names}.",
#                     "Highest {metric} — Top {n}: {names}.",
#                     "Top {n} performers ({metric}): {names}.",
#                 ]).format(n=N, cat=cat, metric=y.replace("_"," "), names=names)
#             )

#             total_sum = float(grp.sum())
#             if total_sum > 0:
#                 shares = (grp / total_sum).head(N)
#                 share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
#                 insights.append(
#                     random.choice([
#                         "Share of total {metric} (Top {n}): {share}.",
#                         "Contribution split (Top {n}, {metric}): {share}.",
#                         "Within total {metric}, Top {n} shares: {share}.",
#                         "{metric} mix (Top {n}): {share}.",
#                         "Top {n} share breakdown ({metric}): {share}.",
#                     ]).format(n=N, metric=y.replace("_"," "), share=share_txt)
#                 )

#     # ---------------- FALLBACK / TOTAL ----------------
#     if not insights:
#         total = pd.to_numeric(d[y], errors="coerce").sum()
#         variations_total = [
#             "Total {metric} in the result: {val}.",
#             "Aggregate {metric}: {val}.",
#             "Combined {metric} across rows: {val}.",
#             "Overall {metric} sums to {val}.",
#             "Sum of {metric}: {val}.",
#         ]
#         insights.append(
#             random.choice(variations_total).format(
#                 metric=y.replace("_", " "), val=_format_num(total)
#             )
#         )

#     return insights[:4]  # allow up to 4 to include period/peak

# # =============================================================================
# # NEW: PAYLOAD-AWARE INSIGHTS (for your ITEMSSSSS JSON)
# # =============================================================================

# def _pct_to_str(p: Optional[float], signed: bool = True, decimals: int = 2) -> str:
#     if p is None or (isinstance(p, float) and (math.isnan(p) or math.isinf(p))):
#         return "NA"
#     pct = p * 100.0
#     s = f"{pct:.{decimals}f}%"
#     if signed and pct > 0:
#         s = "+" + s
#     return s

# def _rupees_compact(n: Optional[float]) -> str:
#     # keep it simple and neutral (no locale lib)
#     try:
#         n = float(n)
#     except Exception:
#         return "NA"
#     if abs(n) >= 1_00_00_000:   # 10M+
#         return f"₹{n/1_00_00_000:.2f}Cr"
#     if abs(n) >= 1_00_000:      # 100k+
#         return f"₹{n/1_00_000:.2f}L"
#     return f"₹{n:,.0f}"

# def _months_inclusive(start_str: str, end_str: str) -> int:
#     try:
#         s = datetime.fromisoformat(start_str[:10])
#         e = datetime.fromisoformat(end_str[:10])
#     except Exception:
#         return 0
#     return (e.year - s.year) * 12 + (e.month - s.month) + 1

# def _safe_get(d: Dict[str, Any], path: List[str], default=None):
#     cur = d
#     for key in path:
#         if isinstance(cur, dict) and key in cur:
#             cur = cur[key]
#         else:
#             return default
#     return cur

# def _calc_growth(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
#     try:
#         if curr is None or prev is None or prev == 0:
#             return None
#         return (curr - prev) / prev
#     except Exception:
#         return None

# def _calc_cagr(v0: Optional[float], vN: Optional[float], years: float) -> Optional[float]:
#     try:
#         if v0 is None or vN is None or v0 <= 0 or years <= 0:
#             return None
#         return (vN / v0) ** (1.0 / years) - 1.0
#     except Exception:
#         return None

# # ---------- per-mode insight builders with variations ----------

# def _insight_mat_compare(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # accept either payload['mat_compare']['periods'] or nested variant
#     periods: List[Dict[str, Any]] = (
#         _safe_get(payload, ["mat_compare", "periods"], [])
#         or _safe_get(payload, ["mat_compare", "mat_compare", "periods"], [])
#         or []
#     )
#     if not periods:
#         return {"bullets": ["No MAT periods available to compare."]}

#     # sort by rank if available; else keep given order
#     periods_sorted = sorted(periods, key=lambda x: x.get("rank", 9999))
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # Headline on top period
#     top = periods_sorted[0]
#     top_label = top.get("mat_label", "Latest")
#     top_val = top.get("value_sales")

#     variations_headline = [
#         "{label} value sales reached {val} (rank #1 among shown periods).",
#         "{label} comes out on top with {val} in value sales.",
#         "Highest value sales in the set: {label} at {val}.",
#         "{label} leads the comparison, posting {val} in value sales.",
#         "{label} prints the peak value sales at {val}.",
#     ]
#     bullets.append(
#         random.choice(variations_headline).format(
#             label=top_label, val=_rupees_compact(top_val)
#         )
#     )

#     # NEW: explicit MAT period windows for each label
#     period_lines = []
#     for p in periods_sorted[:3]:
#         s, e = p.get("start"), p.get("end")
#         label = p.get("mat_label", "")
#         pr = _format_period(s, e)
#         if pr:
#             period_lines.append(f"{label}: {pr}")
#     if period_lines:
#         period_variants = [
#             "Period windows — " + "; ".join(period_lines) + ".",
#             "Coverage: " + "; ".join(period_lines) + ".",
#             "Date ranges → " + "; ".join(period_lines) + ".",
#             "MAT spans: " + "; ".join(period_lines) + ".",
#             "Windows: " + "; ".join(period_lines) + ".",
#         ]
#         bullets.append(random.choice(period_variants))

#     # Pairwise growth
#     if len(periods_sorted) >= 2:
#         p1 = periods_sorted[0]
#         p2 = periods_sorted[1]
#         g_10 = _calc_growth(p1.get("value_sales"), p2.get("value_sales"))
#         if g_10 is not None:
#             variations_pair = [
#                 "{p1} vs {p2}: {g}.",
#                 "Change from {p2} to {p1}: {g}.",
#                 "Step-up {p2}→{p1}: {g}.",
#                 "{p1} relative to {p2}: {g}.",
#                 "Delta {p1} over {p2}: {g}.",
#             ]
#             bullets.append(
#                 random.choice(variations_pair).format(
#                     p1=p1.get("mat_label", "P1"),
#                     p2=p2.get("mat_label", "P2"),
#                     g=_pct_to_str(g_10),
#                 )
#             )
#             derived["growth_p1_vs_p2_pct"] = round(g_10 * 100, 6)

#     if len(periods_sorted) >= 3:
#         p2 = periods_sorted[1]
#         p3 = periods_sorted[2]
#         g_21 = _calc_growth(p2.get("value_sales"), p3.get("value_sales"))
#         if g_21 is not None:
#             variations_pair2 = [
#                 "{p2} vs {p3}: {g}.",
#                 "From {p3} to {p2}: {g}.",
#                 "Lift {p3}→{p2}: {g}.",
#                 "{p2} compared with {p3}: {g}.",
#                 "Delta {p2} over {p3}: {g}.",
#             ]
#             bullets.append(
#                 random.choice(variations_pair2).format(
#                     p2=p2.get("mat_label", "P2"),
#                     p3=p3.get("mat_label", "P3"),
#                     g=_pct_to_str(g_21),
#                 )
#             )
#             derived["growth_p2_vs_p3_pct"] = round(g_21 * 100, 6)

#         # 2-year CAGR (assuming 1 year spacing)
#         cagr = _calc_cagr(p3.get("value_sales"), periods_sorted[0].get("value_sales"), years=2.0)
#         if cagr is not None:
#             variations_cagr = [
#                 "Two-year CAGR across shown MATs: {c}.",
#                 "2Y CAGR (MAT set): {c}.",
#                 "CAGR over the last two MATs: {c}.",
#                 "Across the two-year span, CAGR is {c}.",
#                 "Two-year compounded growth: {c}.",
#             ]
#             bullets.append(random.choice(variations_cagr).format(c=_pct_to_str(cagr, signed=False)))
#             derived["cagr_2y_pct"] = round(cagr * 100, 6)

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# def _insight_yoy(payload: Dict[str, Any]) -> Dict[str, Any]:
#     yoy_items: List[Dict[str, Any]] = _safe_get(payload, ["yoy", "items"], []) or []
#     measure_type = _safe_get(payload, ["yoy", "measure_type"], "measure")
#     if not yoy_items:
#         return {"bullets": ["No YoY items available."]}

#     bullets: List[str] = []

#     # NEW: show current window (and previous if available under debug.prev_window)
#     win = payload.get("window", {}) or {}
#     curr_pr = _format_period(win.get("start"), win.get("end"))
#     dbg_prev = _safe_get(payload, ["debug", "prev_window"], {}) or {}
#     prev_pr = _format_period(dbg_prev.get("start"), dbg_prev.get("end")) if dbg_prev else None
#     if curr_pr and prev_pr:
#         window_variants = [
#             "Current window: {cur}; previous window: {prev}.",
#             "Windows → current: {cur} | previous: {prev}.",
#             "Date ranges — current: {cur}; previous: {prev}.",
#             "Coverage (cur/prev): {cur} / {prev}.",
#             "In-scope periods → {cur} vs {prev}.",
#         ]
#         bullets.append(random.choice(window_variants).format(cur=curr_pr, prev=prev_pr))
#     elif curr_pr:
#         window_variants = [
#             "Window considered: {cur}.",
#             "Period window: {cur}.",
#             "Date range: {cur}.",
#             "Coverage: {cur}.",
#             "Time span in view: {cur}.",
#         ]
#         bullets.append(random.choice(window_variants).format(cur=curr_pr))

#     # If brand present, rank by yoy_pct

#     branded = [it for it in yoy_items if "brand" in it]
#     bullets: List[str] = []

#     if branded:
#         branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)
#         N = min(len(branded), 10)
#         ranked_pairs = []
#         for i, it in enumerate(branded[:N], start=1):
#             ranked_pairs.append(f"{i}. {str(it.get('brand')).title()} ({_pct_to_str(it.get('yoy_pct', 0.0))})")
#         ranking_line = "; ".join(ranked_pairs)

#         bullets.append(
#             random.choice([
#                 "YoY ranking (Top {n}): {line}.",
#                 "Top {n} YoY movers: {line}.",
#                 "Ranked by YoY: {line}.",
#                 "YoY leaderboard (Top {n}): {line}.",
#                 "YoY order of merit (Top {n}): {line}.",
#             ]).format(n=N, line=ranking_line)
#         )

#         pos_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) > 0)
#         neg_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) < 0)
#         if pos_cnt and not neg_cnt:
#             bullets.append(random.choice([
#                 "All tracked brands are growing YoY.",
#                 "Every brand in scope shows YoY growth.",
#                 "YoY is positive across the board.",
#                 "All brands post positive YoY.",
#                 "Universal YoY growth among tracked brands.",
#             ]))
#         elif neg_cnt and not pos_cnt:
#             bullets.append(random.choice([
#                 "All tracked brands are declining YoY.",
#                 "Every brand in scope shows a YoY decline.",
#                 "YoY is negative across the board.",
#                 "All brands post YoY contraction.",
#                 "Universal YoY decline among tracked brands.",
#             ]))
#         else:
#             bullets.append(random.choice([
#                 "{p} brand(s) growing, {n} declining YoY.",
#                 "Mixed picture: {p} up and {n} down YoY.",
#                 "YoY is split — {p} positive, {n} negative.",
#                 "{p} brands up YoY; {n} down.",
#                 "Growth is uneven: {p} positive vs {n} negative YoY.",
#             ]).format(p=pos_cnt, n=neg_cnt))

#         return {"bullets": bullets}

#     # branded = [it for it in yoy_items if "brand" in it]
#     # if branded:
#     #     branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)
#     #     lead = branded[0]
#     #     lead_name = str(lead.get("brand")).title()
#     #     lead_pct = _pct_to_str(lead.get("yoy_pct", 0.0))
#     #     variations_lead = [
#     #         "{brand} leads {mt} YoY at {pct}.",
#     #         "Top YoY mover on {mt}: {brand} ({pct}).",
#     #         "{brand} shows the strongest YoY on {mt} at {pct}.",
#     #         "{brand} is ahead on {mt} YoY with {pct}.",
#     #         "Leading YoY growth ({mt}): {brand} at {pct}.",
#     #     ]
#     #     bullets.append(random.choice(variations_lead).format(brand=lead_name, mt=measure_type, pct=lead_pct))

#     #     if len(branded) >= 2:
#     #         second = branded[1]
#     #         second_name = str(second.get("brand")).title()
#     #         second_pct = _pct_to_str(second.get("yoy_pct", 0.0))
#     #         variations_second = [
#     #             "Next is {brand} at {pct}.",
#     #             "Runner-up: {brand} ({pct}).",
#     #             "Followed by {brand} at {pct}.",
#     #             "Then comes {brand} with {pct}.",
#     #             "{brand} follows at {pct}.",
#     #         ]
#     #         bullets.append(random.choice(variations_second).format(brand=second_name, pct=second_pct))

#     #     # NEW: call out #3 explicitly when present
#     #     if len(branded) >= 3:
#     #         third = branded[2]
#     #         third_name = str(third.get("brand")).title()
#     #         third_pct = _pct_to_str(third.get("yoy_pct", 0.0))
#     #         variations_third = [
#     #             "Third place: {brand} at {pct}.",
#     #             "Completing the top-3: {brand} ({pct}).",
#     #             "In third: {brand} at {pct}.",
#     #             "{brand} rounds out the top-3 with {pct}.",
#     #             "Also notable in #3: {brand} ({pct}).",
#     #         ]
#     #         bullets.append(random.choice(variations_third).format(brand=third_name, pct=third_pct))

#     #     pos_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) > 0)
#     #     neg_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) < 0)
#     #     if pos_cnt and not neg_cnt:
#     #         variations_allpos = [
#     #             "All tracked brands are growing YoY.",
#     #             "Every brand in scope shows YoY growth.",
#     #             "YoY is positive across the board.",
#     #             "All brands post positive YoY.",
#     #             "Universal YoY growth among tracked brands.",
#     #         ]
#     #         bullets.append(random.choice(variations_allpos))
#     #     elif neg_cnt and not pos_cnt:
#     #         variations_allneg = [
#     #             "All tracked brands are declining YoY.",
#     #             "Every brand in scope shows a YoY decline.",
#     #             "YoY is negative across the board.",
#     #             "All brands post YoY contraction.",
#     #             "Universal YoY decline among tracked brands.",
#     #         ]
#     #         bullets.append(random.choice(variations_allneg))
#     #     else:
#     #         variations_mix = [
#     #             "{p} brand(s) growing, {n} declining YoY.",
#     #             "Mixed picture: {p} up and {n} down YoY.",
#     #             "YoY is split — {p} positive, {n} negative.",
#     #             "{p} brands up YoY; {n} down.",
#     #             "Growth is uneven: {p} positive vs {n} negative YoY.",
#     #         ]
#     #         bullets.append(random.choice(variations_mix).format(p=pos_cnt, n=neg_cnt))
#     #     return {"bullets": bullets}

#     # # single total (no brand)
#     # g = yoy_items[0].get("yoy_pct", 0.0)
#     # variations_total = [
#     #     "YoY change is {g}.",
#     #     "Overall YoY stands at {g}.",
#     #     "Aggregate YoY movement: {g}.",
#     #     "Headline YoY shift: {g}.",
#     #     "Total YoY delta: {g}.",
#     # ]
#     # bullets.append(random.choice(variations_total).format(g=_pct_to_str(g)))
#     # return {"bullets": bullets}

# def _insight_totals(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # Handle single total in bar.items (e.g., total unit_sales for a brand)
#     bar_items = _safe_get(payload, ["bar", "items"], [])
#     measure = str(payload.get("measure", "")).lower()
#     if not isinstance(bar_items, list) or len(bar_items) != 1:
#         return {"bullets": ["No single total found."]}

#     item = bar_items[0]
#     label = item.get("label", "Total")
#     # value may live in "value" or under measure name
#     total = item.get("value", None)
#     if total is None:
#         total = item.get(measure, None)

#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # NEW: include window if present
#     win = payload.get("window", {}) or {}
#     pr = _format_period(win.get("start"), win.get("end"))
#     if pr:
#         bullets.append(random.choice([
#             "Window considered: {pr}.",
#             "Period window: {pr}.",
#             "Date range: {pr}.",
#             "Coverage: {pr}.",
#             "Time span in view: {pr}.",
#         ]).format(pr=pr))

#     if measure == "unit_sales":
#         variations_units = [
#             "{label} sold a total of {val} units in the selected period.",
#             "Total units for {label}: {val}.",
#             "{label} accumulated {val} units over the window.",
#             "Across the period, {label} reached {val} units.",
#             "Units summed for {label}: {val}.",
#         ]
#         bullets.append(random.choice(variations_units).format(label=label, val=_format_num(total)))
#     elif measure == "value_sales":
#         variations_value = [
#             "{label} value sales totaled {val} in the selected period.",
#             "Total value sales for {label}: {val}.",
#             "{label} posted {val} in value sales across the window.",
#             "Aggregate value sales for {label} come to {val}.",
#             "Cumulative value sales for {label}: {val}.",
#         ]
#         bullets.append(random.choice(variations_value).format(label=label, val=_rupees_compact(total)))
#     else:
#         variations_other = [
#             "{label} total for {metric} is {val}.",
#             "Aggregate {metric} for {label}: {val}.",
#             "{label} recorded {val} on {metric}.",
#             "Combined {metric} for {label}: {val}.",
#             "Overall {metric} ({label}): {val}.",
#         ]
#         bullets.append(random.choice(variations_other).format(label=label, metric=measure, val=_format_num(total)))

#     # optional monthly average if window present
#     start, end = win.get("start"), win.get("end")
#     months = _months_inclusive(start, end) if (start and end) else 0
#     if months > 0 and isinstance(total, (int, float)):
#         avg = total / months
#         if measure == "unit_sales":
#             variations_avg = [
#                 "~{avg} units per month on average.",
#                 "Monthly run-rate ~{avg} units.",
#                 "That’s roughly {avg} units/month.",
#                 "Avg monthly volume ~{avg} units.",
#                 "Per-month average is ~{avg} units.",
#             ]
#             bullets.append(random.choice(variations_avg).format(avg=_format_num(avg)))
#         elif measure == "value_sales":
#             variations_avg_val = [
#                 "~{avg} per month on average.",
#                 "Monthly run-rate ~{avg}.",
#                 "That’s roughly {avg} each month.",
#                 "Avg monthly value ~{avg}.",
#                 "Per-month average is ~{avg}.",
#             ]
#             bullets.append(random.choice(variations_avg_val).format(avg=_rupees_compact(avg)))
#         derived["avg_per_month"] = avg
#         derived["months"] = months

#     out = {"bullets": bullets}
#     if derived:
#         out["derived"] = derived
#     return out

# def _insight_trend_line(payload: Dict[str, Any]) -> Dict[str, Any]:
#     trend = payload.get("trend", {})
#     overall = trend.get("overall", {})
#     by_brand = trend.get("by_brand", [])
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # NEW: include window if present
#     win = payload.get("window", {}) or {}
#     pr = _format_period(win.get("start"), win.get("end"))
#     if pr:
#         bullets.append(random.choice([
#             "Window considered: {pr}.",
#             "Period window: {pr}.",
#             "Date range: {pr}.",
#             "Coverage: {pr}.",
#             "Time span in view: {pr}.",
#         ]).format(pr=pr))

#     # Overall peak/trough messaging (+ explicit peak month callout)
#     omax = overall.get("max", {})
#     omin = overall.get("min", {})
#     if "value" in omax and "value" in omin and omax.get("value") and omin.get("value"):
#         # explicit peak month callout
#         bullets.append(random.choice([
#             "Peak occurs in {peak} at {val}.",
#             "Highest point is {peak} ({val}).",
#             "Series tops out in {peak} with {val}.",
#             "Peak month: {peak} ({val}).",
#             "The high is registered in {peak}: {val}.",
#         ]).format(peak=omax.get('label','peak'), val=_format_num(omax.get('value'))))

#         # keep the original peak vs trough sentence too (varied)
#         bullets.append(random.choice([
#             "Overall peak in {peak} and trough in {trough}.",
#             "The series peaks around {peak} and bottoms near {trough}.",
#             "Top reading: {peak}; lowest: {trough}.",
#             "Peak appears in {peak}, while the trough is {trough}.",
#             "High watermark at {peak}; low at {trough}.",
#         ]).format(peak=omax.get('label','peak'), trough=omin.get('label','trough')))

#         drop = (omax["value"] - omin["value"]) / omax["value"] if omax["value"] else None
#         if drop is not None:
#             derived["overall_peak_to_trough_drop_pct"] = round(drop * 100, 6)

#     # Brand-wise peak→trough ranges
#     ranges: List[str] = []
#     for b in by_brand or []:
#         name = b.get("brand", "")
#         vmax = _safe_get(b, ["max", "value"], None)
#         vmin = _safe_get(b, ["min", "value"], None)
#         if vmax and vmin and vmax > 0:
#             drop = (vmax - vmin) / vmax
#             derived[f"{name.lower()}_peak_to_trough_drop_pct"] = round(drop * 100, 6)
#             ranges.append(f"{name} ~{int(round(drop*100))}%")

#     if ranges:
#         variations_ranges = [
#             "Peak→trough range (approx): {list}.",
#             "Approximate drawdowns: {list}.",
#             "Peak-to-bottom swings: {list}.",
#             "Volatility snapshot (peak→trough): {list}.",
#             "Range from highs to lows: {list}.",
#         ]
#         bullets.append(random.choice(variations_ranges).format(list=", ".join(ranges)))

#     # Seasonality hint if multiple brands share trough label
#     trough_labels = [b.get("min", {}).get("label") for b in (by_brand or []) if b.get("min")]
#     if trough_labels:
#         common = max(set(trough_labels), key=trough_labels.count)
#         if trough_labels.count(common) >= 2:
#             variations_season = [
#                 "Multiple brands trough around {label}, hinting at seasonality.",
#                 "Common trough near {label} — seasonal pattern likely.",
#                 "Several brands dip around {label}, indicating seasonality.",
#                 "Shared low point around {label} suggests seasonal effects.",
#                 "Trough clustering at {label} points to seasonality.",
#             ]
#             bullets.append(random.choice(variations_season).format(label=common))

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# # ---------- public router ----------

# def attach_insights(payload: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Appends an 'insights' block to your ITEMSSSSS payload without changing existing keys.
#     Supports:
#       - MAT_COMPARE (payload['mat_compare'])
#       - YOY / YTD_YOY (payload['yoy'])
#       - LINE trend (payload['trend'])
#       - Totals (single BAR item, e.g., total unit_sales)
#     """
#     try:
#         mode = str(payload.get("mode", "")).upper()

#         insights_block: Optional[Dict[str, Any]] = None

#         # Prefer explicit structures
#         if mode == "MAT_COMPARE" or "mat_compare" in payload:
#             insights_block = _insight_mat_compare(payload)

#         if insights_block is None and "trend" in payload:
#             insights_block = _insight_trend_line(payload)

#         if insights_block is None and "yoy" in payload:
#             insights_block = _insight_yoy(payload)

#         if insights_block is None and mode == "BAR":
#             bar_items = _safe_get(payload, ["bar", "items"], [])
#             if isinstance(bar_items, list) and len(bar_items) == 1:
#                 insights_block = _insight_totals(payload)

#         if insights_block is None:
#             insights_block = {"bullets": ["No insight template matched this response."]}

#         out = dict(payload)
#         out["insights"] = insights_block
#         return out

#     except Exception as e:
#         out = dict(payload)
#         out["insights"] = {"bullets": [f"Insight generation failed: {e}"]}
#         return out

# # =============================================================================
# # OPTIONAL: quick manual test
# # =============================================================================
# if __name__ == "__main__":
#     # random.seed(42)  # uncomment for deterministic phrasing while testing
#     sample = {
#         "mode": "MAT_COMPARE",
#         "measure": "value_sales",
#         "mat_compare": {
#             "periods": [
#                 {"mat_label": "MAT 2025", "value_sales": 56315997.11, "rank": 1, "start": "2024-10-01", "end": "2025-09-30"},
#                 {"mat_label": "MAT 2024", "value_sales": 55090425.83, "rank": 2, "start": "2023-10-01", "end": "2024-09-30"},
#                 {"mat_label": "MAT 2023", "value_sales": 54262187.76, "rank": 3, "start": "2022-10-01", "end": "2023-09-30"},
#             ]
#         }
#     }
#     print(attach_insights(sample))


#Top n brands insights .Code now shows peaks and troughs for the line chart, various text descriptions for the MAT comparison , still mat and ytd queries without yoy are not supported.








# # backend/insights.py

# from __future__ import annotations

# import math
# import random
# from datetime import datetime
# from typing import Dict, Any, List, Optional, Tuple

# import numpy as np
# import pandas as pd

# CAT_CANDS = ["brand", "category", "market", "channel", "segment", "manufacturer"]

# # =============================================================================
# # EXISTING HELPERS (kept as-is)
# # =============================================================================

# def _first_numeric(df: pd.DataFrame) -> str | None:
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     return None

# def _pick_measure_col(df: pd.DataFrame, meta: dict) -> str | None:
#     # Prefer meta.measure if it exists and is numeric
#     m = (meta or {}).get("measure")
#     if isinstance(m, str) and m in df.columns and pd.api.types.is_numeric_dtype(df[m]):
#         return m
#     # Else try common names
#     for cand in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if cand in df.columns and pd.api.types.is_numeric_dtype(df[cand]):
#             return cand
#     # Else first numeric
#     return _first_numeric(df)

# def _pick_cat_dim(df: pd.DataFrame) -> str | None:
#     for c in CAT_CANDS:
#         if c in df.columns:
#             return c
#     return None

# def _format_num(x: float) -> str:
#     try:
#         if abs(x) >= 1_000_000:
#             return f"{x/1_000_000:.1f}M"
#         if abs(x) >= 1_000:
#             return f"{x/1_000:.1f}K"
#         return f"{x:.0f}"
#     except Exception:
#         return str(x)

# def _format_pct(x: float) -> str:
#     try:
#         return f"{x*100:.1f}%"
#     except Exception:
#         return "NA"

# def _format_period(start: Optional[str], end: Optional[str]) -> Optional[str]:
#     if not start or not end:
#         return None
#     # Keep ISO compact; consistent with your API
#     try:
#         s = datetime.fromisoformat(start[:10]).date().isoformat()
#         e = datetime.fromisoformat(end[:10]).date().isoformat()
#         return f"{s} → {e}"
#     except Exception:
#         return f"{start} → {end}"

# def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Heuristic, lightweight insights that never fail silently.
#     Works for table/bar/line; time or no time; any dim.
#     """
#     insights: list[str] = []

#     # --- guardrails ---
#     if df is None or not isinstance(df, pd.DataFrame) or df.empty:
#         return ["No data to analyze."]

#     # Choose measure (y)s
#     y = _pick_measure_col(df, meta)
#     if y is None:
#         insights.append("No numeric measure returned, so only structural results are shown.")
#         return insights

#     # Pick a categorical dim if present
#     cat = _pick_cat_dim(df)

#     # Detect time
#     has_date = "date" in df.columns
#     has_month = "month_year" in df.columns or "month" in df.columns

#     # Normalize copy for safe ops
#     d = df.copy()

#     # ---------------- TIME-SERIES INSIGHTS ----------------
#     if has_month or has_date:
#         # prefer month_year string for readability
#         if has_date:
#             try:
#                 d["__dt"] = pd.to_datetime(d["date"])
#             except Exception:
#                 d["__dt"] = pd.to_datetime(d["date"], errors="coerce")
#         else:
#             # build a sortable month from month_year or month
#             month_col = "month_year" if "month_year" in d.columns else "month"
#             parsed = pd.to_datetime(d[month_col], errors="coerce")
#             d["__dt"] = parsed.dt.to_period("M").dt.to_timestamp()

#         # If categorical exists (e.g., brand lines), focus on top line at the end
#         if cat and cat in d.columns:
#             # last month in the result
#             last_t = d["__dt"].max()
#             cur = d[d["__dt"] == last_t]

#             # If multiple brands, find top latest and compare to previous point
#             grp = cur.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#             if not grp.empty:
#                 top_brand = grp.index[0]
#                 top_val = grp.iloc[0]

#                 # Compute previous value for that brand (prev timestamp)
#                 prev_t = d["__dt"].sort_values().unique()
#                 prev_t = prev_t[-2] if len(prev_t) >= 2 else None

#                 if prev_t is not None:
#                     prev_val = d[(d[cat] == top_brand) & (d["__dt"] == prev_t)][y].sum()
#                     if pd.notna(prev_val) and prev_val != 0:
#                         chg = (top_val - prev_val) / prev_val
#                         dir_word = "up" if chg >= 0 else "down"
#                         variations = [
#                             "{brand} leads the latest with {val} {metric} ({dir} {chg} vs previous).",
#                             "Most recent leader: {brand} at {val} {metric} ({dir} {chg} vs last point).",
#                             "{brand} tops the newest period at {val} {metric} ({dir} {chg} vs prior).",
#                             "Latest snapshot: {brand} is #1 with {val} {metric} ({dir} {chg} m/m).",
#                             "{brand} holds the lead currently — {val} {metric} ({dir} {chg} vs prev).",
#                         ]
#                         insights.append(
#                             random.choice(variations).format(
#                                 brand=top_brand,
#                                 val=_format_num(top_val),
#                                 metric=y.replace("_", " "),
#                                 dir=dir_word,
#                                 chg=_format_pct(abs(chg)),
#                             )
#                         )

#                 # Gap to #2 at the last point
#                 if len(grp) >= 2:
#                     gap = grp.iloc[0] - grp.iloc[1]
#                     variations_gap = [
#                         "Gap to #{rank2} {b2}: {gap} on the latest point.",
#                         "Lead over {b2} stands at {gap} (most recent period).",
#                         "Current spread vs {b2}: {gap}.",
#                         "Latest margin vs {b2}: {gap}.",
#                         "The distance to {b2} right now is {gap}.",
#                     ]
#                     insights.append(
#                         random.choice(variations_gap).format(
#                             rank2=2, b2=grp.index[1], gap=_format_num(gap)
#                         )
#                     )
#                 # NEW: explicitly mention #3 when present
#                 if len(grp) >= 3:
#                     third_name = grp.index[2]
#                     third_val = grp.iloc[2]
#                     third_variants = [
#                         "In third place: {b3} at {v3}.",
#                         "Completing the top-3 is {b3} with {v3}.",
#                         "Third spot: {b3} ({v3}).",
#                         "{b3} rounds out the top-3 at {v3}.",
#                         "Also noteworthy at #3: {b3} with {v3}.",
#                     ]
#                     insights.append(
#                         random.choice(third_variants).format(
#                             b3=third_name, v3=_format_num(third_val)
#                         )
#                     )
#         else:
#             # No categorical: describe overall trend last vs prev
#             last_t = d["__dt"].max()
#             prev_times = d["__dt"].sort_values().unique()
#             prev_t = prev_times[-2] if len(prev_times) >= 2 else None
#             last_val = d.loc[d["__dt"] == last_t, y].sum()
#             if prev_t is not None:
#                 prev_val = d.loc[d["__dt"] == prev_t, y].sum()
#                 if pd.notna(prev_val) and prev_val != 0:
#                     chg = (last_val - prev_val) / prev_val
#                     dir_word = "up" if chg >= 0 else "down"
#                     variations_line = [
#                         "Latest {metric}: {val}; {dir} {chg} vs previous.",
#                         "{metric} now at {val} — {dir} {chg} vs last period.",
#                         "Most recent {metric} is {val} ({dir} {chg} m/m).",
#                         "{metric} prints {val} in the latest period ({dir} {chg} vs prior).",
#                         "Current {metric} of {val} is {dir} {chg} against previous.",
#                     ]
#                     insights.append(
#                         random.choice(variations_line).format(
#                             metric=y.replace("_", " "),
#                             val=_format_num(last_val),
#                             dir=dir_word,
#                             chg=_format_pct(abs(chg)),
#                         )
#                     )

#         # NEW: peak month callout (overall)
#         try:
#             # Aggregate overall by month and pick the peak
#             by_month = d.groupby(d["__dt"])[y].sum().sort_index()
#             if not by_month.empty:
#                 peak_t = by_month.idxmax()
#                 peak_v = by_month.max()
#                 peak_label = peak_t.strftime("%b %Y")
#                 peak_variants = [
#                     "Peak {metric} occurs in {label} at {val}.",
#                     "Highest {metric}: {label} ({val}).",
#                     "The series peaks in {label} with {val}.",
#                     "Top month is {label} at {val} on {metric}.",
#                     "{label} marks the peak for {metric} ({val}).",
#                 ]
#                 insights.append(
#                     random.choice(peak_variants).format(
#                         metric=y.replace("_", " "), label=peak_label, val=_format_num(peak_v)
#                     )
#                 )
#         except Exception:
#             pass

#         # NEW: show period range when present in meta
#         win = (meta or {}).get("window") or {}
#         pr = _format_period(win.get("start"), win.get("end"))
#         if pr:
#             period_variants = [
#                 "Period window: {pr}.",
#                 "Window considered: {pr}.",
#                 "Date range: {pr}.",
#                 "Coverage: {pr}.",
#                 "Time span in view: {pr}.",
#             ]
#             insights.append(random.choice(period_variants).format(pr=pr))

#     # ---------------- CATEGORICAL INSIGHTS ----------------
#     # if cat and cat in d.columns:
#     #     grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#     #     if not grp.empty:
#     #         top_k = grp.head(3)
#     #         names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
#     #         variations_top = [
#     #             "Top {cat}s by {metric}: {names}.",
#     #             "Leaders on {metric}: {names}.",
#     #             "Ranking by {metric}: {names}.",
#     #             "Highest {metric}: {names}.",
#     #             "Top performers ({metric}): {names}.",
#     #         ]
#     #         insights.append(
#     #             random.choice(variations_top).format(
#     #                 cat=cat, metric=y.replace("_", " "), names=names
#     #             )
#     #         )
#     #         if grp.sum() > 0:
#     #             shares = (grp / grp.sum()).head(3)
#     #             share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
#     #             variations_share = [
#     #                 "Share of total {metric}: {share}.",
#     #                 "Contribution split ({metric}): {share}.",
#     #                 "Within shown total {metric}, shares are: {share}.",
#     #                 "{metric} mix: {share}.",
#     #                 "Top-3 share breakdown ({metric}): {share}.",
#     #             ]
#     #             insights.append(
#     #                 random.choice(variations_share).format(
#     #                     metric=y.replace("_", " "), share=share_txt
#     #                 )
#     #             )

# # ---------------- CATEGORICAL INSIGHTS ----------------
#     if cat and cat in d.columns:
#         grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
#         if not grp.empty:
#             N = min(len(grp), 10)  # cap long lists for readability
#             top_k = grp.head(N)
#             names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
#             insights.append(
#                 random.choice([
#                     "Top {n} {cat}s by {metric}: {names}.",
#                     "Leaders on {metric} (Top {n}): {names}.",
#                     "Ranking by {metric} — Top {n}: {names}.",
#                     "Highest {metric} — Top {n}: {names}.",
#                     "Top {n} performers ({metric}): {names}.",
#                 ]).format(n=N, cat=cat, metric=y.replace("_"," "), names=names)
#             )

#             total_sum = float(grp.sum())
#             if total_sum > 0:
#                 shares = (grp / total_sum).head(N)
#                 share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
#                 insights.append(
#                     random.choice([
#                         "Share of total {metric} (Top {n}): {share}.",
#                         "Contribution split (Top {n}, {metric}): {share}.",
#                         "Within total {metric}, Top {n} shares: {share}.",
#                         "{metric} mix (Top {n}): {share}.",
#                         "Top {n} share breakdown ({metric}): {share}.",
#                     ]).format(n=N, metric=y.replace("_"," "), share=share_txt)
#                 )

#     # ---------------- FALLBACK / TOTAL ----------------
#     if not insights:
#         total = pd.to_numeric(d[y], errors="coerce").sum()
#         variations_total = [
#             "Total {metric} in the result: {val}.",
#             "Aggregate {metric}: {val}.",
#             "Combined {metric} across rows: {val}.",
#             "Overall {metric} sums to {val}.",
#             "Sum of {metric}: {val}.",
#         ]
#         insights.append(
#             random.choice(variations_total).format(
#                 metric=y.replace("_", " "), val=_format_num(total)
#             )
#         )

#     return insights[:4]  # allow up to 4 to include period/peak

# # =============================================================================
# # NEW: PAYLOAD-AWARE INSIGHTS (for your ITEMSSSSS JSON)
# # =============================================================================

# def _pct_to_str(p: Optional[float], signed: bool = True, decimals: int = 2) -> str:
#     if p is None or (isinstance(p, float) and (math.isnan(p) or math.isinf(p))):
#         return "NA"
#     pct = p * 100.0
#     s = f"{pct:.{decimals}f}%"
#     if signed and pct > 0:
#         s = "+" + s
#     return s

# def _rupees_compact(n: Optional[float]) -> str:
#     # keep it simple and neutral (no locale lib)
#     try:
#         n = float(n)
#     except Exception:
#         return "NA"
#     if abs(n) >= 1_00_00_000:   # 10M+
#         return f"₹{n/1_00_00_000:.2f}Cr"
#     if abs(n) >= 1_00_000:      # 100k+
#         return f"₹{n/1_00_000:.2f}L"
#     return f"₹{n:,.0f}"

# def _months_inclusive(start_str: str, end_str: str) -> int:
#     try:
#         s = datetime.fromisoformat(start_str[:10])
#         e = datetime.fromisoformat(end_str[:10])
#     except Exception:
#         return 0
#     return (e.year - s.year) * 12 + (e.month - s.month) + 1

# def _safe_get(d: Dict[str, Any], path: List[str], default=None):
#     cur = d
#     for key in path:
#         if isinstance(cur, dict) and key in cur:
#             cur = cur[key]
#         else:
#             return default
#     return cur

# def _calc_growth(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
#     try:
#         if curr is None or prev is None or prev == 0:
#             return None
#         return (curr - prev) / prev
#     except Exception:
#         return None

# def _calc_cagr(v0: Optional[float], vN: Optional[float], years: float) -> Optional[float]:
#     try:
#         if v0 is None or vN is None or v0 <= 0 or years <= 0:
#             return None
#         return (vN / v0) ** (1.0 / years) - 1.0
#     except Exception:
#         return None

# # ---------- per-mode insight builders with variations ----------

# def _insight_mat_compare(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # accept either payload['mat_compare']['periods'] or nested variant
#     periods: List[Dict[str, Any]] = (
#         _safe_get(payload, ["mat_compare", "periods"], [])
#         or _safe_get(payload, ["mat_compare", "mat_compare", "periods"], [])
#         or []
#     )
#     if not periods:
#         return {"bullets": ["No MAT periods available to compare."]}

#     # sort by rank if available; else keep given order
#     periods_sorted = sorted(periods, key=lambda x: x.get("rank", 9999))
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # Headline on top period
#     top = periods_sorted[0]
#     top_label = top.get("mat_label", "Latest")
#     top_val = top.get("value_sales")

#     variations_headline = [
#         "{label} value sales reached {val} (rank #1 among shown periods).",
#         "{label} comes out on top with {val} in value sales.",
#         "Highest value sales in the set: {label} at {val}.",
#         "{label} leads the comparison, posting {val} in value sales.",
#         "{label} prints the peak value sales at {val}.",
#     ]
#     bullets.append(
#         random.choice(variations_headline).format(
#             label=top_label, val=_rupees_compact(top_val)
#         )
#     )

#     # NEW: explicit MAT period windows for each label
#     period_lines = []
#     for p in periods_sorted[:3]:
#         s, e = p.get("start"), p.get("end")
#         label = p.get("mat_label", "")
#         pr = _format_period(s, e)
#         if pr:
#             period_lines.append(f"{label}: {pr}")
#     if period_lines:
#         period_variants = [
#             "Period windows — " + "; ".join(period_lines) + ".",
#             "Coverage: " + "; ".join(period_lines) + ".",
#             "Date ranges → " + "; ".join(period_lines) + ".",
#             "MAT spans: " + "; ".join(period_lines) + ".",
#             "Windows: " + "; ".join(period_lines) + ".",
#         ]
#         bullets.append(random.choice(period_variants))

#     # Pairwise growth
#     if len(periods_sorted) >= 2:
#         p1 = periods_sorted[0]
#         p2 = periods_sorted[1]
#         g_10 = _calc_growth(p1.get("value_sales"), p2.get("value_sales"))
#         if g_10 is not None:
#             variations_pair = [
#                 "{p1} vs {p2}: {g}.",
#                 "Change from {p2} to {p1}: {g}.",
#                 "Step-up {p2}→{p1}: {g}.",
#                 "{p1} relative to {p2}: {g}.",
#                 "Delta {p1} over {p2}: {g}.",
#             ]
#             bullets.append(
#                 random.choice(variations_pair).format(
#                     p1=p1.get("mat_label", "P1"),
#                     p2=p2.get("mat_label", "P2"),
#                     g=_pct_to_str(g_10),
#                 )
#             )
#             derived["growth_p1_vs_p2_pct"] = round(g_10 * 100, 6)

#     if len(periods_sorted) >= 3:
#         p2 = periods_sorted[1]
#         p3 = periods_sorted[2]
#         g_21 = _calc_growth(p2.get("value_sales"), p3.get("value_sales"))
#         if g_21 is not None:
#             variations_pair2 = [
#                 "{p2} vs {p3}: {g}.",
#                 "From {p3} to {p2}: {g}.",
#                 "Lift {p3}→{p2}: {g}.",
#                 "{p2} compared with {p3}: {g}.",
#                 "Delta {p2} over {p3}: {g}.",
#             ]
#             bullets.append(
#                 random.choice(variations_pair2).format(
#                     p2=p2.get("mat_label", "P2"),
#                     p3=p3.get("mat_label", "P3"),
#                     g=_pct_to_str(g_21),
#                 )
#             )
#             derived["growth_p2_vs_p3_pct"] = round(g_21 * 100, 6)

#         # 2-year CAGR (assuming 1 year spacing)
#         cagr = _calc_cagr(p3.get("value_sales"), periods_sorted[0].get("value_sales"), years=2.0)
#         if cagr is not None:
#             variations_cagr = [
#                 "Two-year CAGR across shown MATs: {c}.",
#                 "2Y CAGR (MAT set): {c}.",
#                 "CAGR over the last two MATs: {c}.",
#                 "Across the two-year span, CAGR is {c}.",
#                 "Two-year compounded growth: {c}.",
#             ]
#             bullets.append(random.choice(variations_cagr).format(c=_pct_to_str(cagr, signed=False)))
#             derived["cagr_2y_pct"] = round(cagr * 100, 6)

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# import random

# def _insight_yoy(payload: Dict[str, Any]) -> Dict[str, Any]:
#     yoy_items: List[Dict[str, Any]] = _safe_get(payload, ["yoy", "items"], []) or []
#     measure_type = _safe_get(payload, ["yoy", "measure_type"], "measure")
#     if not yoy_items:
#         return {"bullets": ["No YoY items available."]}

#     branded = [it for it in yoy_items if "brand" in it]
#     bullets: List[str] = []

#     def _fmt_by_mt(x: Optional[float]) -> str:
#         if x is None:
#             return "NA"
#         return _rupees_compact(x) if str(measure_type).lower().startswith("value") else _format_num(x)

#     if branded:
#         branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)

#         # -------- Top-N summary line --------
#         N = min(len(branded), 10)
#         ranked_pairs = []
#         for i, it in enumerate(branded[:N], start=1):
#             ranked_pairs.append(f"{i}. {str(it.get('brand')).title()} ({_pct_to_str(it.get('yoy_pct', 0.0))})")

#         bullets.append(
#             random.choice([
#                 "Here’s how the top {n} brands stack up YoY: {line}.",
#                 "Looking at YoY growth, the ranking is: {line}.",
#                 "In YoY terms, the top {n} players are: {line}.",
#                 "The YoY leaderboard (Top {n}) looks like this: {line}.",
#                 "Here are the Top {n} brands by YoY change: {line}.",
#             ]).format(n=N, line="; ".join(ranked_pairs))
#         )

#         # -------- Per-rank commentary (more natural tone) --------
#         yoy_vals = [it.get("yoy_pct") for it in branded if isinstance(it.get("yoy_pct"), (int, float))]
#         avg_yoy = np.mean(yoy_vals) if yoy_vals else None

#         K = min(N, 4)
#         for i in range(K):
#             it = branded[i]
#             name = str(it.get("brand")).title()
#             pct = _pct_to_str(it.get("yoy_pct", 0.0))
#             curr = it.get("curr")
#             prev = it.get("prev")
#             delta = (curr - prev) if (isinstance(curr, (int, float)) and isinstance(prev, (int, float))) else None

#             gap_to_prev_rank = None
#             if i == 0 and N >= 2:
#                 gap_to_prev_rank = (branded[0].get("yoy_pct", 0.0) - branded[1].get("yoy_pct", 0.0))
#             elif i > 0:
#                 gap_to_prev_rank = (branded[i].get("yoy_pct", 0.0) - branded[i-1].get("yoy_pct", 0.0))

#             # Build context
#             ctx_parts = []
#             if i == 0 and gap_to_prev_rank is not None:
#                 ctx_parts.append(f"leading by { _pct_to_str(gap_to_prev_rank, signed=True) } over the next brand")
#             elif i > 0 and gap_to_prev_rank is not None:
#                 ctx_parts.append(f"{ _pct_to_str(gap_to_prev_rank, signed=True) } compared to #{i}")

#             if delta is not None:
#                 ctx_parts.append(f"with a net change of {_fmt_by_mt(delta)}")

#             if avg_yoy is not None:
#                 diff_vs_avg = (it.get("yoy_pct", 0.0) - avg_yoy)
#                 if diff_vs_avg >= 0:
#                     ctx_parts.append(f"outperforming the average ({_pct_to_str(avg_yoy, signed=False)})")
#                 else:
#                     ctx_parts.append(f"lagging the average ({_pct_to_str(avg_yoy, signed=False)})")

#             ctx = ", ".join(ctx_parts)

#             per_rank_variants = [
#                 f"{name} holds #{i+1} with {pct}, {ctx}.",
#                 f"Ranked #{i+1}, {name} shows {pct} YoY, {ctx}.",
#                 f"{name} comes in at #{i+1} ({pct}), {ctx}.",
#                 f"At #{i+1}, {name} posts {pct}, {ctx}.",
#                 f"{name} (#{i+1}) records {pct} YoY, {ctx}.",
#             ]
#             bullets.append(random.choice(per_rank_variants))

#         # -------- Overall summary --------
#         pos_cnt = sum(1 for x in branded if (x.get("yoy_pct") or 0) > 0)
#         neg_cnt = sum(1 for x in branded if (x.get("yoy_pct") or 0) < 0)
#         if pos_cnt and not neg_cnt:
#             bullets.append(random.choice([
#                 "Interestingly, every brand tracked here is in growth mode.",
#                 "All brands are enjoying positive YoY momentum.",
#                 "The entire set is growing year-on-year — no declines spotted.",
#             ]))
#         elif neg_cnt and not pos_cnt:
#             bullets.append(random.choice([
#                 "Unfortunately, all brands in this cut are shrinking YoY.",
#                 "Every tracked brand shows a year-on-year decline.",
#                 "No growth stories here — the whole group is down YoY.",
#             ]))
#         else:
#             bullets.append(random.choice([
#                 f"A mixed picture: {pos_cnt} brands are growing while {neg_cnt} are slipping back.",
#                 f"Split performance — {pos_cnt} in the green, {neg_cnt} in decline.",
#                 f"Growth is uneven: {pos_cnt} brands rising and {neg_cnt} falling YoY.",
#             ]))

#         return {"bullets": bullets}

#     # fallback (no brand dim)
#     g = yoy_items[0].get("yoy_pct", 0.0)
#     bullets.append(f"Overall YoY change is { _pct_to_str(g) } for this slice.")
#     return {"bullets": bullets}


#     # branded = [it for it in yoy_items if "brand" in it]
#     # if branded:
#     #     branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)
#     #     lead = branded[0]
#     #     lead_name = str(lead.get("brand")).title()
#     #     lead_pct = _pct_to_str(lead.get("yoy_pct", 0.0))
#     #     variations_lead = [
#     #         "{brand} leads {mt} YoY at {pct}.",
#     #         "Top YoY mover on {mt}: {brand} ({pct}).",
#     #         "{brand} shows the strongest YoY on {mt} at {pct}.",
#     #         "{brand} is ahead on {mt} YoY with {pct}.",
#     #         "Leading YoY growth ({mt}): {brand} at {pct}.",
#     #     ]
#     #     bullets.append(random.choice(variations_lead).format(brand=lead_name, mt=measure_type, pct=lead_pct))

#     #     if len(branded) >= 2:
#     #         second = branded[1]
#     #         second_name = str(second.get("brand")).title()
#     #         second_pct = _pct_to_str(second.get("yoy_pct", 0.0))
#     #         variations_second = [
#     #             "Next is {brand} at {pct}.",
#     #             "Runner-up: {brand} ({pct}).",
#     #             "Followed by {brand} at {pct}.",
#     #             "Then comes {brand} with {pct}.",
#     #             "{brand} follows at {pct}.",
#     #         ]
#     #         bullets.append(random.choice(variations_second).format(brand=second_name, pct=second_pct))

#     #     # NEW: call out #3 explicitly when present
#     #     if len(branded) >= 3:
#     #         third = branded[2]
#     #         third_name = str(third.get("brand")).title()
#     #         third_pct = _pct_to_str(third.get("yoy_pct", 0.0))
#     #         variations_third = [
#     #             "Third place: {brand} at {pct}.",
#     #             "Completing the top-3: {brand} ({pct}).",
#     #             "In third: {brand} at {pct}.",
#     #             "{brand} rounds out the top-3 with {pct}.",
#     #             "Also notable in #3: {brand} ({pct}).",
#     #         ]
#     #         bullets.append(random.choice(variations_third).format(brand=third_name, pct=third_pct))

#     #     pos_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) > 0)
#     #     neg_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) < 0)
#     #     if pos_cnt and not neg_cnt:
#     #         variations_allpos = [
#     #             "All tracked brands are growing YoY.",
#     #             "Every brand in scope shows YoY growth.",
#     #             "YoY is positive across the board.",
#     #             "All brands post positive YoY.",
#     #             "Universal YoY growth among tracked brands.",
#     #         ]
#     #         bullets.append(random.choice(variations_allpos))
#     #     elif neg_cnt and not pos_cnt:
#     #         variations_allneg = [
#     #             "All tracked brands are declining YoY.",
#     #             "Every brand in scope shows a YoY decline.",
#     #             "YoY is negative across the board.",
#     #             "All brands post YoY contraction.",
#     #             "Universal YoY decline among tracked brands.",
#     #         ]
#     #         bullets.append(random.choice(variations_allneg))
#     #     else:
#     #         variations_mix = [
#     #             "{p} brand(s) growing, {n} declining YoY.",
#     #             "Mixed picture: {p} up and {n} down YoY.",
#     #             "YoY is split — {p} positive, {n} negative.",
#     #             "{p} brands up YoY; {n} down.",
#     #             "Growth is uneven: {p} positive vs {n} negative YoY.",
#     #         ]
#     #         bullets.append(random.choice(variations_mix).format(p=pos_cnt, n=neg_cnt))
#     #     return {"bullets": bullets}

#     # # single total (no brand)
#     # g = yoy_items[0].get("yoy_pct", 0.0)
#     # variations_total = [
#     #     "YoY change is {g}.",
#     #     "Overall YoY stands at {g}.",
#     #     "Aggregate YoY movement: {g}.",
#     #     "Headline YoY shift: {g}.",
#     #     "Total YoY delta: {g}.",
#     # ]
#     # bullets.append(random.choice(variations_total).format(g=_pct_to_str(g)))
#     # return {"bullets": bullets}

# def _insight_totals(payload: Dict[str, Any]) -> Dict[str, Any]:
#     # Handle single total in bar.items (e.g., total unit_sales for a brand)
#     bar_items = _safe_get(payload, ["bar", "items"], [])
#     measure = str(payload.get("measure", "")).lower()
#     if not isinstance(bar_items, list) or len(bar_items) != 1:
#         return {"bullets": ["No single total found."]}

#     item = bar_items[0]
#     label = item.get("label", "Total")
#     # value may live in "value" or under measure name
#     total = item.get("value", None)
#     if total is None:
#         total = item.get(measure, None)

#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # NEW: include window if present
#     win = payload.get("window", {}) or {}
#     pr = _format_period(win.get("start"), win.get("end"))
#     if pr:
#         bullets.append(random.choice([
#             "Window considered: {pr}.",
#             "Period window: {pr}.",
#             "Date range: {pr}.",
#             "Coverage: {pr}.",
#             "Time span in view: {pr}.",
#         ]).format(pr=pr))

#     if measure == "unit_sales":
#         variations_units = [
#             "{label} sold a total of {val} units in the selected period.",
#             "Total units for {label}: {val}.",
#             "{label} accumulated {val} units over the window.",
#             "Across the period, {label} reached {val} units.",
#             "Units summed for {label}: {val}.",
#         ]
#         bullets.append(random.choice(variations_units).format(label=label, val=_format_num(total)))
#     elif measure == "value_sales":
#         variations_value = [
#             "{label} value sales totaled {val} in the selected period.",
#             "Total value sales for {label}: {val}.",
#             "{label} posted {val} in value sales across the window.",
#             "Aggregate value sales for {label} come to {val}.",
#             "Cumulative value sales for {label}: {val}.",
#         ]
#         bullets.append(random.choice(variations_value).format(label=label, val=_rupees_compact(total)))
#     else:
#         variations_other = [
#             "{label} total for {metric} is {val}.",
#             "Aggregate {metric} for {label}: {val}.",
#             "{label} recorded {val} on {metric}.",
#             "Combined {metric} for {label}: {val}.",
#             "Overall {metric} ({label}): {val}.",
#         ]
#         bullets.append(random.choice(variations_other).format(label=label, metric=measure, val=_format_num(total)))

#     # optional monthly average if window present
#     start, end = win.get("start"), win.get("end")
#     months = _months_inclusive(start, end) if (start and end) else 0
#     if months > 0 and isinstance(total, (int, float)):
#         avg = total / months
#         if measure == "unit_sales":
#             variations_avg = [
#                 "~{avg} units per month on average.",
#                 "Monthly run-rate ~{avg} units.",
#                 "That’s roughly {avg} units/month.",
#                 "Avg monthly volume ~{avg} units.",
#                 "Per-month average is ~{avg} units.",
#             ]
#             bullets.append(random.choice(variations_avg).format(avg=_format_num(avg)))
#         elif measure == "value_sales":
#             variations_avg_val = [
#                 "~{avg} per month on average.",
#                 "Monthly run-rate ~{avg}.",
#                 "That’s roughly {avg} each month.",
#                 "Avg monthly value ~{avg}.",
#                 "Per-month average is ~{avg}.",
#             ]
#             bullets.append(random.choice(variations_avg_val).format(avg=_rupees_compact(avg)))
#         derived["avg_per_month"] = avg
#         derived["months"] = months

#     out = {"bullets": bullets}
#     if derived:
#         out["derived"] = derived
#     return out

# def _insight_trend_line(payload: Dict[str, Any]) -> Dict[str, Any]:
#     trend = payload.get("trend", {})
#     overall = trend.get("overall", {})
#     by_brand = trend.get("by_brand", [])
#     bullets: List[str] = []
#     derived: Dict[str, Any] = {}

#     # NEW: include window if present
#     win = payload.get("window", {}) or {}
#     pr = _format_period(win.get("start"), win.get("end"))
#     if pr:
#         bullets.append(random.choice([
#             "Window considered: {pr}.",
#             "Period window: {pr}.",
#             "Date range: {pr}.",
#             "Coverage: {pr}.",
#             "Time span in view: {pr}.",
#         ]).format(pr=pr))

#     # Overall peak/trough messaging (+ explicit peak month callout)
#     omax = overall.get("max", {})
#     omin = overall.get("min", {})
#     if "value" in omax and "value" in omin and omax.get("value") and omin.get("value"):
#         # explicit peak month callout
#         bullets.append(random.choice([
#             "Peak occurs in {peak} at {val}.",
#             "Highest point is {peak} ({val}).",
#             "Series tops out in {peak} with {val}.",
#             "Peak month: {peak} ({val}).",
#             "The high is registered in {peak}: {val}.",
#         ]).format(peak=omax.get('label','peak'), val=_format_num(omax.get('value'))))

#         # keep the original peak vs trough sentence too (varied)
#         bullets.append(random.choice([
#             "Overall peak in {peak} and trough in {trough}.",
#             "The series peaks around {peak} and bottoms near {trough}.",
#             "Top reading: {peak}; lowest: {trough}.",
#             "Peak appears in {peak}, while the trough is {trough}.",
#             "High watermark at {peak}; low at {trough}.",
#         ]).format(peak=omax.get('label','peak'), trough=omin.get('label','trough')))

#         drop = (omax["value"] - omin["value"]) / omax["value"] if omax["value"] else None
#         if drop is not None:
#             derived["overall_peak_to_trough_drop_pct"] = round(drop * 100, 6)

#     # Brand-wise peak→trough ranges
#     ranges: List[str] = []
#     for b in by_brand or []:
#         name = b.get("brand", "")
#         vmax = _safe_get(b, ["max", "value"], None)
#         vmin = _safe_get(b, ["min", "value"], None)
#         if vmax and vmin and vmax > 0:
#             drop = (vmax - vmin) / vmax
#             derived[f"{name.lower()}_peak_to_trough_drop_pct"] = round(drop * 100, 6)
#             ranges.append(f"{name} ~{int(round(drop*100))}%")

#     if ranges:
#         variations_ranges = [
#             "Peak→trough range (approx): {list}.",
#             "Approximate drawdowns: {list}.",
#             "Peak-to-bottom swings: {list}.",
#             "Volatility snapshot (peak→trough): {list}.",
#             "Range from highs to lows: {list}.",
#         ]
#         bullets.append(random.choice(variations_ranges).format(list=", ".join(ranges)))

#     # Seasonality hint if multiple brands share trough label
#     trough_labels = [b.get("min", {}).get("label") for b in (by_brand or []) if b.get("min")]
#     if trough_labels:
#         common = max(set(trough_labels), key=trough_labels.count)
#         if trough_labels.count(common) >= 2:
#             variations_season = [
#                 "Multiple brands trough around {label}, hinting at seasonality.",
#                 "Common trough near {label} — seasonal pattern likely.",
#                 "Several brands dip around {label}, indicating seasonality.",
#                 "Shared low point around {label} suggests seasonal effects.",
#                 "Trough clustering at {label} points to seasonality.",
#             ]
#             bullets.append(random.choice(variations_season).format(label=common))

#     return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# # ---------- public router ----------

# def attach_insights(payload: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Appends an 'insights' block to your ITEMSSSSS payload without changing existing keys.
#     Supports:
#       - MAT_COMPARE (payload['mat_compare'])
#       - YOY / YTD_YOY (payload['yoy'])
#       - LINE trend (payload['trend'])
#       - Totals (single BAR item, e.g., total unit_sales)
#     """
#     try:
#         mode = str(payload.get("mode", "")).upper()

#         insights_block: Optional[Dict[str, Any]] = None

#         # Prefer explicit structures
#         if mode == "MAT_COMPARE" or "mat_compare" in payload:
#             insights_block = _insight_mat_compare(payload)

#         if insights_block is None and "trend" in payload:
#             insights_block = _insight_trend_line(payload)

#         if insights_block is None and "yoy" in payload:
#             insights_block = _insight_yoy(payload)

#         if insights_block is None and mode == "BAR":
#             bar_items = _safe_get(payload, ["bar", "items"], [])
#             if isinstance(bar_items, list) and len(bar_items) == 1:
#                 insights_block = _insight_totals(payload)

#         if insights_block is None:
#             insights_block = {"bullets": ["No insight template matched this response."]}

#         out = dict(payload)
#         out["insights"] = insights_block
#         return out

#     except Exception as e:
#         out = dict(payload)
#         out["insights"] = {"bullets": [f"Insight generation failed: {e}"]}
#         return out

# # =============================================================================
# # OPTIONAL: quick manual test
# # =============================================================================
# if __name__ == "__main__":
#     # random.seed(42)  # uncomment for deterministic phrasing while testing
#     sample = {
#         "mode": "MAT_COMPARE",
#         "measure": "value_sales",
#         "mat_compare": {
#             "periods": [
#                 {"mat_label": "MAT 2025", "value_sales": 56315997.11, "rank": 1, "start": "2024-10-01", "end": "2025-09-30"},
#                 {"mat_label": "MAT 2024", "value_sales": 55090425.83, "rank": 2, "start": "2023-10-01", "end": "2024-09-30"},
#                 {"mat_label": "MAT 2023", "value_sales": 54262187.76, "rank": 3, "start": "2022-10-01", "end": "2023-09-30"},
#             ]
#         }
#     }
#     print(attach_insights(sample))


















# backend/insights.py

from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

CAT_CANDS = ["brand", "category", "market", "channel", "segment", "manufacturer"]

# =============================================================================
# EXISTING HELPERS (kept as-is)
# =============================================================================

# --- friendly period + join helpers ---
def _format_period_friendly(start: str | None, end: str | None) -> str | None:
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(start[:10])
        e = datetime.fromisoformat(end[:10])
        return f"{s.strftime('%b %d, %Y')} – {e.strftime('%b %d, %Y')}"
    except Exception:
        return f"{start} – {end}"

def _human_join(items: list[str]) -> str:
    items = [str(x) for x in items if x]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]





def _first_numeric(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None

def _pick_measure_col(df: pd.DataFrame, meta: dict) -> str | None:
    # Prefer meta.measure if it exists and is numeric
    m = (meta or {}).get("measure")
    if isinstance(m, str) and m in df.columns and pd.api.types.is_numeric_dtype(df[m]):
        return m
    # Else try common names
    for cand in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
        if cand in df.columns and pd.api.types.is_numeric_dtype(df[cand]):
            return cand
    # Else first numeric
    return _first_numeric(df)

def _pick_cat_dim(df: pd.DataFrame) -> str | None:
    for c in CAT_CANDS:
        if c in df.columns:
            return c
    return None

def _format_num(x: float) -> str:
    try:
        if abs(x) >= 1_000_000:
            return f"{x/1_000_000:.1f}M"
        if abs(x) >= 1_000:
            return f"{x/1_000:.1f}K"
        return f"{x:.0f}"
    except Exception:
        return str(x)

def _format_pct(x: float) -> str:
    try:
        return f"{x*100:.1f}%"
    except Exception:
        return "NA"

def _format_period(start: Optional[str], end: Optional[str]) -> Optional[str]:
    if not start or not end:
        return None
    # Keep ISO compact; consistent with your API
    try:
        s = datetime.fromisoformat(start[:10]).date().isoformat()
        e = datetime.fromisoformat(end[:10]).date().isoformat()
        return f"{s} → {e}"
    except Exception:
        return f"{start} → {end}"

def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:
    """
    Heuristic, lightweight insights that never fail silently.
    Works for table/bar/line; time or no time; any dim.
    """
    insights: list[str] = []

    # --- guardrails ---
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return ["No data to analyze."]

    # Choose measure (y)s
    y = _pick_measure_col(df, meta)
    if y is None:
        insights.append("No numeric measure returned, so only structural results are shown.")
        return insights

    # Pick a categorical dim if present
    cat = _pick_cat_dim(df)

    # Detect time
    has_date = "date" in df.columns
    has_month = "month_year" in df.columns or "month" in df.columns

    # Normalize copy for safe ops
    d = df.copy()

    # ---------------- TIME-SERIES INSIGHTS ----------------
    if has_month or has_date:
        # prefer month_year string for readability
        if has_date:
            try:
                d["__dt"] = pd.to_datetime(d["date"])
            except Exception:
                d["__dt"] = pd.to_datetime(d["date"], errors="coerce")
        else:
            # build a sortable month from month_year or month
            month_col = "month_year" if "month_year" in d.columns else "month"
            parsed = pd.to_datetime(d[month_col], errors="coerce")
            d["__dt"] = parsed.dt.to_period("M").dt.to_timestamp()

        # If categorical exists (e.g., brand lines), focus on top line at the end
        if cat and cat in d.columns:
            # last month in the result
            last_t = d["__dt"].max()
            cur = d[d["__dt"] == last_t]

            # If multiple brands, find top latest and compare to previous point
            grp = cur.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
            if not grp.empty:
                top_brand = grp.index[0]
                top_val = grp.iloc[0]

                # Compute previous value for that brand (prev timestamp)
                prev_t = d["__dt"].sort_values().unique()
                prev_t = prev_t[-2] if len(prev_t) >= 2 else None

                if prev_t is not None:
                    prev_val = d[(d[cat] == top_brand) & (d["__dt"] == prev_t)][y].sum()
                    if pd.notna(prev_val) and prev_val != 0:
                        chg = (top_val - prev_val) / prev_val
                        dir_word = "up" if chg >= 0 else "down"
                        variations = [
                            "{brand} leads the latest with {val} {metric} ({dir} {chg} vs previous).",
                            "Most recent leader: {brand} at {val} {metric} ({dir} {chg} vs last point).",
                            "{brand} tops the newest period at {val} {metric} ({dir} {chg} vs prior).",
                            "Latest snapshot: {brand} is #1 with {val} {metric} ({dir} {chg} m/m).",
                            "{brand} holds the lead currently — {val} {metric} ({dir} {chg} vs prev).",
                        ]
                        insights.append(
                            random.choice(variations).format(
                                brand=top_brand,
                                val=_format_num(top_val),
                                metric=y.replace("_", " "),
                                dir=dir_word,
                                chg=_format_pct(abs(chg)),
                            )
                        )

                # Gap to #2 at the last point
                if len(grp) >= 2:
                    gap = grp.iloc[0] - grp.iloc[1]
                    variations_gap = [
                        "Gap to #{rank2} {b2}: {gap} on the latest point.",
                        "Lead over {b2} stands at {gap} (most recent period).",
                        "Current spread vs {b2}: {gap}.",
                        "Latest margin vs {b2}: {gap}.",
                        "The distance to {b2} right now is {gap}.",
                    ]
                    insights.append(
                        random.choice(variations_gap).format(
                            rank2=2, b2=grp.index[1], gap=_format_num(gap)
                        )
                    )
                # NEW: explicitly mention #3 when present
                if len(grp) >= 3:
                    third_name = grp.index[2]
                    third_val = grp.iloc[2]
                    third_variants = [
                        "In third place: {b3} at {v3}.",
                        "Completing the top-3 is {b3} with {v3}.",
                        "Third spot: {b3} ({v3}).",
                        "{b3} rounds out the top-3 at {v3}.",
                        "Also noteworthy at #3: {b3} with {v3}.",
                    ]
                    insights.append(
                        random.choice(third_variants).format(
                            b3=third_name, v3=_format_num(third_val)
                        )
                    )
        else:
            # No categorical: describe overall trend last vs prev
            last_t = d["__dt"].max()
            prev_times = d["__dt"].sort_values().unique()
            prev_t = prev_times[-2] if len(prev_times) >= 2 else None
            last_val = d.loc[d["__dt"] == last_t, y].sum()
            if prev_t is not None:
                prev_val = d.loc[d["__dt"] == prev_t, y].sum()
                if pd.notna(prev_val) and prev_val != 0:
                    chg = (last_val - prev_val) / prev_val
                    dir_word = "up" if chg >= 0 else "down"
                    variations_line = [
                        "Latest {metric}: {val}; {dir} {chg} vs previous.",
                        "{metric} now at {val} — {dir} {chg} vs last period.",
                        "Most recent {metric} is {val} ({dir} {chg} m/m).",
                        "{metric} prints {val} in the latest period ({dir} {chg} vs prior).",
                        "Current {metric} of {val} is {dir} {chg} against previous.",
                    ]
                    insights.append(
                        random.choice(variations_line).format(
                            metric=y.replace("_", " "),
                            val=_format_num(last_val),
                            dir=dir_word,
                            chg=_format_pct(abs(chg)),
                        )
                    )

        # NEW: peak month callout (overall)
        try:
            # Aggregate overall by month and pick the peak
            by_month = d.groupby(d["__dt"])[y].sum().sort_index()
            if not by_month.empty:
                peak_t = by_month.idxmax()
                peak_v = by_month.max()
                peak_label = peak_t.strftime("%b %Y")
                peak_variants = [
                    "Peak {metric} occurs in {label} at {val}.",
                    "Highest {metric}: {label} ({val}).",
                    "The series peaks in {label} with {val}.",
                    "Top month is {label} at {val} on {metric}.",
                    "{label} marks the peak for {metric} ({val}).",
                ]
                insights.append(
                    random.choice(peak_variants).format(
                        metric=y.replace("_", " "), label=peak_label, val=_format_num(peak_v)
                    )
                )
        except Exception:
            pass

        # NEW: show period range when present in meta
        win = (meta or {}).get("window") or {}
        pr = _format_period(win.get("start"), win.get("end"))
        if pr:
            period_variants = [
                "Period window: {pr}.",
                "Window considered: {pr}.",
                "Date range: {pr}.",
                "Coverage: {pr}.",
                "Time span in view: {pr}.",
            ]
            insights.append(random.choice(period_variants).format(pr=pr))

    # ---------------- CATEGORICAL INSIGHTS ----------------
    # if cat and cat in d.columns:
    #     grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
    #     if not grp.empty:
    #         top_k = grp.head(3)
    #         names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
    #         variations_top = [
    #             "Top {cat}s by {metric}: {names}.",
    #             "Leaders on {metric}: {names}.",
    #             "Ranking by {metric}: {names}.",
    #             "Highest {metric}: {names}.",
    #             "Top performers ({metric}): {names}.",
    #         ]
    #         insights.append(
    #             random.choice(variations_top).format(
    #                 cat=cat, metric=y.replace("_", " "), names=names
    #             )
    #         )
    #         if grp.sum() > 0:
    #             shares = (grp / grp.sum()).head(3)
    #             share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
    #             variations_share = [
    #                 "Share of total {metric}: {share}.",
    #                 "Contribution split ({metric}): {share}.",
    #                 "Within shown total {metric}, shares are: {share}.",
    #                 "{metric} mix: {share}.",
    #                 "Top-3 share breakdown ({metric}): {share}.",
    #             ]
    #             insights.append(
    #                 random.choice(variations_share).format(
    #                     metric=y.replace("_", " "), share=share_txt
    #                 )
    #             )

# ---------------- CATEGORICAL INSIGHTS ----------------
    if cat and cat in d.columns:
        grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)
        if not grp.empty:
            N = min(len(grp), 10)  # cap long lists for readability
            top_k = grp.head(N)
            names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())
            insights.append(
                random.choice([
                    "Top {n} {cat}s by {metric}: {names}.",
                    "Leaders on {metric} (Top {n}): {names}.",
                    "Ranking by {metric} — Top {n}: {names}.",
                    "Highest {metric} — Top {n}: {names}.",
                    "Top {n} performers ({metric}): {names}.",
                ]).format(n=N, cat=cat, metric=y.replace("_"," "), names=names)
            )

            total_sum = float(grp.sum())
            if total_sum > 0:
                shares = (grp / total_sum).head(N)
                share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())
                insights.append(
                    random.choice([
                        "Share of total {metric} (Top {n}): {share}.",
                        "Contribution split (Top {n}, {metric}): {share}.",
                        "Within total {metric}, Top {n} shares: {share}.",
                        "{metric} mix (Top {n}): {share}.",
                        "Top {n} share breakdown ({metric}): {share}.",
                    ]).format(n=N, metric=y.replace("_"," "), share=share_txt)
                )

    # ---------------- FALLBACK / TOTAL ----------------
    if not insights:
        total = pd.to_numeric(d[y], errors="coerce").sum()
        variations_total = [
            "Total {metric} in the result: {val}.",
            "Aggregate {metric}: {val}.",
            "Combined {metric} across rows: {val}.",
            "Overall {metric} sums to {val}.",
            "Sum of {metric}: {val}.",
        ]
        insights.append(
            random.choice(variations_total).format(
                metric=y.replace("_", " "), val=_format_num(total)
            )
        )

    return insights[:4]  # allow up to 4 to include period/peak

# =============================================================================
# NEW: PAYLOAD-AWARE INSIGHTS (for your ITEMSSSSS JSON)
# =============================================================================

def _pct_to_str(p: Optional[float], signed: bool = True, decimals: int = 2) -> str:
    if p is None or (isinstance(p, float) and (math.isnan(p) or math.isinf(p))):
        return "NA"
    pct = p * 100.0
    s = f"{pct:.{decimals}f}%"
    if signed and pct > 0:
        s = "+" + s
    return s

def _rupees_compact(n: Optional[float]) -> str:
    # keep it simple and neutral (no locale lib)
    try:
        n = float(n)
    except Exception:
        return "NA"
    if abs(n) >= 1_00_00_000:   # 10M+
        return f"₹{n/1_00_00_000:.2f}Cr"
    if abs(n) >= 1_00_000:      # 100k+
        return f"₹{n/1_00_000:.2f}L"
    return f"₹{n:,.0f}"

def _months_inclusive(start_str: str, end_str: str) -> int:
    try:
        s = datetime.fromisoformat(start_str[:10])
        e = datetime.fromisoformat(end_str[:10])
    except Exception:
        return 0
    return (e.year - s.year) * 12 + (e.month - s.month) + 1

def _safe_get(d: Dict[str, Any], path: List[str], default=None):
    cur = d
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur

def _calc_growth(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    try:
        if curr is None or prev is None or prev == 0:
            return None
        return (curr - prev) / prev
    except Exception:
        return None

def _calc_cagr(v0: Optional[float], vN: Optional[float], years: float) -> Optional[float]:
    try:
        if v0 is None or vN is None or v0 <= 0 or years <= 0:
            return None
        return (vN / v0) ** (1.0 / years) - 1.0
    except Exception:
        return None

# ---------- per-mode insight builders with variations ----------
def _insight_topn_period_bar(payload: Dict[str, Any], label_hint: str) -> Dict[str, Any]:
    """
    Human-like Top-N insights for MAT or YTD when we have brand bars.
    Works for payloads like:
      - {'mode': 'YTD', ... 'bar': {'items': [{'rank':1,'label':'Alpha','value':...}, ...]}}
      - {'calculation_mode': 'mat', ... 'bar': {'items': [...]}}
    """
    bar = _safe_get(payload, ["bar"], {}) or {}
    items = bar.get("items") or []
    measure = str(payload.get("measure", "")).lower()
    win = payload.get("window", {}) or {}
    start, end = win.get("start"), win.get("end")
    pr = _format_period_friendly(start, end)

    if not items:
        return {"bullets": [f"No {label_hint} bars available to summarize."]}

    # rank by 'rank' then value if needed
    try:
        items_sorted = sorted(items, key=lambda x: (x.get("rank", 9999), -float(x.get("value", 0))))
    except Exception:
        items_sorted = items

    # Build Top-N list (cap at 10 to avoid walls of text)
    N = min(len(items_sorted), 10)
    fmt_val = lambda v: _format_num(v) if measure.startswith("unit") else _rupees_compact(v)
    topline_bits = [f"{it.get('label','?')} ({fmt_val(it.get('value'))})" for it in items_sorted[:N]]

    bullets: List[str] = []
    # 1) Period line (friendly)
    if pr:
        bullets.append(
            random.choice([
                f"This {label_hint} view covers {pr}.",
                f"We’re looking at {pr} for this {label_hint} cut.",
                f"Period in scope ({label_hint}): {pr}.",
                f"Time span ({label_hint}): {pr}.",
                f"Figures below refer to {pr} ({label_hint}).",
            ])
        )

    # 2) Top-N summary line
    bullets.append(
        random.choice([
            f"Top {N} by {measure.replace('_',' ')}: {_human_join(topline_bits)}.",
            f"On {measure.replace('_',' ')}, the leaders are {_human_join(topline_bits)}.",
            f"Ranking by {measure.replace('_',' ')}: {_human_join(topline_bits)}.",
            f"In this {label_hint} slice, {_human_join(topline_bits)} stand out.",
            f"The {label_hint} leaderboard reads: {_human_join(topline_bits)}.",
        ])
    )

    # 3) Gap between #1 and #2 (when available)
    if len(items_sorted) >= 2:
        lead, runner = items_sorted[0], items_sorted[1]
        gap = (lead.get("value") or 0) - (runner.get("value") or 0)
        if gap:
            bullets.append(
                random.choice([
                    f"{lead.get('label')} holds a lead of {fmt_val(gap)} over {runner.get('label')}.",
                    f"The gap between {lead.get('label')} and {runner.get('label')} is {fmt_val(gap)}.",
                    f"{lead.get('label')} is ahead of {runner.get('label')} by {fmt_val(gap)}.",
                    f"Margin at the top: {fmt_val(gap)} between {lead.get('label')} and {runner.get('label')}.",
                    f"{runner.get('label')} trails {lead.get('label')} by {fmt_val(gap)}.",
                ])
            )

    # 4) Optional: share-of-Top-N (adds one compact line)
    try:
        total_topn = float(sum(float(it.get("value") or 0) for it in items_sorted[:N]))
        if total_topn > 0:
            shares = []
            for it in items_sorted[:min(N,3)]:  # keep it short
                pct = (float(it.get("value") or 0) / total_topn)
                shares.append(f"{it.get('label')} {_format_pct(pct)}")
            bullets.append(
                random.choice([
                    f"Within these Top {N}, share splits roughly as: {_human_join(shares)}.",
                    f"Share within the Top {N}: {_human_join(shares)}.",
                    f"Top {N} contribution mix: {_human_join(shares)}.",
                ])
            )
    except Exception:
        pass

    return {"bullets": bullets}


def _insight_period_total(payload: Dict[str, Any], label_hint: str) -> Dict[str, Any]:
    """
    Human-like totals for MAT or YTD when only one bar item is returned.
    """
    bar = _safe_get(payload, ["bar"], {}) or {}
    items = bar.get("items") or []
    if not isinstance(items, list) or len(items) != 1:
        return {"bullets": [f"No single total found for {label_hint}."]}

    measure = str(payload.get("measure", "")).lower()
    win = payload.get("window", {}) or {}
    start, end = win.get("start"), win.get("end")
    pr = _format_period_friendly(start, end)

    item = items[0]
    label = item.get("label", "Total")
    total = item.get("value", None)

    bullets: List[str] = []
    derived: Dict[str, Any] = {}

    if pr:
        bullets.append(
            random.choice([
                f"This {label_hint} total covers {pr}.",
                f"All numbers here are for {pr} ({label_hint}).",
                f"Time frame in view ({label_hint}): {pr}.",
                f"Period covered: {pr} ({label_hint}).",
                f"These figures refer to {pr} ({label_hint}).",
            ])
        )

    if measure == "unit_sales":
        bullets.append(
            random.choice([
                f"{label} sold {_format_num(total)} units.",
                f"{label} comes to {_format_num(total)} units.",
                f"Total for {label}: {_format_num(total)} units.",
                f"{label} adds up to {_format_num(total)} units.",
                f"{label} delivered {_format_num(total)} units.",
            ])
        )
    elif measure == "value_sales":
        bullets.append(
            random.choice([
                f"{label} brought in {_rupees_compact(total)} in sales.",
                f"{label} totals {_rupees_compact(total)} in value.",
                f"Total for {label}: {_rupees_compact(total)}.",
                f"{label} adds up to {_rupees_compact(total)}.",
                f"{label} delivered {_rupees_compact(total)} in value sales.",
            ])
        )
    else:
        bullets.append(f"{label} total for {measure} is {_format_num(total)}.")

    # avg per month for the period
    months = _months_inclusive(start, end) if (start and end) else 0
    if months > 0 and isinstance(total, (int, float)):
        avg = total / months
        if measure == "unit_sales":
            bullets.append(random.choice([
                f"That works out to ~{_format_num(avg)} units per month.",
                f"Average run-rate is about {_format_num(avg)} units monthly.",
                f"Roughly {_format_num(avg)} units a month on average.",
            ]))
        elif measure == "value_sales":
            bullets.append(random.choice([
                f"That’s ~{_rupees_compact(avg)} per month on average.",
                f"Monthly run-rate is about {_rupees_compact(avg)}.",
                f"Roughly {_rupees_compact(avg)} a month on average.",
            ]))
        derived["avg_per_month"] = avg
        derived["months"] = months

    out = {"bullets": bullets}
    if derived:
        out["derived"] = derived
    return out






def _insight_mat_compare(payload: Dict[str, Any]) -> Dict[str, Any]:
    # accept either payload['mat_compare']['periods'] or nested variant
    periods: List[Dict[str, Any]] = (
        _safe_get(payload, ["mat_compare", "periods"], [])
        or _safe_get(payload, ["mat_compare", "mat_compare", "periods"], [])
        or []
    )
    if not periods:
        return {"bullets": ["No MAT periods available to compare."]}

    # sort by rank if available; else keep given order
    periods_sorted = sorted(periods, key=lambda x: x.get("rank", 9999))
    bullets: List[str] = []
    derived: Dict[str, Any] = {}

    # Headline on top period
    top = periods_sorted[0]
    top_label = top.get("mat_label", "Latest")
    top_val = top.get("value_sales")

    variations_headline = [
        "{label} value sales reached {val} (rank #1 among shown periods).",
        "{label} comes out on top with {val} in value sales.",
        "Highest value sales in the set: {label} at {val}.",
        "{label} leads the comparison, posting {val} in value sales.",
        "{label} prints the peak value sales at {val}.",
    ]
    bullets.append(
        random.choice(variations_headline).format(
            label=top_label, val=_rupees_compact(top_val)
        )
    )

    # NEW: explicit MAT period windows for each label
    period_lines = []
    for p in periods_sorted[:3]:
        s, e = p.get("start"), p.get("end")
        label = p.get("mat_label", "")
        pr = _format_period(s, e)
        if pr:
            period_lines.append(f"{label}: {pr}")
    if period_lines:
        period_variants = [
            "Period windows — " + "; ".join(period_lines) + ".",
            "Coverage: " + "; ".join(period_lines) + ".",
            "Date ranges → " + "; ".join(period_lines) + ".",
            "MAT spans: " + "; ".join(period_lines) + ".",
            "Windows: " + "; ".join(period_lines) + ".",
        ]
        bullets.append(random.choice(period_variants))

    # Pairwise growth
    if len(periods_sorted) >= 2:
        p1 = periods_sorted[0]
        p2 = periods_sorted[1]
        g_10 = _calc_growth(p1.get("value_sales"), p2.get("value_sales"))
        if g_10 is not None:
            variations_pair = [
                "{p1} vs {p2}: {g}.",
                "Change from {p2} to {p1}: {g}.",
                "Step-up {p2}→{p1}: {g}.",
                "{p1} relative to {p2}: {g}.",
                "Delta {p1} over {p2}: {g}.",
            ]
            bullets.append(
                random.choice(variations_pair).format(
                    p1=p1.get("mat_label", "P1"),
                    p2=p2.get("mat_label", "P2"),
                    g=_pct_to_str(g_10),
                )
            )
            derived["growth_p1_vs_p2_pct"] = round(g_10 * 100, 6)

    if len(periods_sorted) >= 3:
        p2 = periods_sorted[1]
        p3 = periods_sorted[2]
        g_21 = _calc_growth(p2.get("value_sales"), p3.get("value_sales"))
        if g_21 is not None:
            variations_pair2 = [
                "{p2} vs {p3}: {g}.",
                "From {p3} to {p2}: {g}.",
                "Lift {p3}→{p2}: {g}.",
                "{p2} compared with {p3}: {g}.",
                "Delta {p2} over {p3}: {g}.",
            ]
            bullets.append(
                random.choice(variations_pair2).format(
                    p2=p2.get("mat_label", "P2"),
                    p3=p3.get("mat_label", "P3"),
                    g=_pct_to_str(g_21),
                )
            )
            derived["growth_p2_vs_p3_pct"] = round(g_21 * 100, 6)

        # 2-year CAGR (assuming 1 year spacing)
        cagr = _calc_cagr(p3.get("value_sales"), periods_sorted[0].get("value_sales"), years=2.0)
        if cagr is not None:
            variations_cagr = [
                "Two-year CAGR across shown MATs: {c}.",
                "2Y CAGR (MAT set): {c}.",
                "CAGR over the last two MATs: {c}.",
                "Across the two-year span, CAGR is {c}.",
                "Two-year compounded growth: {c}.",
            ]
            bullets.append(random.choice(variations_cagr).format(c=_pct_to_str(cagr, signed=False)))
            derived["cagr_2y_pct"] = round(cagr * 100, 6)

    return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

import random

def _insight_yoy(payload: Dict[str, Any]) -> Dict[str, Any]:
    yoy_items: List[Dict[str, Any]] = _safe_get(payload, ["yoy", "items"], []) or []
    measure_type = _safe_get(payload, ["yoy", "measure_type"], "measure")
    if not yoy_items:
        return {"bullets": ["No YoY items available."]}

    branded = [it for it in yoy_items if "brand" in it]
    bullets: List[str] = []

    def _fmt_by_mt(x: Optional[float]) -> str:
        if x is None:
            return "NA"
        return _rupees_compact(x) if str(measure_type).lower().startswith("value") else _format_num(x)

    if branded:
        branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)

        # -------- Top-N summary line --------
        N = min(len(branded), 10)
        ranked_pairs = []
        for i, it in enumerate(branded[:N], start=1):
            ranked_pairs.append(f"{i}. {str(it.get('brand')).title()} ({_pct_to_str(it.get('yoy_pct', 0.0))})")

        bullets.append(
            random.choice([
                "Here’s how the top {n} brands stack up YoY: {line}.",
                "Looking at YoY growth, the ranking is: {line}.",
                "In YoY terms, the top {n} players are: {line}.",
                "The YoY leaderboard (Top {n}) looks like this: {line}.",
                "Here are the Top {n} brands by YoY change: {line}.",
            ]).format(n=N, line="; ".join(ranked_pairs))
        )

        # -------- Per-rank commentary (more natural tone) --------
        yoy_vals = [it.get("yoy_pct") for it in branded if isinstance(it.get("yoy_pct"), (int, float))]
        avg_yoy = np.mean(yoy_vals) if yoy_vals else None

        K = min(N, 4)
        for i in range(K):
            it = branded[i]
            name = str(it.get("brand")).title()
            pct = _pct_to_str(it.get("yoy_pct", 0.0))
            curr = it.get("curr")
            prev = it.get("prev")
            delta = (curr - prev) if (isinstance(curr, (int, float)) and isinstance(prev, (int, float))) else None

            gap_to_prev_rank = None
            if i == 0 and N >= 2:
                gap_to_prev_rank = (branded[0].get("yoy_pct", 0.0) - branded[1].get("yoy_pct", 0.0))
            elif i > 0:
                gap_to_prev_rank = (branded[i].get("yoy_pct", 0.0) - branded[i-1].get("yoy_pct", 0.0))

            # Build context
            ctx_parts = []
            if i == 0 and gap_to_prev_rank is not None:
                ctx_parts.append(f"leading by { _pct_to_str(gap_to_prev_rank, signed=True) } over the next brand")
            elif i > 0 and gap_to_prev_rank is not None:
                ctx_parts.append(f"{ _pct_to_str(gap_to_prev_rank, signed=True) } compared to #{i}")

            if delta is not None:
                ctx_parts.append(f"with a net change of {_fmt_by_mt(delta)}")

            if avg_yoy is not None:
                diff_vs_avg = (it.get("yoy_pct", 0.0) - avg_yoy)
                if diff_vs_avg >= 0:
                    ctx_parts.append(f"outperforming the average ({_pct_to_str(avg_yoy, signed=False)})")
                else:
                    ctx_parts.append(f"lagging the average ({_pct_to_str(avg_yoy, signed=False)})")

            ctx = ", ".join(ctx_parts)

            per_rank_variants = [
                f"{name} holds #{i+1} with {pct}, {ctx}.",
                f"Ranked #{i+1}, {name} shows {pct} YoY, {ctx}.",
                f"{name} comes in at #{i+1} ({pct}), {ctx}.",
                f"At #{i+1}, {name} posts {pct}, {ctx}.",
                f"{name} (#{i+1}) records {pct} YoY, {ctx}.",
            ]
            bullets.append(random.choice(per_rank_variants))

        # -------- Overall summary --------
        pos_cnt = sum(1 for x in branded if (x.get("yoy_pct") or 0) > 0)
        neg_cnt = sum(1 for x in branded if (x.get("yoy_pct") or 0) < 0)
        if pos_cnt and not neg_cnt:
            bullets.append(random.choice([
                "Interestingly, every brand tracked here is in growth mode.",
                "All brands are enjoying positive YoY momentum.",
                "The entire set is growing year-on-year — no declines spotted.",
            ]))
        elif neg_cnt and not pos_cnt:
            bullets.append(random.choice([
                "Unfortunately, all brands in this cut are shrinking YoY.",
                "Every tracked brand shows a year-on-year decline.",
                "No growth stories here — the whole group is down YoY.",
            ]))
        else:
            bullets.append(random.choice([
                f"A mixed picture: {pos_cnt} brands are growing while {neg_cnt} are slipping back.",
                f"Split performance — {pos_cnt} in the green, {neg_cnt} in decline.",
                f"Growth is uneven: {pos_cnt} brands rising and {neg_cnt} falling YoY.",
            ]))

        return {"bullets": bullets}

    # fallback (no brand dim)
    g = yoy_items[0].get("yoy_pct", 0.0)
    bullets.append(f"Overall YoY change is { _pct_to_str(g) } for this slice.")
    return {"bullets": bullets}


    # branded = [it for it in yoy_items if "brand" in it]
    # if branded:
    #     branded.sort(key=lambda x: x.get("yoy_pct", 0.0), reverse=True)
    #     lead = branded[0]
    #     lead_name = str(lead.get("brand")).title()
    #     lead_pct = _pct_to_str(lead.get("yoy_pct", 0.0))
    #     variations_lead = [
    #         "{brand} leads {mt} YoY at {pct}.",
    #         "Top YoY mover on {mt}: {brand} ({pct}).",
    #         "{brand} shows the strongest YoY on {mt} at {pct}.",
    #         "{brand} is ahead on {mt} YoY with {pct}.",
    #         "Leading YoY growth ({mt}): {brand} at {pct}.",
    #     ]
    #     bullets.append(random.choice(variations_lead).format(brand=lead_name, mt=measure_type, pct=lead_pct))

    #     if len(branded) >= 2:
    #         second = branded[1]
    #         second_name = str(second.get("brand")).title()
    #         second_pct = _pct_to_str(second.get("yoy_pct", 0.0))
    #         variations_second = [
    #             "Next is {brand} at {pct}.",
    #             "Runner-up: {brand} ({pct}).",
    #             "Followed by {brand} at {pct}.",
    #             "Then comes {brand} with {pct}.",
    #             "{brand} follows at {pct}.",
    #         ]
    #         bullets.append(random.choice(variations_second).format(brand=second_name, pct=second_pct))

    #     # NEW: call out #3 explicitly when present
    #     if len(branded) >= 3:
    #         third = branded[2]
    #         third_name = str(third.get("brand")).title()
    #         third_pct = _pct_to_str(third.get("yoy_pct", 0.0))
    #         variations_third = [
    #             "Third place: {brand} at {pct}.",
    #             "Completing the top-3: {brand} ({pct}).",
    #             "In third: {brand} at {pct}.",
    #             "{brand} rounds out the top-3 with {pct}.",
    #             "Also notable in #3: {brand} ({pct}).",
    #         ]
    #         bullets.append(random.choice(variations_third).format(brand=third_name, pct=third_pct))

    #     pos_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) > 0)
    #     neg_cnt = sum(1 for it in branded if (it.get("yoy_pct") or 0) < 0)
    #     if pos_cnt and not neg_cnt:
    #         variations_allpos = [
    #             "All tracked brands are growing YoY.",
    #             "Every brand in scope shows YoY growth.",
    #             "YoY is positive across the board.",
    #             "All brands post positive YoY.",
    #             "Universal YoY growth among tracked brands.",
    #         ]
    #         bullets.append(random.choice(variations_allpos))
    #     elif neg_cnt and not pos_cnt:
    #         variations_allneg = [
    #             "All tracked brands are declining YoY.",
    #             "Every brand in scope shows a YoY decline.",
    #             "YoY is negative across the board.",
    #             "All brands post YoY contraction.",
    #             "Universal YoY decline among tracked brands.",
    #         ]
    #         bullets.append(random.choice(variations_allneg))
    #     else:
    #         variations_mix = [
    #             "{p} brand(s) growing, {n} declining YoY.",
    #             "Mixed picture: {p} up and {n} down YoY.",
    #             "YoY is split — {p} positive, {n} negative.",
    #             "{p} brands up YoY; {n} down.",
    #             "Growth is uneven: {p} positive vs {n} negative YoY.",
    #         ]
    #         bullets.append(random.choice(variations_mix).format(p=pos_cnt, n=neg_cnt))
    #     return {"bullets": bullets}

    # # single total (no brand)
    # g = yoy_items[0].get("yoy_pct", 0.0)
    # variations_total = [
    #     "YoY change is {g}.",
    #     "Overall YoY stands at {g}.",
    #     "Aggregate YoY movement: {g}.",
    #     "Headline YoY shift: {g}.",
    #     "Total YoY delta: {g}.",
    # ]
    # bullets.append(random.choice(variations_total).format(g=_pct_to_str(g)))
    # return {"bullets": bullets}

def _insight_totals(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Handle single total in bar.items (e.g., total unit_sales for a brand)
    bar_items = _safe_get(payload, ["bar", "items"], [])
    measure = str(payload.get("measure", "")).lower()
    if not isinstance(bar_items, list) or len(bar_items) != 1:
        return {"bullets": ["No single total found."]}

    item = bar_items[0]
    label = item.get("label", "Total")
    # value may live in "value" or under measure name
    total = item.get("value", None)
    if total is None:
        total = item.get(measure, None)

    bullets: List[str] = []
    derived: Dict[str, Any] = {}

    # NEW: include window if present
    win = payload.get("window", {}) or {}
    pr = _format_period(win.get("start"), win.get("end"))
    if pr:
        bullets.append(random.choice([
            "Window considered: {pr}.",
            "Period window: {pr}.",
            "Date range: {pr}.",
            "Coverage: {pr}.",
            "Time span in view: {pr}.",
        ]).format(pr=pr))

    if measure == "unit_sales":
        variations_units = [
            "{label} sold a total of {val} units in the selected period.",
            "Total units for {label}: {val}.",
            "{label} accumulated {val} units over the window.",
            "Across the period, {label} reached {val} units.",
            "Units summed for {label}: {val}.",
        ]
        bullets.append(random.choice(variations_units).format(label=label, val=_format_num(total)))
    elif measure == "value_sales":
        variations_value = [
            "{label} value sales totaled {val} in the selected period.",
            "Total value sales for {label}: {val}.",
            "{label} posted {val} in value sales across the window.",
            "Aggregate value sales for {label} come to {val}.",
            "Cumulative value sales for {label}: {val}.",
        ]
        bullets.append(random.choice(variations_value).format(label=label, val=_rupees_compact(total)))
    else:
        variations_other = [
            "{label} total for {metric} is {val}.",
            "Aggregate {metric} for {label}: {val}.",
            "{label} recorded {val} on {metric}.",
            "Combined {metric} for {label}: {val}.",
            "Overall {metric} ({label}): {val}.",
        ]
        bullets.append(random.choice(variations_other).format(label=label, metric=measure, val=_format_num(total)))

    # optional monthly average if window present
    start, end = win.get("start"), win.get("end")
    months = _months_inclusive(start, end) if (start and end) else 0
    if months > 0 and isinstance(total, (int, float)):
        avg = total / months
        if measure == "unit_sales":
            variations_avg = [
                "~{avg} units per month on average.",
                "Monthly run-rate ~{avg} units.",
                "That’s roughly {avg} units/month.",
                "Avg monthly volume ~{avg} units.",
                "Per-month average is ~{avg} units.",
            ]
            bullets.append(random.choice(variations_avg).format(avg=_format_num(avg)))
        elif measure == "value_sales":
            variations_avg_val = [
                "~{avg} per month on average.",
                "Monthly run-rate ~{avg}.",
                "That’s roughly {avg} each month.",
                "Avg monthly value ~{avg}.",
                "Per-month average is ~{avg}.",
            ]
            bullets.append(random.choice(variations_avg_val).format(avg=_rupees_compact(avg)))
        derived["avg_per_month"] = avg
        derived["months"] = months

    out = {"bullets": bullets}
    if derived:
        out["derived"] = derived
    return out

def _insight_trend_line(payload: Dict[str, Any]) -> Dict[str, Any]:
    trend = payload.get("trend", {})
    overall = trend.get("overall", {})
    by_brand = trend.get("by_brand", [])
    bullets: List[str] = []
    derived: Dict[str, Any] = {}

    # NEW: include window if present
    win = payload.get("window", {}) or {}
    pr = _format_period(win.get("start"), win.get("end"))
    if pr:
        bullets.append(random.choice([
            "Window considered: {pr}.",
            "Period window: {pr}.",
            "Date range: {pr}.",
            "Coverage: {pr}.",
            "Time span in view: {pr}.",
        ]).format(pr=pr))

    # Overall peak/trough messaging (+ explicit peak month callout)
    omax = overall.get("max", {})
    omin = overall.get("min", {})
    if "value" in omax and "value" in omin and omax.get("value") and omin.get("value"):
        # explicit peak month callout
        bullets.append(random.choice([
            "Peak occurs in {peak} at {val}.",
            "Highest point is {peak} ({val}).",
            "Series tops out in {peak} with {val}.",
            "Peak month: {peak} ({val}).",
            "The high is registered in {peak}: {val}.",
        ]).format(peak=omax.get('label','peak'), val=_format_num(omax.get('value'))))

        # keep the original peak vs trough sentence too (varied)
        bullets.append(random.choice([
            "Overall peak in {peak} and trough in {trough}.",
            "The series peaks around {peak} and bottoms near {trough}.",
            "Top reading: {peak}; lowest: {trough}.",
            "Peak appears in {peak}, while the trough is {trough}.",
            "High watermark at {peak}; low at {trough}.",
        ]).format(peak=omax.get('label','peak'), trough=omin.get('label','trough')))

        drop = (omax["value"] - omin["value"]) / omax["value"] if omax["value"] else None
        if drop is not None:
            derived["overall_peak_to_trough_drop_pct"] = round(drop * 100, 6)

    # Brand-wise peak→trough ranges
    ranges: List[str] = []
    for b in by_brand or []:
        name = b.get("brand", "")
        vmax = _safe_get(b, ["max", "value"], None)
        vmin = _safe_get(b, ["min", "value"], None)
        if vmax and vmin and vmax > 0:
            drop = (vmax - vmin) / vmax
            derived[f"{name.lower()}_peak_to_trough_drop_pct"] = round(drop * 100, 6)
            ranges.append(f"{name} ~{int(round(drop*100))}%")

    if ranges:
        variations_ranges = [
            "Peak→trough range (approx): {list}.",
            "Approximate drawdowns: {list}.",
            "Peak-to-bottom swings: {list}.",
            "Volatility snapshot (peak→trough): {list}.",
            "Range from highs to lows: {list}.",
        ]
        bullets.append(random.choice(variations_ranges).format(list=", ".join(ranges)))

    # Seasonality hint if multiple brands share trough label
    trough_labels = [b.get("min", {}).get("label") for b in (by_brand or []) if b.get("min")]
    if trough_labels:
        common = max(set(trough_labels), key=trough_labels.count)
        if trough_labels.count(common) >= 2:
            variations_season = [
                "Multiple brands trough around {label}, hinting at seasonality.",
                "Common trough near {label} — seasonal pattern likely.",
                "Several brands dip around {label}, indicating seasonality.",
                "Shared low point around {label} suggests seasonal effects.",
                "Trough clustering at {label} points to seasonality.",
            ]
            bullets.append(random.choice(variations_season).format(label=common))

    return {"bullets": bullets, "derived": derived} if derived else {"bullets": bullets}

# ---------- public router ----------

def attach_insights(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Appends an 'insights' block to your ITEMSSSSS payload without changing existing keys.
    Supports:
      - MAT_COMPARE (payload['mat_compare'])
      - YOY / YTD_YOY (payload['yoy'])
      - LINE trend (payload['trend'])
      - Totals (single BAR item, e.g., total unit_sales)
      - MAT / YTD Top-N and Totals
    """
    try:
        mode = str(payload.get("mode", "")).upper()
        calc_mode = str(payload.get("calculation_mode", "")).lower()   # <-- FIXED

        insights_block: Optional[Dict[str, Any]] = None

        # MAT_COMPARE
        if mode == "MAT_COMPARE" or "mat_compare" in payload:
            insights_block = _insight_mat_compare(payload)

        # TREND
        if insights_block is None and "trend" in payload:
            insights_block = _insight_trend_line(payload)

        # YOY
        if insights_block is None and "yoy" in payload:
            insights_block = _insight_yoy(payload)

        # --- MAT / YTD specific ---
        if insights_block is None:
            bar_items = _safe_get(payload, ["bar", "items"], [])
            dims = payload.get("dims") or []

            if (mode == "YTD" or calc_mode == "ytd") and isinstance(bar_items, list):
                if len(bar_items) >= 2 and ("brand" in dims or _safe_get(payload, ["bar", "x"]) == "brand"):
                    insights_block = _insight_topn_period_bar(payload, "YTD")
                elif len(bar_items) == 1:
                    insights_block = _insight_period_total(payload, "YTD")

            if calc_mode == "mat" and isinstance(bar_items, list):
                if len(bar_items) >= 2 and ("brand" in dims or _safe_get(payload, ["bar", "x"]) == "brand"):
                    insights_block = _insight_topn_period_bar(payload, "MAT")
                elif len(bar_items) == 1:
                    insights_block = _insight_period_total(payload, "MAT")

        # BAR fallback
        if insights_block is None and mode == "BAR":
            bar_items = _safe_get(payload, ["bar", "items"], [])
            if isinstance(bar_items, list) and len(bar_items) == 1:
                insights_block = _insight_totals(payload)

        # Default
        if insights_block is None:
            insights_block = {"bullets": ["No insight template matched this response."]}

        out = dict(payload)
        out["insights"] = insights_block
        return out

    except Exception as e:
        out = dict(payload)
        out["insights"] = {"bullets": [f"Insight generation failed: {e}"]}
        return out
