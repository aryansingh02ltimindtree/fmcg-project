# # backend/datasets/build_from_excel_variants.py
# import json, argparse, random, re
# from pathlib import Path
# from typing import Dict, Any, List, Tuple
# import pandas as pd
# from datetime import datetime

# # -------------------- helpers: dates --------------------
# # put near the top (helper)
# def _norm(s:str)->str: return "".join(ch for ch in s.lower() if ch.isalnum())
# ALIASES = {
#     "date": {"date","month","period","periodstart","period_start"},
#     "market": {"market","country","geo"},
#     "channel": {"channel","retailer","tradechannel"},
#     "category": {"category","segment"},
#     "brand": {"brand","banner","label"},
#     "value_sales": {"value","value_sales","sales_value","valueinr","valueusd"},
#     "unit_sales": {"unit","units","unit_sales","sales_units","volume"},
#     "share": {"share","ms","marketshare","%share"}
# }
# def autodetect_mapper(columns: list[str]) -> dict:
#     mapper={}
#     norm_cols={_norm(c):c for c in columns}
#     for key, aliases in ALIASES.items():
#         for alias in aliases:
#             if alias in norm_cols:
#                 mapper[key]=norm_cols[alias]; break
#     return mapper

# def _parse_excel_date_cell(val):
#     if pd.isna(val): return pd.NaT
#     if isinstance(val, (pd.Timestamp, datetime)): return pd.Timestamp(val)
#     if isinstance(val, (int, float)):
#         try:
#             return pd.to_datetime(val, unit="d", origin="1899-12-30", errors="coerce")
#         except Exception:
#             return pd.NaT
#     if isinstance(val, str):
#         s = val.strip()
#         if not s: return pd.NaT
#         ts = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
#         if pd.isna(ts):
#             ts = pd.to_datetime(s, errors="coerce", infer_datetime_format=True)
#         return ts if not pd.isna(ts) else pd.NaT
#     return pd.NaT

# def month_start(ts):
#     if pd.isna(ts): return pd.NaT
#     return pd.Timestamp(ts).to_period("M").to_timestamp(how="start")

# # -------------------- IO --------------------
# def load_excel(excel_path: str, mapper_json: Dict[str,str]) -> pd.DataFrame:
#     df = pd.read_excel(excel_path)
#     rename_map = {mapper_json[k]: k for k in mapper_json}
#     df = df.rename(columns=rename_map)

#     # parse & normalize date
#     parsed = df["date"].map(_parse_excel_date_cell)
#     df["date"] = parsed.map(month_start)
#     for col in ["value_sales","unit_sales","share"]:
#         if col in df.columns:
#             df[col] = pd.to_numeric(df[col], errors="coerce")
#     df = df.dropna(subset=["date"]).copy()
#     return df

# # -------------------- windows (YTD/MAT) --------------------
# def ytd_window(df: pd.DataFrame) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     end = df["date"].max()
#     start = pd.Timestamp(end.year, 1, 1)
#     return start, end

# def mat_window(df: pd.DataFrame) -> Tuple[pd.Timestamp, pd.Timestamp]:
#     end = df["date"].max()
#     # last 12 months inclusive
#     start = (end.to_period("M") - 11).to_timestamp(how="start")
#     return start, end

# def slice_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
#     return df[(df["date"] >= start) & (df["date"] <= end)].copy()

# # -------------------- stats builders (minimal) --------------------
# def topn_stats(dff: pd.DataFrame, measure: str, dim: str, top_n: int,
#                filters: Dict[str,Any]) -> Dict[str,Any]:
#     g = (dff.groupby(dim, as_index=False)[measure]
#             .sum()
#             .sort_values(measure, ascending=False)
#             .head(top_n))
#     items = [{"label": r[dim], "value": float(r[measure])} for _, r in g.iterrows()]
#     return {"items": items, "dimension": dim}

# def yoy_stats(dff: pd.DataFrame, measure_type: str, dim: str|None,
#               filters: Dict[str,Any]) -> Dict[str,Any]:
#     # compare current window vs prior-year same window by brand (or overall)
#     # assume 'unit_sales'/'value_sales' fields present; 'measure_type' selects which
#     measure = f"{measure_type}_sales" if measure_type in ("unit","value") else measure_type
#     # last window boundaries
#     curr_start, curr_end = dff["date"].min(), dff["date"].max()
#     prev_start = (curr_start - pd.offsets.DateOffset(years=1))
#     prev_end   = (curr_end   - pd.offsets.DateOffset(years=1))
#     curr = slice_window(dff, curr_start, curr_end)
#     prev = slice_window(dff, prev_start, prev_end)

#     out=[]
#     if dim:
#         cg = curr.groupby(dim, as_index=False)[measure].sum()
#         pg = prev.groupby(dim, as_index=False)[measure].sum()
#         merged = pd.merge(cg, pg, on=dim, how="left", suffixes=("_curr","_prev")).fillna(0)
#         for _, r in merged.iterrows():
#             curr_v, prev_v = float(r[f"{measure}_curr"]), float(r[f"{measure}_prev"])
#             yoy_pct = (curr_v - prev_v)/prev_v if prev_v else 0.0
#             out.append({"label": r[dim], "curr": curr_v, "prev": prev_v, "yoy_pct": yoy_pct})
#         out = sorted(out, key=lambda x: x["yoy_pct"], reverse=True)
#     else:
#         curr_v = float(curr[measure].sum())
#         prev_v = float(prev[measure].sum())
#         yoy_pct = (curr_v - prev_v)/prev_v if prev_v else 0.0
#         out = [{"label":"overall","curr":curr_v,"prev":prev_v,"yoy_pct":yoy_pct}]
#     return {"measure_type": measure_type, "items": out}

# def total_stats(dff: pd.DataFrame, measure: str, dim: str|None, filters: Dict[str,Any]) -> Dict[str,Any]:
#     if dim:
#         g = dff.groupby(dim, as_index=False)[measure].sum()
#         items = [{"label": r[dim], "value": float(r[measure])} for _, r in g.iterrows()]
#         items = sorted(items, key=lambda x: x["value"], reverse=True)
#         return {"items": items, "dimension": dim}
#     else:
#         return {"items": [{"label":"overall","value": float(dff[measure].sum())}], "dimension": "overall"}

# def mat_compare_stats(df: pd.DataFrame, category: str, anchor_month: int, years: List[int],
#                       measure: str) -> Dict[str,Any]:
#     periods=[]
#     for y in years:
#         # MAT y = (Oct y-1 .. Sep y) if anchor_month=9 (Sep); generalize:
#         end   = pd.Timestamp(y, anchor_month, 1).to_period("M").to_timestamp(how="end")
#         start = (end.to_period("M") - 11).to_timestamp(how="start")
#         dff = df[(df["date"] >= start) & (df["date"] <= end) & (df["category"].str.lower()==category.lower())]
#         value = float(dff[measure].sum()) if measure in dff.columns else 0.0
#         periods.append({"label": f"MAT {y}", "value": value, "start": str(start.date()), "end": str(end.date())})
#     return {"periods": periods}

# def trend_stats(dff: pd.DataFrame, measure: str) -> Dict[str,Any]:
#     # overall min/max by month
#     g = dff.groupby(dff["date"].dt.to_period("M"))[measure].sum().reset_index()
#     g["date"] = g["date"].dt.to_timestamp(how="start")
#     if g.empty:
#         return {"overall": {}}
#     minrow = g.loc[g[measure].idxmin()]
#     maxrow = g.loc[g[measure].idxmax()]
#     month_label = lambda ts: ts.strftime("%b %Y")
#     return {
#         "overall": {
#             "min": {"value": float(minrow[measure]), "label": month_label(minrow["date"])},
#             "max": {"value": float(maxrow[measure]), "label": month_label(maxrow["date"])},
#         }
#     }

# # -------------------- formatting + validation --------------------
# def human_short(n: float) -> str:
#     n = float(n)
#     for u in ["","K","M","B","T"]:
#         if abs(n) < 1000: return f"{n:.2f}{u}".rstrip("0").rstrip(".")
#         n /= 1000
#     return f"{n:.2f}P"

# def fmt_pct(x: float, d=1) -> str:
#     return f"{x*100:+.{d}f}%"

# def numbers_from_stats(stats: Dict[str,Any]) -> set:
#     vals=set()
#     def walk(x):
#         if isinstance(x, dict):
#             for v in x.values(): walk(v)
#         elif isinstance(x, list):
#             for v in x: walk(v)
#         elif isinstance(x,(int,float)) and not isinstance(x,bool):
#             s = str(round(float(x),6)).rstrip("0").rstrip(".")
#             vals.add(s); 
#             if abs(float(x)-round(float(x)))<1e-9: vals.add(str(int(round(float(x)))))
#     walk(stats); return vals

# _num_pat = re.compile(r"[+-]?\d+(?:[.,]\d+)?")

# def numbers_valid(bullets: List[str], stats: Dict[str,Any]) -> bool:
#     allowed = numbers_from_stats(stats)
#     for b in bullets:
#         for raw in _num_pat.findall(b.replace(",","")):
#             clean = re.sub(r"[^\d.+-]", "", raw)
#             if clean and clean not in allowed:
#                 # allow % sign derived from stats; we still keep it conservative
#                 if "%" in b: continue
#                 return False
#     return True

# # -------------------- canonical bullets per mode --------------------
# def bullets_for_stats(stats: Dict[str,Any]) -> List[str]:
#     mode = stats["mode"].upper()
#     p = stats["payload"]
#     meas = stats.get("measure","value_sales").replace("_"," ")
#     if mode == "MAT_COMPARE":
#         periods = p.get("periods",[])
#         if not periods: return ["No MAT periods."]
#         top = max(periods, key=lambda x: x.get("value",0))
#         b=[f"{top['label']} leads with {meas} {human_short(top['value'])}."]
#         if len(periods)>=2:
#             srt = sorted(periods, key=lambda x: x["value"])
#             lo,hi=srt[0],srt[-1]
#             if hi["value"]:
#                 span = (hi["value"]-lo["value"])/hi["value"]
#                 b.append(f"Range across years is {fmt_pct(span)}.")
#         return b[:3]
#     if mode in ("YTD","MAT","YTD_YOY","YOY"):
#         if "items" in p and p["items"]:
#             it = p["items"]
#             # for YOY we show top movers
#             if "yoy_pct" in it[0]:
#                 it = sorted(it, key=lambda x: x["yoy_pct"], reverse=True)
#                 first = it[0]
#                 sign = "up" if first["yoy_pct"]>=0 else "down"
#                 return [f"{first['label']} {sign} {fmt_pct(first['yoy_pct'])} YoY."]
#             # otherwise top total
#             top = it[0]
#             return [f"Top: {top['label']} with {meas} {human_short(top['value'])}."]
#         return ["No items."]
#     if mode == "TOTAL":
#         it = p.get("items",[])
#         if it:
#             e = it[0]
#             return [f"{e['label']} total {meas} {human_short(e['value'])}."]
#     if mode == "TREND":
#         o = p.get("overall",{})
#         if "max" in o and "min" in o:
#             return [f"Peak {o['max']['label']} at {human_short(o['max']['value'])}; trough {o['min']['label']}."]
#     return ["Data steady; no standout changes detected."]

# # -------------------- paraphrase engine (4–5 variants) --------------------
# SYN = {
#     "leads": ["leads", "tops", "is #1", "ranks first", "heads"],
#     "Top:": ["Top:", "Leader:", "No.1:", "Highest:"],
#     "with": ["with", "at", "totaling"],
#     "Range across years is": ["Range across years is", "Spread across years is", "Range across MATs is"],
#     "YoY": ["YoY", "year-on-year", "vs LY"],
#     "up": ["up", "higher by", "rose"],
#     "down": ["down", "lower by", "fell"],
# }

# def swap_synonyms(text: str) -> str:
#     out = text
#     for base, alts in SYN.items():
#         if base in out:
#             out = out.replace(base, random.choice(alts))
#     return " ".join(out.split())

# def permute_order(bullets: List[str]) -> List[str]:
#     if len(bullets)>=2 and random.random()<0.35:
#         return [bullets[1], bullets[0]] + bullets[2:]
#     return bullets

# def variants_from_canonical(canonical: List[str], stats: Dict[str,Any], n=5) -> List[List[str]]:
#     out=[]
#     tries=0
#     while len(out)<n and tries<n*6:
#         tries+=1
#         bs=[swap_synonyms(b) for b in canonical]
#         bs=permute_order(bs)
#         if numbers_valid(bs, stats) and bs not in out:
#             out.append(bs)
#     if canonical not in out:
#         out=[canonical]+out
#     return out[:n]

# # -------------------- dataset builder --------------------
# def build_payloads(df: pd.DataFrame, target_rows: int) -> List[Dict[str,Any]]:
#     rows=[]
#     brands = sorted(df["brand"].dropna().astype(str).unique()) if "brand" in df.columns else []
#     cats   = sorted(df["category"].dropna().astype(str).unique()) if "category" in df.columns else []

#     # windows
#     ytd_s, ytd_e = ytd_window(df)
#     mat_s, mat_e = mat_window(df)

#     for cat in cats or ["Biscuits"]:
#         dfc = df[df["category"].str.lower()==cat.lower()]
#         if dfc.empty: continue

#         # --- MAT_COMPARE for last 3 years ---
#         anchor_month = mat_e.month
#         years = [mat_e.year, mat_e.year-1, mat_e.year-2]
#         matcmp = {
#             "mode": "MAT_COMPARE",
#             "measure": "value_sales",
#             "window": {"start": str((mat_e.to_period('M')-23).to_timestamp(how='start').date()), "end": str(mat_e.date())},
#             "filters": {"category": cat},
#             "payload": mat_compare_stats(df, cat, anchor_month, years, "value_sales"),
#         }
#         rows.append(matcmp)

#         # --- YTD TOPN (2,3,4 brands) for value + unit ---
#         for measure in ["value_sales","unit_sales"]:
#             dff = slice_window(dfc, ytd_s, ytd_e)
#             for k in [2,3,4]:
#                 payload = topn_stats(dff, measure, "brand", k, {"category":cat})
#                 rows.append({
#                     "mode": "YTD", "measure": measure,
#                     "window": {"start": str(ytd_s.date()), "end": str(ytd_e.date())},
#                     "filters": {"category": cat},
#                     "payload": payload
#                 })

#         # --- MAT TOPN (2,3,4 brands) ---
#         for measure in ["value_sales","unit_sales"]:
#             dff = slice_window(dfc, mat_s, mat_e)
#             for k in [2,3,4]:
#                 payload = topn_stats(dff, measure, "brand", k, {"category":cat})
#                 rows.append({
#                     "mode": "MAT", "measure": measure,
#                     "window": {"start": str(mat_s.date()), "end": str(mat_e.date())},
#                     "filters": {"category": cat},
#                     "payload": payload
#                 })

#         # --- YOY (YTD) top movers by unit ---
#         dff = slice_window(dfc, ytd_s, ytd_e)
#         ystats = yoy_stats(dff, "unit", "brand", {"category":cat})
#         rows.append({
#             "mode": "YTD_YOY", "measure": "unit_yoy",
#             "window": {"start": str(ytd_s.date()), "end": str(ytd_e.date())},
#             "filters": {"category": cat},
#             "payload": {"items": ystats["items"]}
#         })

#         # --- TOTAL for a few single brands (per category) ---
#         for b in brands[:5]:
#             dff = slice_window(dfc[dfc["brand"].astype(str).str.lower()==b.lower()], pd.to_datetime(f"{ytd_e.year}-01-01"), ytd_e)
#             if dff.empty: continue
#             payload = total_stats(dff, "unit_sales", None, {"category":cat,"brand":[b]})
#             rows.append({
#                 "mode": "TOTAL", "measure": "unit_sales",
#                 "window": {"start": f"{ytd_e.year}-01-01", "end": str(ytd_e.date())},
#                 "filters": {"category": cat, "brand": [b]},
#                 "payload": payload
#             })

#         # --- TREND (line chart) for category totals (value_sales) over a fixed year ---
#         year = ytd_e.year-1
#         t_s, t_e = pd.Timestamp(year,1,1), pd.Timestamp(year,12,31)
#         dff = slice_window(dfc, t_s, t_e)
#         if not dff.empty:
#             payload = trend_stats(dff, "value_sales")
#             rows.append({
#                 "mode":"TREND","measure":"value_sales",
#                 "window":{"start":str(t_s.date()),"end":str(t_e.date())},
#                 "filters":{"category":cat},
#                 "payload": payload
#             })

#         # stop when we reach target size
#         if len(rows) >= target_rows:
#             break
#     return rows[:target_rows]

# def main():
#     # ap = argparse.ArgumentParser()
#     import argparse

#     ap = argparse.ArgumentParser()

#     # new args
#     ap.add_argument("--excel", required=True, help="Path to Excel file")
#     ap.add_argument("--rows", type=int, default=1500, help="How many dataset rows to generate")
#     ap.add_argument("--variants", type=int, default=5, help="How many variations per payload")

#    # --- add in argparse ---
#     ap.add_argument("--autodetect", action="store_true", help="Autodetect column names from Excel headers")
#     ap.add_argument("--date", "--date-col", dest="date_col")
#     ap.add_argument("--market", dest="market_col")
#     ap.add_argument("--channel", dest="channel_col")
#     ap.add_argument("--category", dest="category_col")
#     ap.add_argument("--brand", dest="brand_col")
#     ap.add_argument("--value_sales", dest="value_sales_col")
#     ap.add_argument("--unit_sales", dest="unit_sales_col")
#     ap.add_argument("--share", dest="share_col")

#     args = ap.parse_args()

#     if args.autodetect:
#         df_headers = pd.read_excel(args.excel, nrows=0)
#         mapper = autodetect_mapper(list(df_headers.columns))
#     else:
#         mapper = {
#             "date": args.date_col,
#             "market": args.market_col,
#             "channel": args.channel_col,
#             "category": args.category_col,
#             "brand": args.brand_col,
#             "value_sales": args.value_sales_col,
#             "unit_sales": args.unit_sales_col,
#             "share": args.share_col,
#         }
#         mapper = {k: v for k, v in mapper.items() if v}  # drop empty


#     # build numeric payloads
#     stats_list = build_payloads(df, args.rows)

#     # produce canonical bullets + variants
#     dataset=[]
#     for stats in stats_list:
#         canonical = bullets_for_stats(stats)
#         variants = variants_from_canonical(canonical, stats, n=args.variants)
#         for v in variants:
#             dataset.append({"input":{"stats": stats}, "output":{"bullets": v}})
#             if len(dataset) >= args.rows:
#                 break
#         if len(dataset) >= args.rows:
#             break

#     # split + write
#     random.shuffle(dataset)
#     cut = max(1, int(0.9*len(dataset)))
#     Path("../data/datasets").mkdir(parents=True, exist_ok=True)
#     Path("../data/datasets/train.json").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in dataset[:cut]), encoding="utf-8")
#     Path("../data/datasets/val.json").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in dataset[cut:]), encoding="utf-8")
#     print(f"[OK] wrote {cut} train and {len(dataset)-cut} val rows to data/datasets/")
    
# if __name__ == "__main__":
#     main()
