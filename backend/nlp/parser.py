import re
from datetime import datetime
from .intent_schema import Intent, TimeRange, SortSpec

# MEASURE_KEYWORDS = {
#     "value": "value_sales",
#     "sales": "value_sales",
#     "units": "unit_sales",
#     "share": "share",
#     "yoy": "value_yoy",
#     "value_yoy": "value_yoy",
#     "share_yoy": "share_yoy"
# }

# def parse_user_text(text: str) -> Intent:
#     t = text.lower()
#     intent = Intent()

#     # task
#     if any(k in t for k in ["trend", "over time", "timeseries", "time series", "line chart"]):
#         intent.task = "chart"
#         if "date" not in intent.dims:
#             intent.dims = ["date"]
#     elif any(k in t for k in ["top", "bottom", "table", "rank"]):
#         intent.task = "table"
#     elif any(k in t for k in ["explain", "insight", "summary"]):
#         intent.task = "text"

#     # measures
#     for k, m in MEASURE_KEYWORDS.items():
#         if re.search(rf"\b{k}\b", t):
#             if m not in intent.measures:
#                 intent.measures.append(m)
#     intent.measures = list(dict.fromkeys(intent.measures))  # dedup
#     if not intent.measures:
#         intent.measures = ["value_sales"]

#     # dims
#     if any(x in t for x in ["brand", "brands"]):
#         if "brand" not in intent.dims: intent.dims.append("brand")
#     if any(x in t for x in ["category", "segment"]):
#         if "category" not in intent.dims: intent.dims.append("category")
#     if "market" in t or "country" in t:
#         if "market" not in intent.dims: intent.dims.append("market")
#     if "channel" in t:
#         if "channel" not in intent.dims: intent.dims.append("channel")

#     # top N
#     m = re.search(r"top\s+(\d+)", t)
#     if m:
#         n = int(m.group(1))
#         intent.sort = SortSpec(by="value_sales", order="desc", limit=n)
#     if "yoy" in t and (intent.sort.by is None):
#         intent.sort.by = "value_yoy"

#     # If the user mentions YoY with a "top/bottom" query,
# # sort by YoY and aggregate by brand (no date in dims).
#     if ("yoy" in t or "value_yoy" in t) and any(k in t for k in ["top", "bottom"]):
#         intent.sort.by = "value_yoy"
#         # keep brand/category/market if present, but remove date for ranking
#         intent.dims = [d for d in intent.dims if d != "date"]
#         if "brand" not in intent.dims:
#             intent.dims.append("brand")

#     # time range - last 12 months
#     if "last 12" in t or "last twelve" in t:
#         now = datetime.utcnow()
#         start = f"{now.year-1}-{now.month:02d}"
#         end = f"{now.year}-{now.month:02d}"
#         intent.time_range = TimeRange(start=start, end=end)
    

#     # simple filters (quoted values)
#     for dim in ["category","market","channel","brand"]:
#         m = re.search(rf'{dim}\s*[:=]\s*"([^"]+)"', t)

#         if m:
#             intent.filters[dim] = m.group(1)

#     return intent

# def intent_to_sql(intent: Intent, table: str = "fact") -> str:
#     if intent.sort and intent.sort.by == "value_yoy" and "brand" in intent.dims:
#         category = (intent.filters.get("category") or "")
#         market   = (intent.filters.get("market") or "")
#         limit    = intent.sort.limit or 5

#         return f"""
#         WITH bounds AS (
#         SELECT
#             date_trunc('month', current_date)                     AS cur_month_start,
#             date_trunc('month', current_date) - INTERVAL 12 MONTH AS last12_start,
#             date_trunc('month', current_date) - INTERVAL 24 MONTH AS prev12_start
#         ),
#         last12 AS (
#         SELECT brand, category, market, SUM(value_sales) AS mat_curr
#         FROM {table}, bounds
#         WHERE lower(category)=lower('{category}')
#             AND lower(market)=lower('{market}')
#             AND date >= last12_start AND date < cur_month_start
#         GROUP BY brand, category, market
#         ),
#         prev12 AS (
#         SELECT brand, category, market, SUM(value_sales) AS mat_prev
#         FROM {table}, bounds
#         WHERE lower(category)=lower('{category}')
#             AND lower(market)=lower('{market}')
#             AND date >= prev12_start AND date < last12_start
#         GROUP BY brand, category, market
#         )
#         SELECT
#         l.brand, l.category, l.market,
#         l.mat_curr AS value_sales_mat,
#         CASE WHEN p.mat_prev IS NULL OR p.mat_prev = 0 THEN NULL
#             ELSE l.mat_curr / p.mat_prev - 1 END AS value_yoy
#         FROM last12 l
#         LEFT JOIN prev12 p
#         ON l.brand=p.brand AND l.category=p.category AND l.market=p.market
#         ORDER BY value_yoy DESC NULLS LAST
#         LIMIT {limit}
#         """.strip()


#     cols = []
#     aggs = []
#     for m in intent.measures:
#         if m in ("value_sales","unit_sales","share"):
#             aggs.append(f"sum({m}) as {m}")
#         else:
#             # for yoy metrics, just average to keep simple
#             aggs.append(f"avg({m}) as {m}")
#     dims = intent.dims or []
#     select_parts = []
#     if dims: select_parts += dims
#     select_parts += [a for a in aggs]
#     select_clause = ", ".join(select_parts) if select_parts else "*"
#     # where = []
#     # for k, v in (intent.filters or {}).items():
#     #     safe_v = v.replace("'", "''")   # escape quotes for SQL
#     #     where.append(f"{k} = '{safe_v}'")

#     where = []
#     for k, v in (intent.filters or {}).items():
#         safe_v = v.replace("'", "''")
#         where.append(f"lower({k}) = lower('{safe_v}')")
#     if intent.time_range and intent.time_range.start and intent.time_range.end:
#         where.append(f"date between '{intent.time_range.start}-01' and '{intent.time_range.end}-28'")

#     where_clause = f"WHERE {' AND '.join(where)}" if where else ""
#     group_clause = f"GROUP BY {', '.join(dims)}" if dims else ""
#     order_clause = ""
#     limit_clause = ""

#     if intent.sort and intent.sort.by:
#         order_clause = f"ORDER BY {intent.sort.by} {intent.sort.order or 'desc'}"
#     if intent.sort and intent.sort.limit:
#         limit_clause = f"LIMIT {intent.sort.limit}"

#     sql = f"""SELECT {select_clause}
# FROM {table}
# {where_clause}
# {group_clause}
# {order_clause}
# {limit_clause}
# """.strip()
#     return sql



import re
from datetime import datetime, timedelta
from .intent_schema import Intent, TimeRange, SortSpec

# ---- measure keyword map ----
MEASURE_KEYWORDS = {
    "value": "value_sales",
    "sales": "value_sales",
    "units": "unit_sales",
    "share": "share",
    "yoy": "value_yoy",
    "value_yoy": "value_yoy",
    "share_yoy": "share_yoy",
}

# ---- helpers ----
def _last_complete_month_anchor():
    """Return (year, month) of the last fully complete month (UTC)."""
    today = datetime.utcnow()
    first_of_cur = today.replace(day=1)
    last_full = first_of_cur - timedelta(days=1)
    return last_full.year, last_full.month


# -------------------------- INTENT PARSER --------------------------
def parse_user_text(text: str) -> Intent:
    t = text.lower()
    intent = Intent()

    # task
    if any(k in t for k in ["trend", "over time", "timeseries", "time series", "line chart"]):
        intent.task = "chart"
        if "date" not in intent.dims:
            intent.dims = ["date"]
    elif any(k in t for k in ["top", "bottom", "table", "rank"]):
        intent.task = "table"
    elif any(k in t for k in ["explain", "insight", "summary"]):
        intent.task = "text"

    # measures
    for k, m in MEASURE_KEYWORDS.items():
        if re.search(rf"\b{k}\b", t):
            if m not in intent.measures:
                intent.measures.append(m)
    # detect "share change"/"pp change"
    if re.search(r"(share.*(change|delta|pp))|((change|delta).*\bshare\b)", t):
        if "share_change" not in intent.measures:
            intent.measures.append("share_change")

    # defaults
    if not intent.measures:
        intent.measures = ["value_sales"]

    # dims
    if any(x in t for x in ["brand", "brands"]):
        if "brand" not in intent.dims: intent.dims.append("brand")
    if any(x in t for x in ["category", "segment"]):
        if "category" not in intent.dims: intent.dims.append("category")
    if "market" in t or "country" in t:
        if "market" not in intent.dims: intent.dims.append("market")
    if "channel" in t:
        if "channel" not in intent.dims: intent.dims.append("channel")

    # top N
    m = re.search(r"top\s+(\d+)", t)
    if m:
        n = int(m.group(1))
        intent.sort = SortSpec(by="value_sales", order="desc", limit=n)

    if "yoy" in t:
        if intent.sort is None:
            intent.sort = SortSpec()
        if intent.sort.by is None:
            intent.sort.by = "value_yoy"

    # If YoY + top/bottom → rank by YoY and aggregate by brand (no date)
    if ("yoy" in t or "value_yoy" in t) and any(k in t for k in ["top", "bottom"]):
        if intent.sort is None:
            intent.sort = SortSpec()
        intent.sort.by = "value_yoy"
        intent.dims = [d for d in intent.dims if d != "date"]
        if "brand" not in intent.dims:
            intent.dims.append("brand")

    # time ranges
    # last 12 complete months
    if "last 12" in t or "last twelve" in t:
        y_end, m_end = _last_complete_month_anchor()
        # start = end - 11 months (inclusive months; SQL will make end exclusive)
        # compute start year/month safely
        start_idx = (y_end * 12 + (m_end - 1)) - 11
        start_y, start_m = divmod(start_idx, 12)
        start_m += 1
        intent.time_range = TimeRange(
            start=f"{start_y:04d}-{start_m:02d}",
            end=f"{y_end:04d}-{m_end:02d}",
        )

    # YTD: Jan 1 → end of last complete month of current year
    if "ytd" in t or "year to date" in t or "year-to-date" in t:
        y_end, m_end = _last_complete_month_anchor()
        intent.time_range = TimeRange(
            start=f"{y_end:04d}-01",
            end=f"{y_end:04d}-{m_end:02d}",
        )

    # filters: quoted values category:"Biscuits", market:"India", etc.
    for dim in ["category", "market", "channel", "brand"]:
        m = re.search(rf'{dim}\s*[:=]\s*"([^"]+)"', t)
        if m:
            intent.filters[dim] = m.group(1)

    return intent


# -------------------------- SQL GENERATOR --------------------------
def intent_to_sql(intent: Intent, table: str = "fact") -> str:
    # 1) Top brands by YoY (MAT: last 12 complete months vs previous 12)
    if intent.sort and intent.sort.by == "value_yoy" and "brand" in intent.dims:
        category = (intent.filters.get("category") or "")
        market   = (intent.filters.get("market") or "")
        limit    = intent.sort.limit or 5
        return f"""
WITH bounds AS (
  SELECT
    date_trunc('month', current_date)                        AS cur_month_start,
    date_trunc('month', current_date) - INTERVAL 12 MONTH    AS last12_start,
    date_trunc('month', current_date) - INTERVAL 24 MONTH    AS prev12_start
),
last12 AS (
  SELECT brand, category, market, SUM(value_sales) AS mat_curr
  FROM {table}, bounds
  WHERE lower(category)=lower('{category}')
    AND lower(market)=lower('{market}')
    AND date >= last12_start AND date < cur_month_start
  GROUP BY brand, category, market
),
prev12 AS (
  SELECT brand, category, market, SUM(value_sales) AS mat_prev
  FROM {table}, bounds
  WHERE lower(category)=lower('{category}')
    AND lower(market)=lower('{market}')
    AND date >= prev12_start AND date < last12_start
  GROUP BY brand, category, market
)
SELECT
  l.brand, l.category, l.market,
  l.mat_curr AS value_sales_mat,
  CASE WHEN p.mat_prev IS NULL OR p.mat_prev = 0 THEN NULL
       ELSE l.mat_curr / p.mat_prev - 1 END AS value_yoy
FROM last12 l
LEFT JOIN prev12 p
  ON l.brand=p.brand AND l.category=p.category AND l.market=p.market
ORDER BY value_yoy DESC NULLS LAST
LIMIT {limit}
""".strip()

    # 2) Share change (pp) by brand over the selected window (or last 12 by default)
    if "share_change" in intent.measures and "brand" in intent.dims:
        category = (intent.filters.get("category") or "")
        market   = (intent.filters.get("market") or "")
        limit    = (intent.sort.limit if intent.sort else None) or 10

        if intent.time_range and intent.time_range.start and intent.time_range.end:
            s = intent.time_range.start  # YYYY-MM
            e = intent.time_range.end    # YYYY-MM
            return f"""
WITH win AS (
  SELECT
    date_trunc('month', DATE '{s}-01')                                       AS cur_start,
    (date_trunc('month', DATE '{e}-01') + INTERVAL 1 MONTH)                  AS cur_end_excl,
    (date_trunc('month', DATE '{s}-01') - INTERVAL 12 MONTH)                 AS prev_start,
    ((date_trunc('month', DATE '{e}-01') + INTERVAL 1 MONTH) - INTERVAL 12 MONTH) AS prev_end_excl
)
),
cur_brand AS (
  SELECT f.brand, SUM(f.value_sales) AS vs
  FROM {table} f, win
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= win.cur_start AND f.date < win.cur_end_excl
  GROUP BY f.brand
),
cur_total AS (
  SELECT SUM(f.value_sales) AS vs_total
  FROM {table} f, win
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= win.cur_start AND f.date < win.cur_end_excl
),
prev_brand AS (
  SELECT f.brand, SUM(f.value_sales) AS vs
  FROM {table} f, win
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= win.prev_start AND f.date < win.prev_end_excl
  GROUP BY f.brand
),
prev_total AS (
  SELECT SUM(f.value_sales) AS vs_total
  FROM {table} f, win
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= win.prev_start AND f.date < win.prev_end_excl
)
SELECT
  cb.brand,
  (cb.vs / NULLIF(ct.vs_total,0)) * 100.0 AS share_curr_pp,
  (pb.vs / NULLIF(pt.vs_total,0)) * 100.0 AS share_prev_pp,
  ((cb.vs / NULLIF(ct.vs_total,0)) - (pb.vs / NULLIF(pt.vs_total,0))) * 100.0 AS share_change_pp
FROM cur_brand cb
CROSS JOIN cur_total ct
LEFT JOIN prev_brand pb ON pb.brand = cb.brand
CROSS JOIN prev_total pt
ORDER BY share_change_pp DESC NULLS LAST
LIMIT {limit}
""".strip()
        else:
            # default: last 12 complete months vs previous 12
            return f"""
WITH bounds AS (
  SELECT
    date_trunc('month', current_date)                       AS cur_m,
    (date_trunc('month', current_date) - INTERVAL 12 MONTH) AS cur_start,
    (date_trunc('month', current_date) - INTERVAL 24 MONTH) AS prev_start
)
),
cur_brand AS (
  SELECT f.brand, SUM(f.value_sales) AS vs
  FROM {table} f, bounds
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= cur_start AND f.date < cur_m
  GROUP BY f.brand
),
cur_total AS (
  SELECT SUM(f.value_sales) AS vs_total
  FROM {table} f, bounds
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= cur_start AND f.date < cur_m
),
prev_brand AS (
  SELECT f.brand, SUM(f.value_sales) AS vs
  FROM {table} f, bounds
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= prev_start AND f.date < cur_start
  GROUP BY f.brand
),
prev_total AS (
  SELECT SUM(f.value_sales) AS vs_total
  FROM {table} f, bounds
  WHERE lower(f.category)=lower('{category}')
    AND lower(f.market)=lower('{market}')
    AND f.date >= prev_start AND f.date < cur_start
)
SELECT
  cb.brand,
  (cb.vs / NULLIF(ct.vs_total,0)) * 100.0 AS share_curr_pp,
  (pb.vs / NULLIF(pt.vs_total,0)) * 100.0 AS share_prev_pp,
  ((cb.vs / NULLIF(ct.vs_total,0)) - (pb.vs / NULLIF(pt.vs_total,0))) * 100.0 AS share_change_pp
FROM cur_brand cb
CROSS JOIN cur_total ct
LEFT JOIN prev_brand pb ON pb.brand = cb.brand
CROSS JOIN prev_total pt
ORDER BY share_change_pp DESC NULLS LAST
LIMIT {limit}
""".strip()

    # 3) Generic SELECT (uses time_range if present)
    aggs = []
    for m in intent.measures:
        if m in ("value_sales", "unit_sales", "share"):
            aggs.append(f"sum({m}) as {m}")
        else:
            aggs.append(f"avg({m}) as {m}")  # simple placeholder

    dims = intent.dims or []
    select_parts = []
    if dims:
        select_parts += dims
    select_parts += aggs
    select_clause = ", ".join(select_parts) if select_parts else "*"

    where = []
    for k, v in (intent.filters or {}).items():
        safe_v = v.replace("'", "''")
        where.append(f"lower({k}) = lower('{safe_v}')")

    # Convert YYYY-MM to exact month window: start inclusive, end exclusive
    # Convert YYYY-MM to exact month window: start inclusive, end exclusive
    if intent.time_range and intent.time_range.start and intent.time_range.end:
        s = intent.time_range.start  # 'YYYY-MM'
        e = intent.time_range.end    # 'YYYY-MM'
        where.append(
            f"date >= date_trunc('month', DATE '{s}-01') "
            f"AND date < (date_trunc('month', DATE '{e}-01') + INTERVAL 1 MONTH)"
        )


    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    group_clause = f"GROUP BY {', '.join(dims)}" if dims else ""
    order_clause = ""
    limit_clause = ""
    if intent.sort and intent.sort.by:
        order_clause = f"ORDER BY {intent.sort.by} {intent.sort.order or 'desc'}"
    if intent.sort and intent.sort.limit:
        limit_clause = f"LIMIT {intent.sort.limit}"

    sql = f"""SELECT {select_clause}
FROM {table}
{where_clause}
{group_clause}
{order_clause}
{limit_clause}
""".strip()
    return sql
