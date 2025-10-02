import random, numpy as np, pandas as pd, json
from datetime import date
from calendar import monthrange
from pathlib import Path

# ==== CONFIG =====
EXCEL_PATH = r"./data/sample_nielsen_extended.xlsx"        # ⬅️ change to your file path
OUTPUT_JSONL = r"./data/synthetic_payloads.json"     # payloads only
OUTPUT_PAIRS_JSONL = r"./data/synthetic_pairs.json"  # {payload, insights[]} pairs
N_SAMPLES_PER_TYPE = 3                  # ⬅️ how many per scenario per category
RANDOM_SEED = 42
# =================

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# -------- date helpers --------
def month_end(y, m):
    print("Generating month end date...")
    print(date(y, m, monthrange(y, m)[1]).isoformat())
    return date(y, m, monthrange(y, m)[1]).isoformat()

def month_start(y, m):
    print("Generating month start date...")
    print(date(y, m, 1).isoformat())
    return date(y, m, 1).isoformat()

def month_label(y, m):
    return pd.Timestamp(year=y, month=m, day=1).strftime("%b %Y")

def mat_window_for(year, anchor_month):
    """Return (start_iso, end_iso) for a 12-month MAT ending at anchor_month of `year`."""
    end_y, end_m = year, anchor_month
    start_m_total = (end_y * 12 + end_m) - 11
    start_y = (start_m_total - 1) // 12
    start_m = (start_m_total - 1) % 12 + 1
    return month_start(start_y, start_m), month_end(end_y, end_m)

# -------- load categories/brands from Excel --------
def load_entities(path):
    df = pd.read_excel(path)
    # tolerant column resolution
    cols = {c.lower().strip(): c for c in df.columns}
    if "category" not in cols or "brand" not in cols:
        raise ValueError("Excel must have 'category' and 'brand' columns.")
    cat_col, brand_col = cols["category"], cols["brand"]
    df = df[[cat_col, brand_col]].dropna()
    cats = df[cat_col].dropna().unique().tolist()
    brands_by_cat = {
        cat: df.loc[df[cat_col] == cat, brand_col].dropna().unique().tolist()
        for cat in cats
    }
    # remove empties
    brands_by_cat = {c: b for c, b in brands_by_cat.items() if len(b) > 0}
    cats = [c for c in cats if c in brands_by_cat]
    return cats, brands_by_cat

# -------- payload builders --------
def build_mat_compare(cat):
    measure = random.choice(["value_sales","unit_sales"])
    years = random.sample([2025, 2024, 2023, 2022], 3)
    years.sort(reverse=True)
    anchor_month = random.choice([3, 6, 9, 12])  # Mar/Jun/Sep/Dec
    periods = []
    # synthetic but consistent magnitudes by measure
    base_low, base_high = (5e6, 8e6) if measure == "value_sales" else (5e5, 1.2e6)
    for y in years:
        st, en = mat_window_for(y, anchor_month)
        val = float(np.random.uniform(* (base_low, base_high)))
        periods.append({"mat_label": f"MAT {y}", "start": st, "end": en, measure: val})
    return {
        "mode": "MAT_COMPARE",
        "measure": measure,
        "window": {"start": periods[-1]["start"], "end": periods[0]["end"]},
        "dims": ["mat_label"],
        "filters": {"category": cat},
        "mat_compare": {
            "mat_compare": {
                "anchor_month": anchor_month,
                "years": years,
                "labels": [f"MAT {y}" for y in years],
            },
            "periods": periods,
            "chart_type": "bar",
            "rowcount": len(periods),
        },
        "calculation_mode": "mat_compare",
    }

def build_yoy_by_brand(cat, brands):
    measure_type = random.choice(["value","unit"])
    measure = f"{measure_type}_yoy"
    # choose 2–3 brands from this category
    pick = random.sample(brands, min(len(brands), random.choice([2,3])))
    items=[]
    for b in pick:
        prev = float(np.random.uniform(3e5, 8e5)) if measure_type=="unit" else float(np.random.uniform(5e6, 1.2e7))
        growth = np.random.uniform(0.90, 1.20)  # -10% to +20%
        curr = float(prev * growth)
        items.append({"brand": b, "prev": prev, "curr": curr, "yoy_pct": (curr/prev - 1)})
    # simple window (random quarter)
    y = random.choice([2023, 2024, 2025])
    start_m = random.choice([1, 4, 7, 10])
    end_m = start_m + 2
    return {
        "mode": "BAR",
        "measure": measure,
        "window": {"start": month_start(y, start_m), "end": month_end(y, end_m)},
        "dims": ["brand"],
        "filters": {"category": cat},
        "yoy": {"measure_type": measure_type, "items": items},
        "bar": {"x": "brand", "y": measure,
                "items": [{"rank": i+1, "label": it["brand"], "value": it["yoy_pct"]} for i, it in enumerate(sorted(items, key=lambda z: z["yoy_pct"], reverse=True))]},
        "calculation_mode": "YOY",
    }

def build_total_for_brand(cat, brands):
    measure = random.choice(["value_sales","unit_sales"])
    b = random.choice(brands)
    val = float(np.random.uniform(8e5,2e6)) if measure=="unit_sales" else float(np.random.uniform(5e6,1.2e7))
    # random full-year window
    y = random.choice([2022, 2023, 2024])
    return {
        "mode": "BAR",
        "measure": measure,
        "window": {"start": month_start(y,1), "end": month_end(y,12)},
        "dims": [],
        "filters": {"category": cat, "brand": [b]},
        "bar": {"x": "brand", "y": measure, "items": [{"rank": 1, "label": b, "value": val}]},
        "calculation_mode": f"total {measure} sales",
    }

def build_trend_by_brand(cat, brands):
    measure = random.choice(["value_sales","unit_sales"])
    pick = random.sample(brands, min(len(brands), 3))
    y = random.choice([2022, 2023, 2024])
    by_brand=[]
    for b in pick:
        vals=[float(np.random.uniform(7e5,1.6e6)) if measure=="unit_sales" else float(np.random.uniform(6e6,1.8e7)) for _ in range(12)]
        minm, maxm = np.argmin(vals)+1, np.argmax(vals)+1
        by_brand.append({
            "brand": b,
            "min": {"value": float(min(vals)), "period": f"{y}-{minm:02d}", "label": month_label(y, minm)},
            "max": {"value": float(max(vals)), "period": f"{y}-{maxm:02d}", "label": month_label(y, maxm)},
        })
    return {
        "mode": "LINE",
        "measure": measure,
        "window": {"start": month_start(y,1), "end": month_end(y,12)},
        "dims": ["brand"],
        "filters": {"category": cat, "brand": pick},
        "trend": {"measure": measure, "by_brand": by_brand,
                  "overall": {
                      "min": min((x["min"] for x in by_brand), key=lambda z: z["value"]),
                      "max": max((x["max"] for x in by_brand), key=lambda z: z["value"]),
                  }},
        "calculation_mode": f"total {measure}",
    }

# -------- insight variants (3–4 sentences each) --------
def insight_variants(payload):
    cat = payload.get("filters", {}).get("category", "")
    meas = payload.get("measure", "")
    nice_meas = {"value_sales": "value sales", "unit_sales": "unit sales",
                 "value_yoy": "value YoY", "unit_yoy": "unit YoY"}.get(meas, meas)

    out = []

    if payload["mode"] == "MAT_COMPARE":
        periods = payload["mat_compare"]["periods"]
        best = max(periods, key=lambda p: p.get("value_sales", p.get("unit_sales", 0)))
        worst = min(periods, key=lambda p: p.get("value_sales", p.get("unit_sales", 0)))
        out += [
            f"In {cat}, the strongest {nice_meas} was in {best['mat_label']} and the weakest in {worst['mat_label']}.",
            f"MAT comparison for {cat} shows {best['mat_label']} leading overall.",
            f"{cat}: {best['mat_label']} outperformed {worst['mat_label']} on {nice_meas}.",
            f"Across years, {cat} peaked at {best['mat_label']} for {nice_meas}.",
        ]

    elif payload["mode"] == "BAR" and "yoy" in payload:
        items = payload["yoy"]["items"]
        items_sorted = sorted(items, key=lambda x: x["yoy_pct"], reverse=True)
        top = items_sorted[0]
        last = items_sorted[-1]
        out += [
            f"In {cat}, {top['brand']} leads YoY with {top['yoy_pct']:.1%}.",
            f"{top['brand']} shows the strongest YoY momentum in {cat}, while {last['brand']} trails.",
            f"{cat} YoY snapshot: best is {top['brand']} at {top['yoy_pct']:.1%}.",
            f"Year-over-year, {top['brand']} improved the most in {cat}.",
        ]

    elif payload["mode"] == "BAR" and "bar" in payload:
        item = payload["bar"]["items"][0]
        out += [
            f"{cat}: {item['label']} total {nice_meas} is {item['value']:.0f}.",
            f"Total {nice_meas} for {item['label']} in {cat} is {item['value']:.0f}.",
            f"{item['label']} recorded {item['value']:.0f} in {nice_meas} for {cat}.",
        ]

    elif payload["mode"] == "LINE" and "trend" in payload:
        bb = payload["trend"]["by_brand"]
        best_peak = max(bb, key=lambda b: b["max"]["value"])
        out += [
            f"In {cat}, {best_peak['brand']} reached the highest monthly {nice_meas} at {best_peak['max']['label']}.",
            f"Trend view ({cat}): {best_peak['brand']} shows the strongest monthly peak.",
            f"{cat} trend: multiple brands vary month-to-month; {best_peak['brand']} peaks highest.",
        ]

    # cap at 4
    return out[:4] if len(out) > 4 else out

# -------- main driver --------
if __name__=="__main__":
    cats, brands_by_cat = load_entities(EXCEL_PATH)

    Path(OUTPUT_JSONL).write_text("", encoding="utf-8")         # clear
    Path(OUTPUT_PAIRS_JSONL).write_text("", encoding="utf-8")   # clear

    with open(OUTPUT_JSONL, "a", encoding="utf-8") as f_payloads, \
         open(OUTPUT_PAIRS_JSONL, "a", encoding="utf-8") as f_pairs:

        total = 0
        for cat in cats:
            brands = brands_by_cat[cat]
            for _ in range(N_SAMPLES_PER_TYPE):
                samples = [
                    build_mat_compare(cat),
                    build_yoy_by_brand(cat, brands),
                    build_total_for_brand(cat, brands),
                    build_trend_by_brand(cat, brands),
                ]
                for s in samples:
                    insights = insight_variants(s)
                    f_payloads.write(json.dumps(s) + "\n")
                    f_pairs.write(json.dumps({"payload": s, "insights": insights}) + "\n")
                    total += 1

    print(f"Done. Wrote {total} payloads.")
    print(f"• Payloads only: {OUTPUT_JSONL}")
    print(f"• Payload + insights pairs: {OUTPUT_PAIRS_JSONL}")