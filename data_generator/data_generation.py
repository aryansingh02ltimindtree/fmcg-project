# import random, numpy as np, pandas as pd, json
# from datetime import date
# from calendar import monthrange
# from pathlib import Path

# # ==== CONFIG =====
# EXCEL_PATH = r"./data/sample_nielsen_extended.xlsx"        # ⬅️ change to your file path
# OUTPUT_JSONL = r"./data/synthetic_payloads.json"     # payloads only
# OUTPUT_PAIRS_JSONL = r"./data/synthetic_pairs.json"  # {payload, insights[]} pairs
# N_SAMPLES_PER_TYPE = 3                  # ⬅️ how many per scenario per category
# RANDOM_SEED = 42
# # =================

# random.seed(RANDOM_SEED)
# np.random.seed(RANDOM_SEED)

# # -------- date helpers --------
# def month_end(y, m):
#     return date(y, m, monthrange(y, m)[1]).isoformat()

# def month_start(y, m):
#     return date(y, m, 1).isoformat()

# def month_label(y, m):
#     return pd.Timestamp(year=y, month=m, day=1).strftime("%b %Y")

# def mat_window_for(year, anchor_month):
#     """Return (start_iso, end_iso) for a 12-month MAT ending at anchor_month of `year`."""
#     end_y, end_m = year, anchor_month
#     start_m_total = (end_y * 12 + end_m) - 11
#     start_y = (start_m_total - 1) // 12
#     start_m = (start_m_total - 1) % 12 + 1
#     return month_start(start_y, start_m), month_end(end_y, end_m)

# # -------- load categories/brands from Excel --------
# def load_entities(path):
#     df = pd.read_excel(path)
#     # tolerant column resolution
#     cols = {c.lower().strip(): c for c in df.columns}
#     if "category" not in cols or "brand" not in cols:
#         raise ValueError("Excel must have 'category' and 'brand' columns.")
#     cat_col, brand_col = cols["category"], cols["brand"]
#     df = df[[cat_col, brand_col]].dropna()
#     cats = df[cat_col].dropna().unique().tolist()
#     brands_by_cat = {
#         cat: df.loc[df[cat_col] == cat, brand_col].dropna().unique().tolist()
#         for cat in cats
#     }
#     # remove empties
#     brands_by_cat = {c: b for c, b in brands_by_cat.items() if len(b) > 0}
#     cats = [c for c in cats if c in brands_by_cat]
#     return cats, brands_by_cat

# # -------- payload builders --------
# def build_mat_compare(cat):
#     measure = random.choice(["value_sales","unit_sales"])
#     years = random.sample([2025, 2024, 2023, 2022], 3)
#     years.sort(reverse=True)
#     anchor_month = random.choice([3, 6, 9, 12])  # Mar/Jun/Sep/Dec
#     periods = []
#     # synthetic but consistent magnitudes by measure
#     base_low, base_high = (5e6, 8e6) if measure == "value_sales" else (5e5, 1.2e6)
#     for y in years:
#         st, en = mat_window_for(y, anchor_month)
#         val = float(np.random.uniform(* (base_low, base_high)))
#         periods.append({"mat_label": f"MAT {y}", "start": st, "end": en, measure: val})
#     return {
#         "mode": "MAT_COMPARE",
#         "measure": measure,
#         "window": {"start": periods[-1]["start"], "end": periods[0]["end"]},
#         "dims": ["mat_label"],
#         "filters": {"category": cat},
#         "mat_compare": {
#             "mat_compare": {
#                 "anchor_month": anchor_month,
#                 "years": years,
#                 "labels": [f"MAT {y}" for y in years],
#             },
#             "periods": periods,
#             "chart_type": "bar",
#             "rowcount": len(periods),
#         },
#         "calculation_mode": "mat_compare",
#     }

# def build_yoy_by_brand(cat, brands):
#     measure_type = random.choice(["value","unit"])
#     measure = f"{measure_type}_yoy"
#     # choose 2–3 brands from this category
#     pick = random.sample(brands, min(len(brands), random.choice([2,3])))
#     items=[]
#     for b in pick:
#         prev = float(np.random.uniform(3e5, 8e5)) if measure_type=="unit" else float(np.random.uniform(5e6, 1.2e7))
#         growth = np.random.uniform(0.90, 1.20)  # -10% to +20%
#         curr = float(prev * growth)
#         items.append({"brand": b, "prev": prev, "curr": curr, "yoy_pct": (curr/prev - 1)})
#     # simple window (random quarter)
#     y = random.choice([2023, 2024, 2025])
#     start_m = random.choice([1, 4, 7, 10])
#     end_m = start_m + 2
#     return {
#         "mode": "BAR",
#         "measure": measure,
#         "window": {"start": month_start(y, start_m), "end": month_end(y, end_m)},
#         "dims": ["brand"],
#         "filters": {"category": cat},
#         "yoy": {"measure_type": measure_type, "items": items},
#         "bar": {"x": "brand", "y": measure,
#                 "items": [{"rank": i+1, "label": it["brand"], "value": it["yoy_pct"]} for i, it in enumerate(sorted(items, key=lambda z: z["yoy_pct"], reverse=True))]},
#         "calculation_mode": "YOY",
#     }

# def build_total_for_brand(cat, brands):
#     measure = random.choice(["value_sales","unit_sales"])
#     b = random.choice(brands)
#     val = float(np.random.uniform(8e5,2e6)) if measure=="unit_sales" else float(np.random.uniform(5e6,1.2e7))
#     # random full-year window
#     y = random.choice([2022, 2023, 2024])
#     return {
#         "mode": "BAR",
#         "measure": measure,
#         "window": {"start": month_start(y,1), "end": month_end(y,12)},
#         "dims": [],
#         "filters": {"category": cat, "brand": [b]},
#         "bar": {"x": "brand", "y": measure, "items": [{"rank": 1, "label": b, "value": val}]},
#         "calculation_mode": f"total {measure} sales",
#     }

# def build_trend_by_brand(cat, brands):
#     measure = random.choice(["value_sales","unit_sales"])
#     pick = random.sample(brands, min(len(brands), 3))
#     y = random.choice([2022, 2023, 2024])
#     by_brand=[]
#     for b in pick:
#         vals=[float(np.random.uniform(7e5,1.6e6)) if measure=="unit_sales" else float(np.random.uniform(6e6,1.8e7)) for _ in range(12)]
#         minm, maxm = np.argmin(vals)+1, np.argmax(vals)+1
#         by_brand.append({
#             "brand": b,
#             "min": {"value": float(min(vals)), "period": f"{y}-{minm:02d}", "label": month_label(y, minm)},
#             "max": {"value": float(max(vals)), "period": f"{y}-{maxm:02d}", "label": month_label(y, maxm)},
#         })
#     return {
#         "mode": "LINE",
#         "measure": measure,
#         "window": {"start": month_start(y,1), "end": month_end(y,12)},
#         "dims": ["brand"],
#         "filters": {"category": cat, "brand": pick},
#         "trend": {"measure": measure, "by_brand": by_brand,
#                   "overall": {
#                       "min": min((x["min"] for x in by_brand), key=lambda z: z["value"]),
#                       "max": max((x["max"] for x in by_brand), key=lambda z: z["value"]),
#                   }},
#         "calculation_mode": f"total {measure}",
#     }

# # -------- insight variants (3–4 sentences each) --------
# def insight_variants(payload):
#     cat = payload.get("filters", {}).get("category", "")
#     meas = payload.get("measure", "")
#     nice_meas = {"value_sales": "value sales", "unit_sales": "unit sales",
#                  "value_yoy": "value YoY", "unit_yoy": "unit YoY"}.get(meas, meas)

#     out = []

#     if payload["mode"] == "MAT_COMPARE":
#         periods = payload["mat_compare"]["periods"]
#         best = max(periods, key=lambda p: p.get("value_sales", p.get("unit_sales", 0)))
#         worst = min(periods, key=lambda p: p.get("value_sales", p.get("unit_sales", 0)))
#         out += [
#             f"In {cat}, the strongest {nice_meas} was in {best['mat_label']} and the weakest in {worst['mat_label']}.",
#             f"MAT comparison for {cat} shows {best['mat_label']} leading overall.",
#             f"{cat}: {best['mat_label']} outperformed {worst['mat_label']} on {nice_meas}.",
#             f"Across years, {cat} peaked at {best['mat_label']} for {nice_meas}.",
#         ]

#     elif payload["mode"] == "BAR" and "yoy" in payload:
#         items = payload["yoy"]["items"]
#         items_sorted = sorted(items, key=lambda x: x["yoy_pct"], reverse=True)
#         top = items_sorted[0]
#         last = items_sorted[-1]
#         out += [
#             f"In {cat}, {top['brand']} leads YoY with {top['yoy_pct']:.1%}.",
#             f"{top['brand']} shows the strongest YoY momentum in {cat}, while {last['brand']} trails.",
#             f"{cat} YoY snapshot: best is {top['brand']} at {top['yoy_pct']:.1%}.",
#             f"Year-over-year, {top['brand']} improved the most in {cat}.",
#         ]

#     elif payload["mode"] == "BAR" and "bar" in payload:
#         item = payload["bar"]["items"][0]
#         out += [
#             f"{cat}: {item['label']} total {nice_meas} is {item['value']:.0f}.",
#             f"Total {nice_meas} for {item['label']} in {cat} is {item['value']:.0f}.",
#             f"{item['label']} recorded {item['value']:.0f} in {nice_meas} for {cat}.",
#         ]

#     elif payload["mode"] == "LINE" and "trend" in payload:
#         bb = payload["trend"]["by_brand"]
#         best_peak = max(bb, key=lambda b: b["max"]["value"])
#         out += [
#             f"In {cat}, {best_peak['brand']} reached the highest monthly {nice_meas} at {best_peak['max']['label']}.",
#             f"Trend view ({cat}): {best_peak['brand']} shows the strongest monthly peak.",
#             f"{cat} trend: multiple brands vary month-to-month; {best_peak['brand']} peaks highest.",
#         ]

#     # cap at 4
#     return out[:4] if len(out) > 4 else out

# # -------- main driver --------
# if __name__=="__main__":
#     cats, brands_by_cat = load_entities(EXCEL_PATH)

#     Path(OUTPUT_JSONL).write_text("", encoding="utf-8")         # clear
#     Path(OUTPUT_PAIRS_JSONL).write_text("", encoding="utf-8")   # clear

#     with open(OUTPUT_JSONL, "a", encoding="utf-8") as f_payloads, \
#          open(OUTPUT_PAIRS_JSONL, "a", encoding="utf-8") as f_pairs:

#         total = 0
#         for cat in cats:
#             brands = brands_by_cat[cat]
#             for _ in range(N_SAMPLES_PER_TYPE):
#                 samples = [
#                     build_mat_compare(cat),
#                     build_yoy_by_brand(cat, brands),
#                     build_total_for_brand(cat, brands),
#                     build_trend_by_brand(cat, brands),
#                 ]
#                 for s in samples:
#                     insights = insight_variants(s)
#                     f_payloads.write(json.dumps(s) + "\n")
#                     f_pairs.write(json.dumps({"payload": s, "insights": insights}) + "\n")
#                     total += 1

#     print(f"Done. Wrote {total} payloads.")
#     print(f"• Payloads only: {OUTPUT_JSONL}")
#     print(f"• Payload + insights pairs: {OUTPUT_PAIRS_JSONL}")









# data_generator/data_generation.py
import json
import random
from datetime import date, datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# -----------------------------
# CONFIG
# -----------------------------
EXCEL_PATH = Path("./data/sample_nielsen_extended.xlsx")  # <-- update if needed
OUTPUT_PAYLOADS = Path("./data/outputs.json")
OUTPUT_PAIRS = Path("./data/output_pairs.json")

# how many samples per (category, type)
SAMPLES_PER_TYPE = 4

# random number bands (tweak to suit scale of your data)
VALUE_RANGE = (8e5, 2e6)     # monthly brand value_sales
UNIT_RANGE = (2e5, 8e5)      # monthly brand unit_sales

ANCHOR_MONTH = 9             # MAT ends at Sep by default (change if your FY differs)
RNG = random.Random(42)
NP_RNG = np.random.default_rng(42)


# -----------------------------
# HELPERS
# -----------------------------

import pandas as pd

# import pandas as pd
import pandas as pd
from pandas.tseries.offsets import MonthEnd

def month_end(year: int, month: int) -> pd.Timestamp:
    """Safe last day of (year, month)."""
    return pd.Timestamp(year, month, 1) + MonthEnd(0)

# def mat_period(year: int, anchor_month: int) -> tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT window for 'year' with anchor 'anchor_month'.
#     Example: anchor=9 (Sep) -> MAT 2025 = 2024-10-01 … 2025-09-30
#     """
#     start = pd.Timestamp(year - 1, anchor_month + 1, 1)
#     end   = month_end(year, anchor_month)
#     return start, end



# # ---------------- Safe date helpers ----------------
# import pandas as pd
# from pandas.tseries.offsets import MonthEnd

# import numpy as np
# import pandas as pd
# from pandas.tseries.offsets import MonthEnd

# def _mat_period(year: int, anchor_month: int) -> tuple[pd.Timestamp, pd.Timestamp]:
#     """
#     MAT <year> means the 12 months ending at <anchor_month> of <year>.
#     E.g., MAT 2025 (anchor 9) => 2024-10-01 .. 2025-09-30
#     """
#     start = pd.Timestamp(year - 1, anchor_month, 1)
#     end = pd.Timestamp(year, anchor_month, 1) + MonthEnd(0)  # last day of anchor month
#     return start, end


# # def mat_period(year: int, anchor_month: int):
# #     """
# #     Return the 12M MAT window for a given year and anchor_month.
# #     end = last day of anchor_month in 'year'
# #     start = first day of the month 11 months before 'end'
# #     """
# #     end = pd.Timestamp(year=int(year), month=int(anchor_month), day=1) + MonthEnd(0)
# #     start = (end - pd.DateOffset(months=11)).replace(day=1)
# #     return start, end

# def ytd_window(year: int, end_month: int):
#     """
#     Year-to-date window from Jan 1 to the *last* day of end_month in 'year'.
#     """
#     start = pd.Timestamp(year=int(year), month=1, day=1)
#     end = pd.Timestamp(year=int(year), month=int(end_month), day=1) + MonthEnd(0)
#     return start, end

# def _iso(d: pd.Timestamp) -> str:
#     return d.date().isoformat()


# def month_start(year: int, month: int) -> pd.Timestamp:
#     return pd.Timestamp(year, month, 1)

# # def month_end(year: int, month: int) -> pd.Timestamp:
# #     # last valid calendar day of that month
# #     return pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)

# def ytd_period(year: int, month: int):
#     start = pd.Timestamp(year, 1, 1)
#     end = month_end(year, month)
#     label = f"YTD {year}"
#     return start, end, label

# # def mat_period(year: int, anchor_month: int):
# #     end = month_end(year, anchor_month)
# #     start = (end - pd.DateOffset(months=11)).to_period("M").to_timestamp("start")
# #     label = f"MAT {year}"
# #     return start, end, label

# # def month_start(y: int, m: int) -> pd.Timestamp:
# #     # First day of that month
# #     return pd.Timestamp(y, m, 1)

# # def month_end(y: int, m: int) -> pd.Timestamp:
# #     # Last calendar day of that month
# #     return (pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(1))

# # def _month_start(d: date) -> date:
# #     return date(d.year, d.month, 1)

# def _rand_year_between(start: int, end: int) -> int:
#     return RNG.randint(start, end)

# def _rand_value(measure: str) -> float:
#     lo, hi = UNIT_RANGE if "unit" in measure else VALUE_RANGE
#     return float(NP_RNG.uniform(lo, hi))

# def _brands_by_category(df: pd.DataFrame) -> Dict[str, List[str]]:
#     # assumes columns: category, brand
#     out: Dict[str, List[str]] = {}
#     for cat, g in df.groupby("category"):
#         names = sorted(set(map(str, g["brand"].dropna().tolist())))
#         if names:
#             out[cat] = names
#     return out

# def _some_brands(brands: List[str], k: int) -> List[str]:
#     k = max(1, min(k, len(brands)))
#     return RNG.sample(brands, k)

# def _window_str(start: date, end: date) -> Dict[str, str]:
#     return {"start": start.isoformat(), "end": end.isoformat()}

# def _yoy_items(brands: List[str], measure: str) -> List[Dict]:
#     items = []
#     for b in brands:
#         prev = _rand_value(measure)
#         curr = prev * (1.0 + NP_RNG.normal(0.03, 0.05))  # ±5% around +3%
#         yoy = (curr / prev) - 1.0 if prev > 0 else 0.0
#         items.append({"curr": round(curr, 2), "prev": round(prev, 2), "yoy_pct": float(yoy), "brand": b})
#     return items

# def _trend_block(brands: List[str], measure: str, start: date, end: date) -> Dict:
#     # produce per-brand min/max within the window; values synthetic
#     months = pd.period_range(start=_month_start(start), end=_month_start(end), freq="M")
#     by_brand = []
#     overall_vals = []
#     for b in brands:
#         series = [_rand_value(measure) for _ in months]
#         overall_vals.extend(series)
#         # pick min/max
#         a = int(np.argmin(series))
#         z = int(np.argmax(series))
#         by_brand.append({
#             "brand": b,
#             "min": {"value": round(series[a], 2), "period": str(months[a]).replace("-", ""), "label": months[a].strftime("%b %Y")},
#             "max": {"value": round(series[z], 2), "period": str(months[z]).replace("-", ""), "label": months[z].strftime("%b %Y")},
#         })
#     a = int(np.argmin(overall_vals))
#     z = int(np.argmax(overall_vals))
#     # map overall indices to months
#     M = len(months)
#     # a//M is fine since we appended per brand; we can just use months[a % M]
#     min_m = months[a % M]
#     max_m = months[z % M]
#     overall = {
#         "min": {"value": round(sorted(overall_vals)[0], 2), "period": str(min_m).replace("-", ""), "label": min_m.strftime("%b %Y")},
#         "max": {"value": round(sorted(overall_vals)[-1], 2), "period": str(max_m).replace("-", ""), "label": max_m.strftime("%b %Y")},
#     }
#     return {"measure": measure, "by_brand": by_brand, "overall": overall}

# def _mat_period(year: int, anchor_month: int) -> Tuple[date, date, str]:
#     """Return start,end,label for MAT <year> with anchor month (e.g., Sep)."""
#     end = date(year, anchor_month, 30 if anchor_month in (4, 6, 9, 11) else 31)
#     # safer: use pandas to get last day of month
#     end = pd.Period(end, freq="M").to_timestamp(how="end").date()
#     start = pd.Period(end, freq="M").asfreq("M", how="end") - 11
#     start_d = pd.Period(start, freq="M").to_timestamp(how="start").date()
#     label = f"MAT {year}"
#     return start_d, end, label

# def _rank_and_sort(items: List[Dict], key: str, descending: bool = True) -> List[Dict]:
#     items = sorted(items, key=lambda x: x[key], reverse=descending)
#     for i, it in enumerate(items, start=1):
#         it["rank"] = i
#     return items


# # -----------------------------
# # BUILDERS (exact JSON shapes)
# # -----------------------------

# # ---------------- Common aggregator ----------------
# def _sum_measure(df, category: str, brand: str | None, measure: str,
#                  start: pd.Timestamp, end: pd.Timestamp) -> float:
#     """
#     Sum 'measure' for rows between [start, end] inclusive, with category filter
#     and optional brand filter.
#     """
#     mask = (df["date"] >= start) & (df["date"] <= end) & (df["category"].str.lower()==category.lower())
#     if brand is not None:
#         mask &= (df["brand"].str.lower()==brand.lower())
#     return float(pd.to_numeric(df.loc[mask, measure], errors="coerce").fillna(0).sum())






# # ===================================================
# # MAT COMPARE (ranked)  e.g. "MAT 2025 vs MAT 2024 vs MAT 2023"
# # ===================================================
# def build_mat_compare_exact(df,
#     cat: str,
#     measure: str,
#     years: list[int],
#     anchor_month: int = 9
# ) -> dict:
#     """
#     Synthetic MAT comparison payload (no dataframe required).
#     Produces the same JSON shape you showed earlier, including ranked periods.
#     """
#     periods = []
#     for y in years:
#         start, end,_ = _mat_period(y, anchor_month)
#         total = float(np.random.uniform(5.2e7, 6.3e7))  # synthetic total for this MAT
#         periods.append({
#             "mat_label": f"MAT {y}",
#             "start": start.strftime("%Y-%m-%d"),
#             "end":   end.strftime("%Y-%m-%d"),
#             measure: round(total, 2),
#             "rank": None,  # will fill after sorting
#         })

#     # rank by measure (desc)
#     periods = sorted(periods, key=lambda x: x[measure], reverse=True)
#     for r, p in enumerate(periods, 1):
#         p["rank"] = r

#     overall_start = periods[-1]["start"]
#     overall_end   = periods[0]["end"]

#     return {
#         "mode": "MAT_COMPARE",
#         "measure": measure,
#         "window": {"start": overall_start, "end": overall_end},
#         "dims": ["mat_label"],
#         "filters": {"category": cat},
#         "mat_compare": {
#             "mat_compare": {
#                 "anchor_month": anchor_month,
#                 "years": years,
#                 "labels": [f"MAT {y}" for y in years],
#             },
#             "window": {"start": overall_start, "end": overall_end},
#             "dims": ["mat_label"],
#             "measure": measure,
#             "filters": {"category": cat},
#             "mode": "MAT_COMPARE",
#             "rowcount": len(periods),
#             "chart_type": "bar",
#             "periods": periods
#         },
#         "calculation_mode": "mat_compare"
#     }

    
# def build_line_trend_exact(df,cat: str, brands: List[str], measure: str) -> Dict:
#     """
#     Trend over a year (min/max by brand).
#     """
#     start = pd.Timestamp(2022, 1, 1)
#     end = pd.Timestamp(2022, 12, 31)

#     by_brand = []
#     for b in brands[:3]:  # pick 3 brands
#         vals = np.random.randint(800000, 1500000, size=12)
#         min_idx = vals.argmin()
#         max_idx = vals.argmax()
#         by_brand.append({
#             "brand": b,
#             "min": {"value": float(vals[min_idx]), "period": f"2022-{min_idx+1:02d}", "label": f"{pd.Timestamp(2022, min_idx+1, 1).strftime('%b %Y')}"},
#             "max": {"value": float(vals[max_idx]), "period": f"2022-{max_idx+1:02d}", "label": f"{pd.Timestamp(2022, max_idx+1, 1).strftime('%b %Y')}"}
#         })

#     payload = {
#         "mode": "LINE",
#         "measure": measure,
#         "window": {"start": str(start.date()), "end": str(end.date())},
#         "dims": ["brand"],
#         "filters": {"brand": brands[:3]},
#         "trend": {
#             "measure": measure,
#             "by_brand": by_brand,
#             "overall": {
#                 "min": min([x["min"] for x in by_brand], key=lambda v: v["value"]),
#                 "max": max([x["max"] for x in by_brand], key=lambda v: v["value"])
#             }
#         },
#         "calculation_mode": f"total {measure} sales"
#     }
#     return payload

# # ===================================================
# # MAT YoY by brand  e.g. MAT(2025) vs MAT(2024)
# # ===================================================
# def build_mat_yoy_exact(df, category: str, brands: list[str],
#                         measure: str, year: int, anchor_month: int = 9) -> dict:
#     curr_start, curr_end,lbl = _mat_period(year, anchor_month)
#     prev_start, prev_end,lbl = _mat_period(year-1, anchor_month)
#     # print(_mat_period(year, anchor_month))
#     import sys
#     sys.exit(0)

#     items = []
#     for b in brands:
#         curr_total = _sum_measure(df, category, b, measure, curr_start, curr_end)
#         prev_total = _sum_measure(df, category, b, measure, prev_start, prev_end)
#         yoy = (curr_total / prev_total - 1.0) if prev_total else 0.0
#         items.append({
#             "brand": b,
#             "curr": curr_total,
#             "prev": prev_total,
#             "yoy_pct": yoy,
#             "curr_label": f"MAT {year}",
#             "prev_label": f"MAT {year-1}",
#             "curr_start": _iso(curr_start),
#             "curr_end": _iso(curr_end),
#             "prev_start": _iso(prev_start),
#             "prev_end": _iso(prev_end),
#         })

#     # Rank by YoY% desc
#     ranked = sorted(items, key=lambda x: x["yoy_pct"], reverse=True)
#     bar = {
#         "x": "brand",
#         "y": f"{'unit' if 'unit' in measure else 'value'}_yoy",
#         "items": [{"rank": i+1, "label": it["brand"], "value": it["yoy_pct"]} for i, it in enumerate(ranked)]
#     }

#     payload = {
#         "mode": "BAR",
#         "measure": f"{'unit' if 'unit' in measure else 'value'}_yoy",
#         "window": {"start": _iso(prev_start), "end": _iso(curr_end)},
#         "dims": ["brand"],
#         "filters": {"category": category},
#         "yoy": {"measure_type": "unit" if "unit" in measure else "value", "items": items},
#         "bar": bar,
#         "calculation_mode": "MAT_YOY",
#         "mat": {
#             "anchor_month": anchor_month,
#             "years": [year, year-1],
#             "labels": [f"MAT {year}", f"MAT {year-1}"]
#         }
#     }
#     return payload

# def build_total_exact(df,cat: str, brands: List[str], measure: str,
#                       start: date, end: date) -> Dict:
#     """
#     Match: total unit/value sales for selected brand(s) in a window.
#     Shape like your example #6.
#     """
#     picked = _some_brands(brands, 1)
#     total = sum(_rand_value(measure) for _ in range(12))
#     bar_items = [{"rank": 1, "label": picked[0], "value": round(total, 2)}]
#     payload = {
#         "mode": "BAR",
#         "measure": measure,
#         "window": _window_str(start, end),
#         "dims": [],
#         "filters": {"category": cat, "brand": picked},
#         "bar": {"x": "brand", "y": measure, "items": bar_items},
#         "calculation_mode": f"total {measure} sales",
#     }
#     return payload

# def build_yoy_exact(df,cat: str, brands: List[str], measure: str,
#                     start: date, end: date) -> Dict:
#     """
#     Match: YoY by brand within [start,end], like example #2.
#     """
#     picked = _some_brands(brands, 2)
#     items = _yoy_items(picked, measure)
#     bar = _rank_and_sort([{"label": x["brand"], "value": x["yoy_pct"]} for x in items], "value")
#     payload = {
#         "mode": "BAR",
#         "measure": f"{'unit' if 'unit' in measure else 'value'}_yoy",
#         "window": _window_str(start, end),
#         "dims": ["brand"],
#         "filters": {"category": cat},
#         "yoy": {"measure_type": "unit" if "unit" in measure else "value", "items": items},
#         "bar": {"x": "brand", "y": f"{'unit' if 'unit' in measure else 'value'}_yoy", "items": bar},
#         "calculation_mode": "YOY",
#     }
#     return payload

# from typing import List, Dict

# # ===================================================
# # YTD YoY by brand  (Jan->chosen month) for a given year
# # ===================================================
# def build_ytd_yoy_exact(df, category: str, brands: list[str],
#                         measure: str, year: int, end_month: int) -> dict:
#     curr_start, curr_end = ytd_window(year, end_month)
#     prev_start, prev_end = ytd_window(year-1, end_month)

#     items = []
#     for b in brands:
#         curr_total = _sum_measure(df, category, b, measure, curr_start, curr_end)
#         prev_total = _sum_measure(df, category, b, measure, prev_start, prev_end)
#         yoy = (curr_total / prev_total - 1.0) if prev_total else 0.0
#         items.append({
#             "brand": b,
#             "curr": curr_total,
#             "prev": prev_total,
#             "yoy_pct": yoy,
#             "curr_label": f"YTD {year} (Jan–{pd.Timestamp(year, end_month, 1).strftime('%b')})",
#             "prev_label": f"YTD {year-1} (Jan–{pd.Timestamp(year-1, end_month, 1).strftime('%b')})",
#             "curr_start": _iso(curr_start),
#             "curr_end": _iso(curr_end),
#             "prev_start": _iso(prev_start),
#             "prev_end": _iso(prev_end),
#         })

#     # Rank by YoY% desc
#     ranked = sorted(items, key=lambda x: x["yoy_pct"], reverse=True)
#     bar = {
#         "x": "brand",
#         "y": f"{'unit' if 'unit' in measure else 'value'}_yoy",
#         "items": [{"rank": i+1, "label": it["brand"], "value": it["yoy_pct"]} for i, it in enumerate(ranked)]
#     }

#     payload = {
#         "mode": "BAR",
#         "measure": f"{'unit' if 'unit' in measure else 'value'}_yoy",
#         "window": {"start": _iso(prev_start), "end": _iso(curr_end)},
#         "dims": ["brand"],
#         "filters": {"category": category},
#         "yoy": {"measure_type": "unit" if "unit" in measure else "value", "items": items},
#         "bar": bar,
#         "calculation_mode": "YTD_YOY",
#         "ytd": {
#             "end_month": end_month,
#             "years": [year, year-1]
#         }
#     }
#     return payload

# # -----------------------------
# # INSIGHT VARIANTS
# # -----------------------------
# def insight_variants(payload: Dict) -> List[str]:
#     cat = payload.get("filters", {}).get("category", "")
#     mode = payload.get("mode")
#     meas = payload.get("measure", "")
#     nice_meas = "unit sales" if "unit" in meas else ("value sales" if "value" in meas else meas)

#     out: List[str] = []

#     if mode == "MAT_COMPARE":
#         periods = payload["mat_compare"]["periods"]
#         top = max(periods, key=lambda x: x.get(meas, 0.0))
#         low = min(periods, key=lambda x: x.get(meas, 0.0))
#         out.append(f"In {cat}, {top['mat_label']} led {nice_meas} ({top[meas]:,.0f}), ahead of {low['mat_label']} ({low[meas]:,.0f}).")
#         out.append(f"Across MATs, the range for {nice_meas} was {low[meas]:,.0f}–{top[meas]:,.0f}.")
#         out.append(f"Best MAT window: {top['mat_label']} (ends {top['end']}).")

#     elif mode == "BAR" and "yoy" in payload:
#         items = payload["yoy"]["items"]
#         best = max(items, key=lambda x: x["yoy_pct"])
#         worst = min(items, key=lambda x: x["yoy_pct"])
#         out.append(f"{best['brand']} shows the strongest YoY on {nice_meas} at {best['yoy_pct']*100:.1f}%.")
#         out.append(f"{worst['brand']} trails with {worst['yoy_pct']*100:.1f}% YoY.")
#         out.append(f"YoY spread is {(best['yoy_pct']-worst['yoy_pct'])*100:.1f} p.p.")

#     elif mode == "BAR" and "bar" in payload and payload["bar"]["items"]:
#         b0 = payload["bar"]["items"][0]
#         out.append(f"Total {nice_meas} for {b0['label']} is {b0['value']:,.0f}.")
#         out.append(f"Within {cat}, {b0['label']} contributes the shown total for the selected period.")

#     elif mode == "LINE" and "trend" in payload:
#         tr = payload["trend"]
#         overall = tr["overall"]
#         out.append(f"{nice_meas.capitalize()} bottomed in {overall['min']['label']} and peaked in {overall['max']['label']}.")
#         if tr.get("by_brand"):
#             b = tr["by_brand"][0]
#             out.append(f"For {b['brand']}, min was {b['min']['label']} and max was {b['max']['label']}.")
#         out.append("Seasonality is visible across the window.")

#     return out


# # -----------------------------
# # MAIN DRIVER
# # -----------------------------
# @dataclass
# class SourceMeta:
#     categories: List[str]
#     brands_by_cat: Dict[str, List[str]]

# def load_names_from_excel(path: Path) -> SourceMeta:
#     df = pd.read_excel(path)
#     # ensure expected columns exist (category, brand)
#     if "category" not in df.columns or "brand" not in df.columns:
#         raise ValueError("Excel must contain columns: 'category' and 'brand'")
#     cats = sorted(set(map(str, df["category"].dropna().tolist())))
#     return SourceMeta(categories=cats, brands_by_cat=_brands_by_category(df[["category", "brand"]]))

# def main():
#     df=pd.read_excel("./data/sample_nielsen_extended.xlsx")
#     meta = load_names_from_excel(EXCEL_PATH)

#     OUTPUT_PAYLOADS.parent.mkdir(parents=True, exist_ok=True)

#     total_written = 0
#     with OUTPUT_PAYLOADS.open("w", encoding="utf-8") as f_payloads, \
#          OUTPUT_PAIRS.open("w", encoding="utf-8") as f_pairs:

#         for cat in meta.categories:
#             brands = meta.brands_by_cat.get(cat, [])
#             if not brands:
#                 continue

#             for _ in range(SAMPLES_PER_TYPE):
#                 # choose windows
#                 y = _rand_year_between(2022, 2025)
#                 start = date(y, 1, 1)
#                 end = date(y, 12, 31)

#                 # measures flip
#                 measure = "unit_sales" if RNG.random() < 0.5 else "value_sales"

#                 samples = [
#                     build_mat_compare_exact(df,cat, "value_sales", years=[2025, 2024, 2023]),
#                     build_yoy_exact(df,cat, brands, measure, start, end),
#                     build_ytd_yoy_exact(df,cat, brands, measure, year=2025,end_month=8),
#                     build_total_exact(df,cat, brands, measure, start, end),
#                     build_mat_yoy_exact(df,cat, brands, measure, year=2025),  # <-- ADD THIS
#                     build_line_trend_exact(df,cat, brands, "value_sales", date(2022, 1, 1), date(2022, 12, 31)),
#                 ]

#                 for s in samples:
#                     insights = insight_variants(s)
#                     # write payloads.jsonl
#                     f_payloads.write(json.dumps(s) + "\n")
#                     # write paired jsonl
#                     f_pairs.write(json.dumps({"payload": s, "insights": insights}) + "\n")
#                     total_written += 1

#     print(f"Done. Wrote {total_written} payloads.")
#     print(f"- Payloads only: {OUTPUT_PAYLOADS}")
#     print(f"- Payload + insights pairs: {OUTPUT_PAIRS}")


# if __name__ == "__main__":
#     main()









# ---------------- Safe date helpers ----------------
import pandas as pd
from pandas.tseries.offsets import MonthEnd

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd

import pandas as pd

def _mat_period(year: int, anchor_month: int):
    """
    Return MAT start, end, label.
    Example: MAT 2025 with anchor_month=9 => Oct 2024 to Sep 2025
    """
    end = pd.Timestamp(year=year, month=anchor_month, day=1) + pd.offsets.MonthEnd(1)
    start = (end - pd.offsets.MonthEnd(12)) + pd.offsets.MonthBegin(1)
    return start.date(), end.date(), f"MAT {year}"


# def mat_period(year: int, anchor_month: int):
#     """
#     Return the 12M MAT window for a given year and anchor_month.
#     end = last day of anchor_month in 'year'
#     start = first day of the month 11 months before 'end'
#     """
#     end = pd.Timestamp(year=int(year), month=int(anchor_month), day=1) + MonthEnd(0)
#     start = (end - pd.DateOffset(months=11)).replace(day=1)
#     return start, end

def ytd_window(year: int, end_month: int):
    """
    Year-to-date window from Jan 1 to the *last* day of end_month in 'year'.
    """
    start = pd.Timestamp(year=int(year), month=1, day=1)
    end = pd.Timestamp(year=int(year), month=int(end_month), day=1) + MonthEnd(0)
    return start, end

def _iso(d: pd.Timestamp) -> str:
    return d.date().isoformat()


def month_start(year: int, month: int) -> pd.Timestamp:
    return pd.Timestamp(year, month, 1)

# def month_end(year: int, month: int) -> pd.Timestamp:
#     # last valid calendar day of that month
#     return pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)

def ytd_period(year: int, end_month: int):
    """
    Return YTD start, end, label.
    Example: YTD 2025 (end_month=9) => Jan 2025 to Sep 2025
    """
    end = pd.Timestamp(year=year, month=end_month, day=1) + pd.offsets.MonthEnd(1)
    start = pd.Timestamp(year=year, month=1, day=1)
    return start.date(), end.date(), f"YTD {year} (to {end.strftime('%b')})"

# def mat_period(year: int, anchor_month: int):
#     end = month_end(year, anchor_month)
#     start = (end - pd.DateOffset(months=11)).to_period("M").to_timestamp("start")
#     label = f"MAT {year}"
#     return start, end, label

# def month_start(y: int, m: int) -> pd.Timestamp:
#     # First day of that month
#     return pd.Timestamp(y, m, 1)

# def month_end(y: int, m: int) -> pd.Timestamp:
#     # Last calendar day of that month
#     return (pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(1))

# def _month_start(d: date) -> date:
#     return date(d.year, d.month, 1)

def _rand_year_between(start: int, end: int) -> int:
    return RNG.randint(start, end)

def _rand_value(measure: str) -> float:
    lo, hi = UNIT_RANGE if "unit" in measure else VALUE_RANGE
    return float(NP_RNG.uniform(lo, hi))

def _brands_by_category(df: pd.DataFrame) -> Dict[str, List[str]]:
    # assumes columns: category, brand
    out: Dict[str, List[str]] = {}
    for cat, g in df.groupby("category"):
        names = sorted(set(map(str, g["brand"].dropna().tolist())))
        if names:
            out[cat] = names
    return out

def _some_brands(brands: List[str], k: int) -> List[str]:
    k = max(1, min(k, len(brands)))
    return RNG.sample(brands, k)

def _window_str(start: date, end: date) -> Dict[str, str]:
    return {"start": start.isoformat(), "end": end.isoformat()}

def _yoy_items(brands: List[str], measure: str) -> List[Dict]:
    items = []
    for b in brands:
        prev = _rand_value(measure)
        curr = prev * (1.0 + NP_RNG.normal(0.03, 0.05))  # ±5% around +3%
        yoy = (curr / prev) - 1.0 if prev > 0 else 0.0
        items.append({"curr": round(curr, 2), "prev": round(prev, 2), "yoy_pct": float(yoy), "brand": b})
    return items

def _trend_block(brands: List[str], measure: str, start: date, end: date) -> Dict:
    # produce per-brand min/max within the window; values synthetic
    months = pd.period_range(start=_month_start(start), end=_month_start(end), freq="M")
    by_brand = []
    overall_vals = []
    for b in brands:
        series = [_rand_value(measure) for _ in months]
        overall_vals.extend(series)
        # pick min/max
        a = int(np.argmin(series))
        z = int(np.argmax(series))
        by_brand.append({
            "brand": b,
            "min": {"value": round(series[a], 2), "period": str(months[a]).replace("-", ""), "label": months[a].strftime("%b %Y")},
            "max": {"value": round(series[z], 2), "period": str(months[z]).replace("-", ""), "label": months[z].strftime("%b %Y")},
        })
    a = int(np.argmin(overall_vals))
    z = int(np.argmax(overall_vals))
    # map overall indices to months
    M = len(months)
    # a//M is fine since we appended per brand; we can just use months[a % M]
    min_m = months[a % M]
    max_m = months[z % M]
    overall = {
        "min": {"value": round(sorted(overall_vals)[0], 2), "period": str(min_m).replace("-", ""), "label": min_m.strftime("%b %Y")},
        "max": {"value": round(sorted(overall_vals)[-1], 2), "period": str(max_m).replace("-", ""), "label": max_m.strftime("%b %Y")},
    }
    return {"measure": measure, "by_brand": by_brand, "overall": overall}

def _mat_period(year: int, anchor_month: int) -> Tuple[date, date, str]:
    """Return start,end,label for MAT <year> with anchor month (e.g., Sep)."""
    end = date(year, anchor_month, 30 if anchor_month in (4, 6, 9, 11) else 31)
    # safer: use pandas to get last day of month
    end = pd.Period(end, freq="M").to_timestamp(how="end").date()
    start = pd.Period(end, freq="M").asfreq("M", how="end") - 11
    start_d = pd.Period(start, freq="M").to_timestamp(how="start").date()
    label = f"MAT {year}"
    return start_d, end, label

def _rank_and_sort(items: List[Dict], key: str, descending: bool = True) -> List[Dict]:
    items = sorted(items, key=lambda x: x[key], reverse=descending)
    for i, it in enumerate(items, start=1):
        it["rank"] = i
    return items


# -----------------------------
# BUILDERS (exact JSON shapes)
# -----------------------------

# ---------------- Common aggregator ----------------
def _sum_measure(df, category: str, brand: str | None, measure: str,
                 start: pd.Timestamp, end: pd.Timestamp) -> float:
    """
    Sum 'measure' for rows between [start, end] inclusive, with category filter
    and optional brand filter.
    """
    mask = (df["date"] >= start) & (df["date"] <= end) & (df["category"].str.lower()==category.lower())
    if brand is not None:
        mask &= (df["brand"].str.lower()==brand.lower())
    return float(pd.to_numeric(df.loc[mask, measure], errors="coerce").fillna(0).sum())






# ===================================================
# MAT COMPARE (ranked)  e.g. "MAT 2025 vs MAT 2024 vs MAT 2023"
# ===================================================

def build_mat_compare_exact(
    df: pd.DataFrame,
    cat: str,
    measure: str,
    years: list[int],
    anchor_month: int = 9,
) -> dict:
    periods = []

    # build one period per year
    for y in years:
        start, end, label = _mat_period(y, anchor_month)  # <-- unpack 3 values
        mask = (
            (df["category"].str.lower() == cat.lower())
            & (df["date"] >= pd.Timestamp(start))
            & (df["date"] <= pd.Timestamp(end))
        )
        total = float(df.loc[mask, measure].sum())

        periods.append({
            "mat_label": label,
            "start": str(start),
            "end": str(end),
            measure: total,
        })

    # rank by total (desc)
    periods = sorted(periods, key=lambda x: x[measure], reverse=True)
    for i, p in enumerate(periods, start=1):
        p["rank"] = i

    # overall window (min start, max end)
    overall_start = min(pd.to_datetime(p["start"]) for p in periods).date().isoformat()
    overall_end   = max(pd.to_datetime(p["end"])   for p in periods).date().isoformat()

    return {
        "mode": "MAT_COMPARE",
        "measure": measure,
        "window": {"start": overall_start, "end": overall_end},
        "dims": ["mat_label"],
        "filters": {"category": cat},
        "mat_compare": {
            "anchor_month": anchor_month,
            "years": years,
            "labels": [f"MAT {y}" for y in years],
        },
        "rowcount": len(periods),
        "chart_type": "bar",
        "periods": periods,
    }
    
def build_line_trend_exact(df,cat: str, brands: List[str], measure: str) -> Dict:
    """
    Trend over a year (min/max by brand).
    """
    start = pd.Timestamp(2022, 1, 1)
    end = pd.Timestamp(2022, 12, 31)

    by_brand = []
    for b in brands[:3]:  # pick 3 brands
        vals = np.random.randint(800000, 1500000, size=12)
        min_idx = vals.argmin()
        max_idx = vals.argmax()
        by_brand.append({
            "brand": b,
            "min": {"value": float(vals[min_idx]), "period": f"2022-{min_idx+1:02d}", "label": f"{pd.Timestamp(2022, min_idx+1, 1).strftime('%b %Y')}"},
            "max": {"value": float(vals[max_idx]), "period": f"2022-{max_idx+1:02d}", "label": f"{pd.Timestamp(2022, max_idx+1, 1).strftime('%b %Y')}"}
        })

    payload = {
        "mode": "LINE",
        "measure": measure,
        "window": {"start": str(start.date()), "end": str(end.date())},
        "dims": ["brand"],
        "filters": {"brand": brands[:3]},
        "trend": {
            "measure": measure,
            "by_brand": by_brand,
            "overall": {
                "min": min([x["min"] for x in by_brand], key=lambda v: v["value"]),
                "max": max([x["max"] for x in by_brand], key=lambda v: v["value"])
            }
        },
        "calculation_mode": f"total {measure} sales"
    }
    return payload

# ===================================================
# MAT YoY by brand  e.g. MAT(2025) vs MAT(2024)
# ===================================================
def build_mat_yoy_exact(df, category: str, brands: list[str],
                        measure: str, year: int, anchor_month: int = 9) -> dict:
    curr_start, curr_end,lbl = _mat_period(year, anchor_month)
    prev_start, prev_end,lbl = _mat_period(year-1, anchor_month)
    # print(_mat_period(year, anchor_month))
    import sys
    sys.exit(0)

    items = []
    for b in brands:
        curr_total = _sum_measure(df, category, b, measure, curr_start, curr_end)
        prev_total = _sum_measure(df, category, b, measure, prev_start, prev_end)
        yoy = (curr_total / prev_total - 1.0) if prev_total else 0.0
        items.append({
            "brand": b,
            "curr": curr_total,
            "prev": prev_total,
            "yoy_pct": yoy,
            "curr_label": f"MAT {year}",
            "prev_label": f"MAT {year-1}",
            "curr_start": _iso(curr_start),
            "curr_end": _iso(curr_end),
            "prev_start": _iso(prev_start),
            "prev_end": _iso(prev_end),
        })

    # Rank by YoY% desc
    ranked = sorted(items, key=lambda x: x["yoy_pct"], reverse=True)
    bar = {
        "x": "brand",
        "y": f"{'unit' if 'unit' in measure else 'value'}_yoy",
        "items": [{"rank": i+1, "label": it["brand"], "value": it["yoy_pct"]} for i, it in enumerate(ranked)]
    }

    payload = {
        "mode": "BAR",
        "measure": f"{'unit' if 'unit' in measure else 'value'}_yoy",
        "window": {"start": _iso(prev_start), "end": _iso(curr_end)},
        "dims": ["brand"],
        "filters": {"category": category},
        "yoy": {"measure_type": "unit" if "unit" in measure else "value", "items": items},
        "bar": bar,
        "calculation_mode": "MAT_YOY",
        "mat": {
            "anchor_month": anchor_month,
            "years": [year, year-1],
            "labels": [f"MAT {year}", f"MAT {year-1}"]
        }
    }
    return payload

def build_total_exact(df,cat: str, brands: List[str], measure: str,
                      start: date, end: date) -> Dict:
    """
    Match: total unit/value sales for selected brand(s) in a window.
    Shape like your example #6.
    """
    picked = _some_brands(brands, 1)
    total = sum(_rand_value(measure) for _ in range(12))
    bar_items = [{"rank": 1, "label": picked[0], "value": round(total, 2)}]
    payload = {
        "mode": "BAR",
        "measure": measure,
        "window": _window_str(start, end),
        "dims": [],
        "filters": {"category": cat, "brand": picked},
        "bar": {"x": "brand", "y": measure, "items": bar_items},
        "calculation_mode": f"total {measure} sales",
    }
    return payload

def build_yoy_exact(df,cat: str, brands: List[str], measure: str,
                    start: date, end: date) -> Dict:
    """
    Match: YoY by brand within [start,end], like example #2.
    """
    picked = _some_brands(brands, 2)
    items = _yoy_items(picked, measure)
    bar = _rank_and_sort([{"label": x["brand"], "value": x["yoy_pct"]} for x in items], "value")
    payload = {
        "mode": "BAR",
        "measure": f"{'unit' if 'unit' in measure else 'value'}_yoy",
        "window": _window_str(start, end),
        "dims": ["brand"],
        "filters": {"category": cat},
        "yoy": {"measure_type": "unit" if "unit" in measure else "value", "items": items},
        "bar": {"x": "brand", "y": f"{'unit' if 'unit' in measure else 'value'}_yoy", "items": bar},
        "calculation_mode": "YOY",
    }
    return payload

from typing import List, Dict

# ===================================================
# YTD YoY by brand  (Jan->chosen month) for a given year
# ===================================================
def build_ytd_yoy_exact(df, category: str, brands: list[str],
                        measure: str, year: int, end_month: int) -> dict:
    curr_start, curr_end = ytd_window(year, end_month)
    prev_start, prev_end = ytd_window(year-1, end_month)

    items = []
    for b in brands:
        curr_total = _sum_measure(df, category, b, measure, curr_start, curr_end)
        prev_total = _sum_measure(df, category, b, measure, prev_start, prev_end)
        yoy = (curr_total / prev_total - 1.0) if prev_total else 0.0
        items.append({
            "brand": b,
            "curr": curr_total,
            "prev": prev_total,
            "yoy_pct": yoy,
            "curr_label": f"YTD {year} (Jan–{pd.Timestamp(year, end_month, 1).strftime('%b')})",
            "prev_label": f"YTD {year-1} (Jan–{pd.Timestamp(year-1, end_month, 1).strftime('%b')})",
            "curr_start": _iso(curr_start),
            "curr_end": _iso(curr_end),
            "prev_start": _iso(prev_start),
            "prev_end": _iso(prev_end),
        })

    # Rank by YoY% desc
    ranked = sorted(items, key=lambda x: x["yoy_pct"], reverse=True)
    bar = {
        "x": "brand",
        "y": f"{'unit' if 'unit' in measure else 'value'}_yoy",
        "items": [{"rank": i+1, "label": it["brand"], "value": it["yoy_pct"]} for i, it in enumerate(ranked)]
    }

    payload = {
        "mode": "BAR",
        "measure": f"{'unit' if 'unit' in measure else 'value'}_yoy",
        "window": {"start": _iso(prev_start), "end": _iso(curr_end)},
        "dims": ["brand"],
        "filters": {"category": category},
        "yoy": {"measure_type": "unit" if "unit" in measure else "value", "items": items},
        "bar": bar,
        "calculation_mode": "YTD_YOY",
        "ytd": {
            "end_month": end_month,
            "years": [year, year-1]
        }
    }
    return payload

# -----------------------------
# INSIGHT VARIANTS
# -----------------------------
def insight_variants(payload: Dict) -> List[str]:
    cat = payload.get("filters", {}).get("category", "")
    mode = payload.get("mode")
    meas = payload.get("measure", "")
    nice_meas = "unit sales" if "unit" in meas else ("value sales" if "value" in meas else meas)

    out: List[str] = []

    if mode == "MAT_COMPARE":
        periods = payload["mat_compare"]["periods"]
        top = max(periods, key=lambda x: x.get(meas, 0.0))
        low = min(periods, key=lambda x: x.get(meas, 0.0))
        out.append(f"In {cat}, {top['mat_label']} led {nice_meas} ({top[meas]:,.0f}), ahead of {low['mat_label']} ({low[meas]:,.0f}).")
        out.append(f"Across MATs, the range for {nice_meas} was {low[meas]:,.0f}–{top[meas]:,.0f}.")
        out.append(f"Best MAT window: {top['mat_label']} (ends {top['end']}).")

    elif mode == "BAR" and "yoy" in payload:
        items = payload["yoy"]["items"]
        best = max(items, key=lambda x: x["yoy_pct"])
        worst = min(items, key=lambda x: x["yoy_pct"])
        out.append(f"{best['brand']} shows the strongest YoY on {nice_meas} at {best['yoy_pct']*100:.1f}%.")
        out.append(f"{worst['brand']} trails with {worst['yoy_pct']*100:.1f}% YoY.")
        out.append(f"YoY spread is {(best['yoy_pct']-worst['yoy_pct'])*100:.1f} p.p.")

    elif mode == "BAR" and "bar" in payload and payload["bar"]["items"]:
        b0 = payload["bar"]["items"][0]
        out.append(f"Total {nice_meas} for {b0['label']} is {b0['value']:,.0f}.")
        out.append(f"Within {cat}, {b0['label']} contributes the shown total for the selected period.")

    elif mode == "LINE" and "trend" in payload:
        tr = payload["trend"]
        overall = tr["overall"]
        out.append(f"{nice_meas.capitalize()} bottomed in {overall['min']['label']} and peaked in {overall['max']['label']}.")
        if tr.get("by_brand"):
            b = tr["by_brand"][0]
            out.append(f"For {b['brand']}, min was {b['min']['label']} and max was {b['max']['label']}.")
        out.append("Seasonality is visible across the window.")

    return out


# -----------------------------
# MAIN DRIVER
# -----------------------------
@dataclass
class SourceMeta:
    categories: List[str]
    brands_by_cat: Dict[str, List[str]]

def load_names_from_excel(path: Path) -> SourceMeta:
    df = pd.read_excel(path)
    # ensure expected columns exist (category, brand)
    if "category" not in df.columns or "brand" not in df.columns:
        raise ValueError("Excel must contain columns: 'category' and 'brand'")
    cats = sorted(set(map(str, df["category"].dropna().tolist())))
    return SourceMeta(categories=cats, brands_by_cat=_brands_by_category(df[["category", "brand"]]))

def main():
    df=pd.read_excel("./data/sample_nielsen_extended.xlsx")
    meta = load_names_from_excel(EXCEL_PATH)

    OUTPUT_PAYLOADS.parent.mkdir(parents=True, exist_ok=True)

    total_written = 0
    with OUTPUT_PAYLOADS.open("w", encoding="utf-8") as f_payloads, \
         OUTPUT_PAIRS.open("w", encoding="utf-8") as f_pairs:

        for cat in meta.categories:
            brands = meta.brands_by_cat.get(cat, [])
            if not brands:
                continue

            for _ in range(SAMPLES_PER_TYPE):
                # choose windows
                y = _rand_year_between(2022, 2025)
                start = date(y, 1, 1)
                end = date(y, 12, 31)

                # measures flip
                measure = "unit_sales" if RNG.random() < 0.5 else "value_sales"

                samples = [
                    build_mat_compare_exact(df,cat, "value_sales", years=[2025, 2024, 2023]),
                    build_yoy_exact(df,cat, brands, measure, start, end),
                    build_ytd_yoy_exact(df,cat, brands, measure, year=2025,end_month=8),
                    build_total_exact(df,cat, brands, measure, start, end),
                    build_mat_yoy_exact(df,cat, brands, measure, year=2025),  # <-- ADD THIS
                    build_line_trend_exact(df,cat, brands, "value_sales", date(2022, 1, 1), date(2022, 12, 31)),
                ]

                for s in samples:
                    insights = insight_variants(s)
                    # write payloads.jsonl
                    f_payloads.write(json.dumps(s) + "\n")
                    # write paired jsonl
                    f_pairs.write(json.dumps({"payload": s, "insights": insights}) + "\n")
                    total_written += 1

    print(f"Done. Wrote {total_written} payloads.")
    print(f"- Payloads only: {OUTPUT_PAYLOADS}")
    print(f"- Payload + insights pairs: {OUTPUT_PAIRS}")


if __name__ == "__main__":
    main()