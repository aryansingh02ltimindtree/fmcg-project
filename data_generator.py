# data_generator.py
# Build a richer FMCG insights dataset from Excel.
# Generates examples for multiple reference months (sliding MAT windows).
#
# Usage:
#   python data_generator.py --excel data/sample_nielsen_extended.xlsx --out data/ --months 12

import argparse, json, os
from datetime import date
from itertools import combinations
from typing import List, Dict

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

# ---------- time helpers ----------
def month_start(d: date) -> date: return date(d.year, d.month, 1)
def next_month(d: date) -> date:  return month_start(d + relativedelta(months=1))
def prev_month(d: date) -> date:  return month_start(d - relativedelta(months=1))

def mat_window(ref: date):
    """Last 12 complete months relative to a reference month (exclude ref)."""
    end_excl = month_start(ref)              # exclude reference month
    start_incl = month_start(end_excl - relativedelta(months=12))
    return start_incl, end_excl

def prev_mat_window(ref: date):
    """The 12 months before the MAT window."""
    end_excl = month_start(ref) - relativedelta(months=12)
    start_incl = month_start(end_excl - relativedelta(months=12))
    return start_incl, end_excl

def ytd_window(ref: date):
    """Current YTD and previous YTD windows relative to a reference month."""
    cur_start = date(ref.year, 1, 1)
    cur_end   = month_start(ref) + relativedelta(months=1)  # exclusive
    prev_start = date(ref.year - 1, 1, 1)
    prev_end   = date(ref.year - 1, ref.month, 1) + relativedelta(months=1)
    return (cur_start, cur_end), (prev_start, prev_end)


# ---------- math helpers ----------
def safe_div(a, b): return None if (b is None or b == 0) else float(a)/float(b)
def to_cr(x):       return None if x is None else float(x)/1e7      # adjust unit if needed
def pct(x):         return None if x is None else round(100*float(x), 2)
def pp(x):          return None if x is None else round(100*float(x), 2)

# ---------- phrasing templates ----------
def bullets_summary(f: Dict) -> List[str]:
    leader = f["leaders"][0] if f.get("leaders") else None
    yoy_txt = "—" if f["yoy"] is None else f"{pct(f['yoy'])}%"
    out = []

    v1 = [f"• {f['category']} ({f['market']}) MAT ₹{f['mat_sales_cr']}Cr; YoY {yoy_txt}."]
    if leader:
        if f.get("lead_share_pp_delta") is None:
            v1.append(f"• {leader['brand']} leads with {pct(leader['share'])}% share.")
        else:
            sgn = "+" if f['lead_share_pp_delta'] >= 0 else "−"
            v1.append(f"• {leader['brand']} leads at {pct(leader['share'])}% ({sgn}{abs(pp(f['lead_share_pp_delta']))} pp vs LY).")
    if f.get("top_movers"):
        tm = f["top_movers"][0]; sgn = "+" if tm["yoy"] >= 0 else "−"
        v1.append(f"• Top mover: {tm['brand']} ({sgn}{abs(pct(tm['yoy']))}%).")
    out.append("\n".join(v1))

    v2 = [f"• Category: {f['category']} | Market: {f['market']} | MAT ₹{f['mat_sales_cr']}Cr (YoY {yoy_txt})."]
    if leader:
        tail = "" if f.get("lead_share_pp_delta") is None else f" ({'+' if f['lead_share_pp_delta']>=0 else '−'}{abs(pp(f['lead_share_pp_delta']))} pp)."
        v2.append(f"• Leader: {leader['brand']} | Share {pct(leader['share'])}%{tail}")
    if len(f.get("leaders", [])) > 1:
        second = f["leaders"][1]
        v2.append(f"• #2: {second['brand']} at {pct(second['share'])}% share.")
    out.append("\n".join(v2))
    return out

def bullets_topn(f: Dict, n=3) -> List[str]:
    leaders = f.get("leaders", [])[:n]
    if not leaders: return []
    names = ", ".join([f"{x['brand']} ({pct(x['share'])}%)" for x in leaders])
    v = f"• Top {n} in {f['category']} ({f['market']}): {names}.\n• MAT ₹{f['mat_sales_cr']}Cr; YoY {pct(f['yoy']) if f['yoy'] is not None else '—'}%."
    return [v]

def bullets_bottom_movers(f: Dict, n=2) -> List[str]:
    lows = f.get("bottom_movers", [])[:n]
    if not lows: return []
    tail = ", ".join([f"{x['brand']} ({pct(x['yoy'])}%)" for x in lows])
    v = f"• Weakest movers: {tail} in {f['category']} ({f['market']}).\n• Market MAT ₹{f['mat_sales_cr']}Cr."
    return [v]

def bullets_pair(pair: Dict) -> List[str]:
    a, b = pair["brand_a"], pair["brand_b"]
    yoy_a = pct(pair["yoy_a"]) if pair["yoy_a"] is not None else "—"
    yoy_b = pct(pair["yoy_b"]) if pair["yoy_b"] is not None else "—"
    v = (f"• {pair['category']} ({pair['market']}): {a} vs {b}.\n"
         f"• MAT: ₹{pair['mat_cr_a']}Cr vs ₹{pair['mat_cr_b']}Cr; "
         f"Share: {pct(pair['share_a'])}% vs {pct(pair['share_b'])}%.\n"
         f"• YoY: {yoy_a}% vs {yoy_b}%.")
    return [v]

# ---------- core builders ----------
# def build_for_reference_month(m, ref_month, rng, max_pairs_per_cat=6):
#     """Create records for a single reference month."""
#     cur_s, cur_e = mat_window(ref_month)
#     prv_s, prv_e = prev_mat_window(ref_month)

#     cur = m[(m["month"]>=cur_s) & (m["month"]<cur_e)].copy()
#     prv = m[(m["month"]>=prv_s) & (m["month"]<prv_e)].copy()

#     records = []

#     for (cat, mkt), g in cur.groupby(["category","market"]):
#         bc = (g.groupby("brand", as_index=False)
#                 .agg(mat_curr=("value_sales","sum"))
#                 .sort_values("mat_curr", ascending=False))
#         total_cur = bc["mat_curr"].sum()

#         gp = prv[(prv["category"]==cat) & (prv["market"]==mkt)]
#         bp = (gp.groupby("brand", as_index=False).agg(mat_prev=("value_sales","sum")))
#         merged = pd.merge(bc, bp, on="brand", how="left").fillna({"mat_prev":0.0})

#         merged["yoy"]   = merged.apply(lambda r: safe_div(r["mat_curr"]-r["mat_prev"], r["mat_prev"]), axis=1)
#         merged["share"] = merged["mat_curr"]/total_cur if total_cur else 0.0

#         mat_curr_total = float(total_cur)
#         mat_prev_total = float(bp["mat_prev"].sum())
#         yoy_market     = safe_div(mat_curr_total - mat_prev_total, mat_prev_total)

#         total_prev = mat_prev_total if mat_prev_total else None
#         merged["share_prev"]    = merged.apply(lambda r: safe_div(r["mat_prev"], total_prev) if total_prev else None, axis=1)
#         merged["share_pp_delta"]= merged.apply(lambda r: None if r["share_prev"] is None else (r["share"]-r["share_prev"]), axis=1)

#         leaders = (merged.sort_values("mat_curr", ascending=False)[["brand","mat_curr","share"]].head(5).copy())
#         leaders["mat_cr"] = leaders["mat_curr"].apply(to_cr)
#         leaders = leaders.drop(columns=["mat_curr"]).to_dict(orient="records")

#         movers_up = merged.dropna(subset=["yoy"]).sort_values("yoy", ascending=False)
#         movers_dn = merged.dropna(subset=["yoy"]).sort_values("yoy", ascending=True)
#         top_movers    = movers_up[["brand","yoy"]].head(3).to_dict(orient="records")
#         bottom_movers = movers_dn[["brand","yoy"]].head(3).to_dict(orient="records")

#         facts = {
#             "category": str(cat),
#             "market":   str(mkt),
#             "period":   f"{cur_s.strftime('%Y-%m')}..{(cur_e - relativedelta(days=1)).strftime('%Y-%m')}",
#             "mat_sales_cr": round(to_cr(mat_curr_total),3) if mat_curr_total is not None else None,
#             "yoy": None if yoy_market is None else round(float(yoy_market),4),
#             "leaders": [{**r, "share": round(float(r["share"]),4)} for r in leaders],
#             "top_movers":    [{"brand": r["brand"], "yoy": round(float(r["yoy"]),4)} for r in top_movers],
#             "bottom_movers":[{"brand": r["brand"], "yoy": round(float(r["yoy"]),4)} for r in bottom_movers]
#         }

#         if not merged.empty:
#             lead_row = merged.sort_values("mat_curr", ascending=False).iloc[0]
#             facts["lead_share_pp_delta"] = None if pd.isna(lead_row.get("share_pp_delta")) else round(float(lead_row["share_pp_delta"]),4)

#         # summaries (2 phrasings)
#         for txt in bullets_summary(facts):
#             records.append({"input": facts, "output": txt})

#         # top-N variants
#         for n in (3, 5):
#             for txt in bullets_topn(facts, n=n):
#                 records.append({"input": facts, "output": txt})

#         # bottom movers
#         for txt in bullets_bottom_movers(facts, n=2):
#             records.append({"input": facts, "output": txt})

#         # pairwise (several pairs)
#         brands = list(merged["brand"].unique())
#         rng.shuffle(brands)
#         pairs = list(combinations(brands[:min(len(brands), 6)], 2))[:max_pairs_per_cat]
#         for a, b in pairs:
#             ra = merged[merged["brand"]==a].iloc[0]
#             rb = merged[merged["brand"]==b].iloc[0]
#             pair = {
#                 "task": "brand_pair",
#                 "category": str(cat), "market": str(mkt),
#                 "brand_a": a, "brand_b": b,
#                 "mat_cr_a": round(to_cr(ra["mat_curr"]),3),
#                 "mat_cr_b": round(to_cr(rb["mat_curr"]),3),
#                 "share_a": round(float(ra["share"]),4),
#                 "share_b": round(float(rb["share"]),4),
#                 "yoy_a": None if pd.isna(ra["yoy"]) else round(float(ra["yoy"]),4),
#                 "yoy_b": None if pd.isna(rb["yoy"]) else round(float(rb["yoy"]),4),
#             }
#             for txt in bullets_pair(pair):
#                 records.append({"input": pair, "output": txt})
            

#     return records

def build_for_reference_month(m, ref_month, rng, max_pairs_per_cat=6):
    """Create records for a single reference month (MAT + YTD examples)."""
    records = []

    # ---------------- MAT (last 12 complete months) ----------------
    cur_s, cur_e = mat_window(ref_month)
    prv_s, prv_e = prev_mat_window(ref_month)

    cur = m[(m["month"] >= cur_s) & (m["month"] < cur_e)].copy()
    prv = m[(m["month"] >= prv_s) & (m["month"] < prv_e)].copy()

    for (cat, mkt), g in cur.groupby(["category", "market"]):
        bc = (g.groupby("brand", as_index=False)
                .agg(mat_curr=("value_sales", "sum"))
                .sort_values("mat_curr", ascending=False))
        total_cur = bc["mat_curr"].sum()

        gp = prv[(prv["category"] == cat) & (prv["market"] == mkt)]
        bp = gp.groupby("brand", as_index=False).agg(mat_prev=("value_sales", "sum"))
        merged = pd.merge(bc, bp, on="brand", how="left").fillna({"mat_prev": 0.0})

        merged["yoy"]   = merged.apply(lambda r: safe_div(r["mat_curr"] - r["mat_prev"], r["mat_prev"]), axis=1)
        merged["share"] = merged["mat_curr"] / total_cur if total_cur else 0.0

        mat_curr_total = float(total_cur)
        mat_prev_total = float(bp["mat_prev"].sum())
        yoy_market     = safe_div(mat_curr_total - mat_prev_total, mat_prev_total)

        total_prev = mat_prev_total if mat_prev_total else None
        merged["share_prev"]     = merged.apply(lambda r: safe_div(r["mat_prev"], total_prev) if total_prev else None, axis=1)
        merged["share_pp_delta"] = merged.apply(lambda r: None if r["share_prev"] is None else (r["share"] - r["share_prev"]), axis=1)

        leaders = (merged.sort_values("mat_curr", ascending=False)[["brand", "mat_curr", "share"]].head(5).copy())
        leaders["mat_cr"] = leaders["mat_curr"].apply(to_cr)
        leaders = leaders.drop(columns=["mat_curr"]).to_dict(orient="records")

        movers_up = merged.dropna(subset=["yoy"]).sort_values("yoy", ascending=False)
        movers_dn = merged.dropna(subset=["yoy"]).sort_values("yoy", ascending=True)
        top_movers    = movers_up[["brand", "yoy"]].head(3).to_dict(orient="records")
        bottom_movers = movers_dn[["brand", "yoy"]].head(3).to_dict(orient="records")

        facts = {
            "task": "mat_summary",
            "category": str(cat),
            "market":   str(mkt),
            "period":   f"{cur_s.strftime('%Y-%m')}..{(cur_e - relativedelta(days=1)).strftime('%Y-%m')}",
            "mat_sales_cr": round(to_cr(mat_curr_total), 3) if mat_curr_total is not None else None,
            "yoy": None if yoy_market is None else round(float(yoy_market), 4),
            "leaders": [{**r, "share": round(float(r["share"]), 4)} for r in leaders],
            "top_movers":     [{"brand": r["brand"], "yoy": round(float(r["yoy"]), 4)} for r in top_movers],
            "bottom_movers":  [{"brand": r["brand"], "yoy": round(float(r["yoy"]), 4)} for r in bottom_movers],
        }

        if not merged.empty:
            lead_row = merged.sort_values("mat_curr", ascending=False).iloc[0]
            facts["lead_share_pp_delta"] = None if pd.isna(lead_row.get("share_pp_delta")) else round(float(lead_row["share_pp_delta"]), 4)

        # MAT summaries (2 phrasings)
        for txt in bullets_summary(facts):
            records.append({"input": facts, "output": txt})

        # MAT Top-N variants
        for n in (3, 5):
            for txt in bullets_topn(facts, n=n):
                records.append({"input": facts, "output": txt})

        # MAT bottom movers
        for txt in bullets_bottom_movers(facts, n=2):
            records.append({"input": facts, "output": txt})

        # MAT brand-vs-brand pairs
        brands = list(merged["brand"].unique())
        rng.shuffle(brands)
        pairs = list(combinations(brands[:min(len(brands), 6)], 2))[:max_pairs_per_cat]
        for a, b in pairs:
            ra = merged[merged["brand"] == a].iloc[0]
            rb = merged[merged["brand"] == b].iloc[0]
            pair = {
                "task": "brand_pair",
                "category": str(cat), "market": str(mkt),
                "brand_a": a, "brand_b": b,
                "mat_cr_a": round(to_cr(ra["mat_curr"]), 3),
                "mat_cr_b": round(to_cr(rb["mat_curr"]), 3),
                "share_a": round(float(ra["share"]), 4),
                "share_b": round(float(rb["share"]), 4),
                "yoy_a": None if pd.isna(ra["yoy"]) else round(float(ra["yoy"]), 4),
                "yoy_b": None if pd.isna(rb["yoy"]) else round(float(rb["yoy"]), 4),
            }
            for txt in bullets_pair(pair):
                records.append({"input": pair, "output": txt})

    # ---------------- YTD (current year up to ref month vs last year) ----------------
    (ytd_cur_s, ytd_cur_e), (ytd_prv_s, ytd_prv_e) = ytd_window(ref_month)

    cur_ytd = m[(m["month"] >= ytd_cur_s) & (m["month"] < ytd_cur_e)].copy()
    prv_ytd = m[(m["month"] >= ytd_prv_s) & (m["month"] < ytd_prv_e)].copy()

    for (cat, mkt), g in cur_ytd.groupby(["category", "market"]):
        bc = g.groupby("brand", as_index=False).agg(ytd_curr=("value_sales", "sum"))
        total_cur = bc["ytd_curr"].sum()

        gp = prv_ytd[(prv_ytd["category"] == cat) & (prv_ytd["market"] == mkt)]
        bp = gp.groupby("brand", as_index=False).agg(ytd_prev=("value_sales", "sum"))
        merged = pd.merge(bc, bp, on="brand", how="left").fillna({"ytd_prev": 0.0})

        merged["yoy"]   = merged.apply(lambda r: safe_div(r["ytd_curr"] - r["ytd_prev"], r["ytd_prev"]), axis=1)
        merged["share"] = merged["ytd_curr"] / total_cur if total_cur else 0.0

        ytd_curr_total = float(total_cur)
        ytd_prev_total = float(bp["ytd_prev"].sum())
        yoy_market     = safe_div(ytd_curr_total - ytd_prev_total, ytd_prev_total)

        leaders = (merged.sort_values("ytd_curr", ascending=False)
                        [["brand", "ytd_curr", "share"]].head(5).copy())
        leaders["ytd_cr"] = leaders["ytd_curr"].apply(to_cr)
        leaders = leaders.drop(columns=["ytd_curr"]).to_dict(orient="records")

        ytd_facts = {
            "task": "ytd_summary",
            "category": str(cat),
            "market":   str(mkt),
            "period":   f"YTD {ytd_cur_s.strftime('%Y-%m')}..{(ytd_cur_e - relativedelta(days=1)).strftime('%Y-%m')}",
            "ytd_sales_cr": round(to_cr(ytd_curr_total), 3) if ytd_curr_total is not None else None,
            "yoy": None if yoy_market is None else round(float(yoy_market), 4),
            "leaders": [{**r, "share": round(float(r['share']), 4)} for r in leaders]
        }

        # YTD concise bullet
        if ytd_facts["leaders"]:
            lead = ytd_facts["leaders"][0]
            txt = (f"• {ytd_facts['category']} ({ytd_facts['market']}) YTD ₹{ytd_facts['ytd_sales_cr']}Cr; "
                   f"YoY {pct(ytd_facts['yoy']) if ytd_facts['yoy'] is not None else '—'}%. "
                   f"Leader: {lead['brand']} at {pct(lead['share'])}% share.")
        else:
            txt = (f"• {ytd_facts['category']} ({ytd_facts['market']}) YTD ₹{ytd_facts['ytd_sales_cr']}Cr; "
                   f"YoY {pct(ytd_facts['yoy']) if ytd_facts['yoy'] is not None else '—'}%.")

        records.append({"input": ytd_facts, "output": txt})

    return records


def build_dataset(excel_path: str, out_dir: str, months: int, max_pairs_per_cat=6, seed=123):
    os.makedirs(out_dir, exist_ok=True)

    # load & standardize
    df = pd.read_excel(excel_path)
    cmap = {c.lower().strip(): c for c in df.columns}
    for r in ["date","category","brand","market","value_sales"]:
        if r not in cmap: raise ValueError(f"Missing column: {r}")

    df = df.rename(columns={
        cmap["date"]:"date", cmap["category"]:"category", cmap["brand"]:"brand",
        cmap["market"]:"market", cmap["value_sales"]:"value_sales"
    })
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").dt.to_timestamp().dt.date
    df = df.dropna(subset=["month","category","brand","market","value_sales"])

    # monthly aggregate
    m = (df.groupby(["month","category","market","brand"], as_index=False)
           .agg(value_sales=("value_sales","sum")))

    # decide reference months we can use:
    min_month = m["month"].min()
    max_month = m["month"].max()
    # you need at least 24 months before a reference month to compute MAT and YoY
    earliest_ref = month_start(min_month) + relativedelta(months=24)
    latest_ref   = next_month(max_month)  # ref can be just after last data month

    # build list of ref months backward from latest_ref
    ref_months = []
    cur = month_start(latest_ref)
    while cur >= earliest_ref and len(ref_months) < months:
        ref_months.append(cur)
        cur = prev_month(cur)

    rng = np.random.default_rng(seed)
    all_records = []
    for ref in ref_months:
        all_records.extend(build_for_reference_month(m, ref, rng, max_pairs_per_cat=max_pairs_per_cat))

    # shuffle + smart split
    rng.shuffle(all_records)
    n = len(all_records)
    if n < 200:
        n_val = min(3, max(1, n // 8))
    else:
        n_val = max(100, int(0.1 * n))
    val, train = all_records[:n_val], all_records[n_val:]

    # write
    train_path = os.path.join(out_dir, "insights_train.jsonl")
    val_path   = os.path.join(out_dir, "insights_val.jsonl")
    with open(train_path, "w", encoding="utf-8") as f:
        for r in train: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(val_path, "w", encoding="utf-8") as f:
        for r in val:   f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"✅ Generated {len(train)} train / {len(val)} val examples "
          f"from {len(ref_months)} reference months.")
    print(f"   {train_path}\n   {val_path}")

# ---------- CLI ----------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", default="data/sample_nielsen_extended.xlsx")
    ap.add_argument("--out", default="data")
    ap.add_argument("--months", type=int, default=12, help="How many reference months to generate")
    ap.add_argument("--max_pairs", type=int, default=6)
    args = ap.parse_args()
    build_dataset(args.excel, args.out, months=args.months, max_pairs_per_cat=args.max_pairs)
