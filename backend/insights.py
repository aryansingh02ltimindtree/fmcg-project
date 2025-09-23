# backend/insights.py

from __future__ import annotations

import numpy as np

import pandas as pd

CAT_CANDS = ["brand", "category", "market", "channel", "segment", "manufacturer"]

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

    return f"{x*100:.1f}%"

def generate_simple_insights(df: pd.DataFrame, meta: dict) -> list[str]:

    """

    Heuristic, lightweight insights that never fail silently.

    Works for table/bar/line; time or no time; any dim.

    """

    insights: list[str] = []

    # --- guardrails ---

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:

        return ["No data to analyze."]

    # DEBUG (keep if helpful)

    print("DEBUG INSIGHTS >>> cols:", df.columns.tolist())

    print("DEBUG INSIGHTS >>> meta:", meta)

    # Choose measure (y)

    y = _pick_measure_col(df, meta)

    if y is None:

        # No numeric measure → at least say something

        insights.append("No numeric measure returned, so only structural results are shown.")

        return insights

    # Pick a categorical dim if present

    cat = _pick_cat_dim(df)

    # Detect time

    has_date = "date" in df.columns

    has_month = "month_year" in df.columns

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

            # build a sortable month from month_year

            parsed = pd.to_datetime(d["month_year"], errors="coerce")

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

                        insights.append(

                            f"{top_brand} leads most recently with {_format_num(top_val)} {y.replace('_',' ')} "

                            f"({dir_word} {_format_pct(abs(chg))} vs previous point)."

                        )

                # Gap to #2 at the last point

                if len(grp) >= 2:

                    gap = grp.iloc[0] - grp.iloc[1]

                    insights.append(

                        f"Gap between {grp.index[0]} and {grp.index[1]} is {_format_num(gap)} on the latest point."

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

                    insights.append(

                        f"Latest {_format_num(last_val)} {y.replace('_',' ')}; {dir_word} {_format_pct(abs(chg))} vs previous point."

                    )

    # ---------------- CATEGORICAL INSIGHTS ----------------

    if cat and cat in d.columns:

        grp = d.groupby(cat, dropna=False)[y].sum().sort_values(ascending=False)

        if not grp.empty:

            top_k = grp.head(3)

            names = ", ".join(f"{idx} ({_format_num(val)})" for idx, val in top_k.items())

            insights.append(f"Top {cat}s by {y.replace('_',' ')}: {names}.")

            if grp.sum() > 0:

                shares = (grp / grp.sum()).head(3)

                share_txt = ", ".join(f"{idx} {_format_pct(v)}" for idx, v in shares.items())

                insights.append(f"Share of total {y.replace('_',' ')}: {share_txt}.")

    # ---------------- FALLBACK / TOTAL ----------------

    if not insights:

        total = pd.to_numeric(d[y], errors="coerce").sum()

        insights.append(f"Total {y.replace('_',' ')} in the shown result: {_format_num(total)}.")
    print(insights)

    # Cap to 3 neat bullets

    return insights[:3]