# # Working code MAT YoY,YTD, TopN, Brand Grouping
# # backend/nlp/parser.py

# import re
# from datetime import datetime, timedelta
# from .intent_schema import Intent, TimeRange, SortSpec


# # --- add near the top of parser.py (after imports) ---
# import re
# from datetime import datetime, timedelta
# from .intent_schema import Intent, TimeRange, SortSpec

# # map month words to month numbers (short or long)
# _MONTH_MAP = {
#     "jan": 1, "january": 1,
#     "feb": 2, "february": 2,
#     "mar": 3, "march": 3,
#     "apr": 4, "april": 4,
#     "may": 5,
#     "jun": 6, "june": 6,
#     "jul": 7, "july": 7,
#     "aug": 8, "august": 8,
#     "sep": 9, "sept": 9, "september": 9,
#     "oct": 10, "october": 10,
#     "nov": 11, "november": 11,
#     "dec": 12, "december": 12,
# }

# # matches "jan 2024", "january 2024", etc.
# # Month name + 4-digit year (e.g., "Jan 2024", "september 2025")
# BY_BRAND_RE = re.compile(r"\bby\s+brand(s)?\b", re.IGNORECASE)

# _MONTH_YR_RE = re.compile(r"""
#     \b
#     ( jan(?:uary)? |
#       feb(?:ruary)? |
#       mar(?:ch)? |
#       apr(?:il)? |
#       may |
#       jun(?:e)? |
#       jul(?:y)? |
#       aug(?:ust)? |
#       sep(?:t(?:ember)?)? |
#       oct(?:ober)? |
#       nov(?:ember)? |
#       dec(?:ember)? )
#     \W*           # space or punctuation between month and year
#     (\d{4})
#     \b
# """, re.IGNORECASE | re.VERBOSE)


# def _parse_month_year_range_freeform(text: str):
#     """
#     Find two month-year mentions in order and return ('YYYY-MM', 'YYYY-MM').
#     Handles phrases like:
#       - 'from Jan 2024 to Mar 2025'
#       - 'between January 2024 and March 2025'
#       - 'Jan 2024 to March 2025'
#     If fewer than two mentions are found, returns None.
#     """
#     t = text.lower()
#     hits = list(_MONTH_YR_RE.finditer(t))
#     if len(hits) < 2:
#         return None

#     # prefer pairs connected by 'to' or 'and' if present; otherwise, first two hits
#     # (simple heuristic that works well for natural queries)
#     start_m, start_y = hits[0].group(1), hits[0].group(2)
#     end_m, end_y     = hits[1].group(1), hits[1].group(2)

#     sm = _MONTH_MAP[start_m]   # month number
#     em = _MONTH_MAP[end_m]

#     start = f"{int(start_y):04d}-{sm:02d}"
#     end   = f"{int(end_y):04d}-{em:02d}"
#     return start, end


# # (existing) helper kept as-is
# def _last_complete_month_anchor():
#     today = datetime.utcnow()
#     first_of_cur = today.replace(day=1)
#     last_full = first_of_cur - timedelta(days=1)
#     return last_full.year, last_full.month



# # ---- measure keyword map (detect & normalize) ----
# MEASURE_KEYWORDS = {
#     "value": "value_sales",
#     "sales": "value_sales",
#     "value sales": "value_sales",

#     # unit sales (aliases)
#     "unit": "unit_sales",
#     "units": "unit_sales",
#     "unit sales": "unit_sales",

#     "share": "share",
#     "yoy": "value_yoy",
#     "value_yoy": "value_yoy",
#     "share_yoy": "share_yoy",
# }

# # ---- MoM trigger phrases (Month-over-Month) ----
# MOM_KEYWORDS = [
#     "mom",
#     "m/m",
#     "month over month",
#     "monthly change",
#     "mom growth",
# ]

# # ---- helpers ----
# def _last_complete_month_anchor():
#     """Return (year, month) of the last fully complete calendar month (UTC)."""
#     today = datetime.utcnow()
#     first_of_cur = today.replace(day=1)
#     last_full = first_of_cur - timedelta(days=1)
#     return last_full.year, last_full.month


# # -------------------------- INTENT PARSER --------------------------
# def parse_user_text(text: str) -> Intent:
#     """
#     Parse a free-text question into a structured Intent (no SQL!).
#     """
#     t = text.lower()
#     intent = Intent()

#     # --- task ---
#     if any(k in t for k in ["trend", "over time", "timeseries", "time series", "line chart", "chart"]):
#         intent.task = "chart"
#         if "date" not in intent.dims:
#             intent.dims = ["date"]
#     elif any(k in t for k in ["top", "bottom", "table", "rank"]):
#         intent.task = "table"
#     elif any(k in t for k in ["explain", "insight", "summary"]):
#         intent.task = "text"

#     # --- measures ---
#     for k, m in MEASURE_KEYWORDS.items():
#         if re.search(rf"\b{k}\b", t):
#             if m not in intent.measures:
#                 intent.measures.append(m)
#     if re.search(r"(share.*(change|delta|pp))|((change|delta).*\bshare\b)", t):
#         if "share_change" not in intent.measures:
#             intent.measures.append("share_change")
#     if "unit_sales" in intent.measures and "value_sales" in intent.measures:
#         intent.measures = ["unit_sales"]
#     if not intent.measures:
#         intent.measures = ["value_sales"]

#     # --- dims ---
#    # --- dims ---

# # Only add BRAND if the user explicitly asks to group by it
# # e.g. "by brand", "per brand", "brand-wise", or a ranking query (Top/Bottom)
#   # --- NEW: infer "group by brand" from phrasing ---
#     brand_group = False
#     if re.search(r"\bby\s+brand\b", t) or re.search(r"\btop(\s+\d+)?\s+brands?\b", t):
#         brand_group = True
#     # but if user fixed a single brand, don't group
#     if "brand" in intent.filters:
#         brand_group = False

#     # ensure 'brand' in dims when we'll group by brand
#     if brand_group and "brand" not in intent.dims:
#         intent.dims.append("brand")

#     # carry the flag
#     try:
#         intent.brand_group = brand_group
#     except Exception:
#         pass


#     # --- top N ---
#     m = re.search(r"top\s+(\d+)", t)
#     if m:
#         n = int(m.group(1))
#         intent.sort = SortSpec(by="value_sales", order="desc", limit=n)
#     if "yoy" in t:
#         if intent.sort is None:
#             intent.sort = SortSpec()
#         if intent.sort.by is None:
#             intent.sort.by = "value_yoy"
#     if ("yoy" in t or "value_yoy" in t) and any(k in t for k in ["top", "bottom"]):
#         if intent.sort is None:
#             intent.sort = SortSpec()
#         intent.sort.by = "value_yoy"
#         intent.dims = [d for d in intent.dims if d != "date"]
#         if "brand" not in intent.dims:
#             intent.dims.append("brand")

#     # --- MoM ---
#     if any(k in t for k in MOM_KEYWORDS):
#         try:
#             intent.mom = True
#         except Exception:
#             pass
#         if intent.sort is None:
#             intent.sort = SortSpec()
#         if intent.sort.by is None:
#             intent.sort.by = "value_mom"

#     # --- explicit month-year ranges (NEW) ---
#     rng = _parse_month_year_range_freeform(t)
#     if rng:
#         start, end = rng
#         intent.time_range = TimeRange(start=start, end=end)

#     # --- fallback ranges ---
#     if not intent.time_range and ("last 12" in t or "last twelve" in t):
#         y_end, m_end = _last_complete_month_anchor()
#         start_idx = (y_end * 12 + (m_end - 1)) - 11
#         start_y, start_m = divmod(start_idx, 12)
#         start_m += 1
#         intent.time_range = TimeRange(
#             start=f"{start_y:04d}-{start_m:02d}",
#             end=f"{y_end:04d}-{m_end:02d}",
#         )
#     if not intent.time_range and ("ytd" in t or "year to date" in t or "year-to-date" in t):
#         y_end, m_end = _last_complete_month_anchor()
#         intent.time_range = TimeRange(
#             start=f"{y_end:04d}-01",
#             end=f"{y_end:04d}-{m_end:02d}",
#         )

#     # --- filters ---
#     # --- filters: category:"Biscuits", category:'Biscuits', or even category: Biscuits ---
#     for dim in ["category", "market", "channel", "brand"]:
#         # 1) quoted with "..." or '...'
#         m = re.search(rf'{dim}\s*[:=]\s*([\'"])(.+?)\1', t, flags=re.IGNORECASE)
#         if m:
#             intent.filters[dim] = m.group(2).strip()
#             continue
#         # 2) unquoted single token (letters / spaces until next key or end)
#         m = re.search(rf'{dim}\s*[:=]\s*([a-zA-Z][a-zA-Z\s\-&]+)', t, flags=re.IGNORECASE)
#         if m:
#             intent.filters[dim] = m.group(1).strip()

#     return intent


# # -------------------------- DICT CONVERTER (for pandas runner) --------------------------
# import re

# TOPN_RE = re.compile(r"\btop\s+(\d+)", re.IGNORECASE)

# def intent_to_dict(intent: Intent, original_text: str = "") -> dict:
#     t = (original_text or "").lower()

#     # --- task ---
#     task = intent.task or "table"
#     if task == "table" and intent.sort and intent.sort.limit:
#         task = "topn"

#     filters = intent.filters or {}

#     # --- "by brand" grouping intent ---
#     brand_group = bool(BY_BRAND_RE.search(original_text or ""))

#     # --- dims ---
#     dims = intent.dims or []
#     if task == "topn":
#         dims = [d for d in dims if d != "date"]
#     fixed_dims = set(filters.keys()) - ({"brand"} if brand_group else set())
#     dims = [d for d in dims if d not in fixed_dims]
#     if brand_group and "brand" not in dims:
#         dims = ["brand"] + dims  # put brand first for readability

#     # --- time range ---
#     mode = None
#     if any(k in t for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#         mode = "MAT"
#     if any(k in t for k in ["ytd", "year to date", "year-to-date"]):
#         mode = "YTD"
#     if mode:
#         tr = {"mode": mode}
#     elif intent.time_range and intent.time_range.start and intent.time_range.end:
#         tr = {"start": intent.time_range.start, "end": intent.time_range.end}
#     else:
#         tr = None

#     # --- measures + explicit YoY flag ---
#     raw_measures = intent.measures or ["value_sales"]
#     asked_unit   = ("unit_sales" in raw_measures)
#     asked_value  = ("value_sales" in raw_measures)
#     asked_yoy    = ("yoy" in t) or any(m in raw_measures for m in ["value_yoy", "unit_yoy"])

#     # keep sales measure AND (optionally) the matching *_yoy token
#     if asked_unit:
#         measures = ["unit_sales"] + (["unit_yoy"] if asked_yoy else [])
#     elif asked_value:
#         measures = ["value_sales"] + (["value_yoy"] if asked_yoy else [])
#     else:
#         measures = ["value_sales"] + (["value_yoy"] if asked_yoy else [])

#     # --- Top-N detection (parser OR regex fallback) ---
#     top_n = None
#     if intent.sort and intent.sort.limit:
#         top_n = intent.sort.limit
#     else:
#         m = TOPN_RE.search(original_text or "")
#         if m:
#             top_n = int(m.group(1))

#     # --- MoM flag ---
#     is_mom = any(k in t for k in MOM_KEYWORDS)
#     if getattr(intent, "mom", False):
#         is_mom = True

#     # --- sorting defaults ---
#     sort_by    = (intent.sort.by if intent.sort else None)
#     sort_order = (intent.sort.order if intent.sort else "desc")
#     if is_mom and sort_by is None:
#         sort_by = "value_mom"
#     if asked_yoy and sort_by is None:
#         sort_by = "unit_yoy" if "unit_yoy" in measures else "value_yoy"

#     return {
#         "task": task,
#         "dims": dims,
#         "measures": measures,
#         "filters": filters,
#         "time_range": tr,
#         "top_n": top_n,   # ✅ now correctly detects "top 2", "top 3", etc.
#         "sort_by": sort_by,
#         "sort_order": sort_order,
#         "mom": is_mom,
#         "is_yoy": asked_yoy,            # ✅ explicit YoY flag
#         "brand_group": brand_group,
#         "has_brand_filter": ("brand" in filters),
#         "raw_text": original_text or "",
#     }




#Bar chart , Line chart added MAT comparisons remaining , when calculating YoY , MAT charts showing YoY % growth not showing


# import re
# from datetime import datetime, timedelta
# from .intent_schema import Intent, TimeRange, SortSpec


# # --- add near the top of parser.py (after imports) ---
# import re
# from datetime import datetime, timedelta
# from .intent_schema import Intent, TimeRange, SortSpec

# # map month words to month numbers (short or long)
# _MONTH_MAP = {
#     "jan": 1, "january": 1,
#     "feb": 2, "february": 2,
#     "mar": 3, "march": 3,
#     "apr": 4, "april": 4,
#     "may": 5,
#     "jun": 6, "june": 6,
#     "jul": 7, "july": 7,
#     "aug": 8, "august": 8,
#     "sep": 9, "sept": 9, "september": 9,
#     "oct": 10, "october": 10,
#     "nov": 11, "november": 11,
#     "dec": 12, "december": 12,
# }

# # matches "jan 2024", "january 2024", etc.
# # Month name + 4-digit year (e.g., "Jan 2024", "september 2025")
# BY_BRAND_RE = re.compile(r"\bby\s+brand(s)?\b", re.IGNORECASE)

# _MONTH_YR_RE = re.compile(r"""
#     \b
#     ( jan(?:uary)? |
#       feb(?:ruary)? |
#       mar(?:ch)? |
#       apr(?:il)? |
#       may |
#       jun(?:e)? |
#       jul(?:y)? |
#       aug(?:ust)? |
#       sep(?:t(?:ember)?)? |
#       oct(?:ober)? |
#       nov(?:ember)? |
#       dec(?:ember)? )
#     \W*           # space or punctuation between month and year
#     (\d{4})
#     \b
# """, re.IGNORECASE | re.VERBOSE)


# def _parse_month_year_range_freeform(text: str):
#     """
#     Find two month-year mentions in order and return ('YYYY-MM', 'YYYY-MM').
#     Handles phrases like:
#       - 'from Jan 2024 to Mar 2025'
#       - 'between January 2024 and March 2025'
#       - 'Jan 2024 to March 2025'
#     If fewer than two mentions are found, returns None.
#     """
#     t = text.lower()
#     hits = list(_MONTH_YR_RE.finditer(t))
#     if len(hits) < 2:
#         return None

#     # prefer pairs connected by 'to' or 'and' if present; otherwise, first two hits
#     # (simple heuristic that works well for natural queries)
#     start_m, start_y = hits[0].group(1), hits[0].group(2)
#     end_m, end_y     = hits[1].group(1), hits[1].group(2)

#     sm = _MONTH_MAP[start_m]   # month number
#     em = _MONTH_MAP[end_m]

#     start = f"{int(start_y):04d}-{sm:02d}"
#     end   = f"{int(end_y):04d}-{em:02d}"
#     return start, end


# # (existing) helper kept as-is
# def _last_complete_month_anchor():
#     today = datetime.utcnow()
#     first_of_cur = today.replace(day=1)
#     last_full = first_of_cur - timedelta(days=1)
#     return last_full.year, last_full.month



# # ---- measure keyword map (detect & normalize) ----
# MEASURE_KEYWORDS = {
#     "value": "value_sales",
#     "sales": "value_sales",
#     "value sales": "value_sales",

#     # unit sales (aliases)
#     "unit": "unit_sales",
#     "units": "unit_sales",
#     "unit sales": "unit_sales",

#     "share": "share",
#     "yoy": "value_yoy",
#     "value_yoy": "value_yoy",
#     "share_yoy": "share_yoy",
# }

# # ---- MoM trigger phrases (Month-over-Month) ----
# MOM_KEYWORDS = [
#     "mom",
#     "m/m",
#     "month over month",
#     "monthly change",
#     "mom growth",
# ]

# # ---- helpers ----
# def _last_complete_month_anchor():
#     """Return (year, month) of the last fully complete calendar month (UTC)."""
#     today = datetime.utcnow()
#     first_of_cur = today.replace(day=1)
#     last_full = first_of_cur - timedelta(days=1)
#     return last_full.year, last_full.month


# # -------------------------- INTENT PARSER --------------------------
# def parse_user_text(text: str) -> Intent:
#     """
#     Parse a free-text question into a structured Intent (no SQL!).
#     """
#     t = text.lower()
#     intent = Intent()

#     # --- task ---
#     if any(k in t for k in ["trend", "over time", "timeseries", "time series", "line chart", "chart"]):
#         intent.task = "chart"
#         if "date" not in intent.dims:
#             intent.dims = ["date"]
#     elif any(k in t for k in ["top", "bottom", "table", "rank"]):
#         intent.task = "table"
#     elif any(k in t for k in ["explain", "insight", "summary"]):
#         intent.task = "text"

#     # --- measures ---
#     for k, m in MEASURE_KEYWORDS.items():
#         if re.search(rf"\b{k}\b", t):
#             if m not in intent.measures:
#                 intent.measures.append(m)
#     if re.search(r"(share.*(change|delta|pp))|((change|delta).*\bshare\b)", t):
#         if "share_change" not in intent.measures:
#             intent.measures.append("share_change")
#     if "unit_sales" in intent.measures and "value_sales" in intent.measures:
#         intent.measures = ["unit_sales"]
#     if not intent.measures:
#         intent.measures = ["value_sales"]

#     # --- dims ---
#    # --- dims ---

# # Only add BRAND if the user explicitly asks to group by it
# # e.g. "by brand", "per brand", "brand-wise", or a ranking query (Top/Bottom)
#   # --- NEW: infer "group by brand" from phrasing ---
#     brand_group = False
#     if re.search(r"\bby\s+brand\b", t) or re.search(r"\btop(\s+\d+)?\s+brands?\b", t):
#         brand_group = True
#     # but if user fixed a single brand, don't group
#     if "brand" in intent.filters:
#         brand_group = False

#     # ensure 'brand' in dims when we'll group by brand
#     if brand_group and "brand" not in intent.dims:
#         intent.dims.append("brand")

#     # carry the flag
#     try:
#         intent.brand_group = brand_group
#     except Exception:
#         pass


#     # --- top N ---
#     m = re.search(r"top\s+(\d+)", t)
#     if m:
#         n = int(m.group(1))
#         intent.sort = SortSpec(by="value_sales", order="desc", limit=n)
#     if "yoy" in t:
#         if intent.sort is None:
#             intent.sort = SortSpec()
#         if intent.sort.by is None:
#             intent.sort.by = "value_yoy"
#     if ("yoy" in t or "value_yoy" in t) and any(k in t for k in ["top", "bottom"]):
#         if intent.sort is None:
#             intent.sort = SortSpec()
#         intent.sort.by = "value_yoy"
#         intent.dims = [d for d in intent.dims if d != "date"]
#         if "brand" not in intent.dims:
#             intent.dims.append("brand")

#     # --- MoM ---
#     if any(k in t for k in MOM_KEYWORDS):
#         try:
#             intent.mom = True
#         except Exception:
#             pass
#         if intent.sort is None:
#             intent.sort = SortSpec()
#         if intent.sort.by is None:
#             intent.sort.by = "value_mom"

#     # --- explicit month-year ranges (NEW) ---
#     rng = _parse_month_year_range_freeform(t)
#     if rng:
#         start, end = rng
#         intent.time_range = TimeRange(start=start, end=end)

#     # --- fallback ranges ---
#     if not intent.time_range and ("last 12" in t or "last twelve" in t):
#         y_end, m_end = _last_complete_month_anchor()
#         start_idx = (y_end * 12 + (m_end - 1)) - 11
#         start_y, start_m = divmod(start_idx, 12)
#         start_m += 1
#         intent.time_range = TimeRange(
#             start=f"{start_y:04d}-{start_m:02d}",
#             end=f"{y_end:04d}-{m_end:02d}",
#         )
#     if not intent.time_range and ("ytd" in t or "year to date" in t or "year-to-date" in t):
#         y_end, m_end = _last_complete_month_anchor()
#         intent.time_range = TimeRange(
#             start=f"{y_end:04d}-01",
#             end=f"{y_end:04d}-{m_end:02d}",
#         )

#     # --- filters ---
#     # --- filters: category:"Biscuits", category:'Biscuits', or even category: Biscuits ---
#     for dim in ["category", "market", "channel", "brand"]:
#         # 1) quoted with "..." or '...'
#         m = re.search(rf'{dim}\s*[:=]\s*([\'"])(.+?)\1', t, flags=re.IGNORECASE)
#         if m:
#             intent.filters[dim] = m.group(2).strip()
#             continue
#         # 2) unquoted single token (letters / spaces until next key or end)
#         m = re.search(rf'{dim}\s*[:=]\s*([a-zA-Z][a-zA-Z\s\-&]+)', t, flags=re.IGNORECASE)
#         if m:
#             intent.filters[dim] = m.group(1).strip()

#     return intent


# # -------------------------- DICT CONVERTER (for pandas runner) --------------------------
# import re

# TOPN_RE = re.compile(r"\btop\s+(\d+)", re.IGNORECASE)

# def intent_to_dict(intent: Intent, original_text: str = "") -> dict:
#     t = (original_text or "").lower()

#     # --- task ---
#     task = intent.task or "table"
#     if task == "table" and intent.sort and intent.sort.limit:
#         task = "topn"

#     filters = intent.filters or {}

#     # --- "by brand" grouping intent ---
#     brand_group = bool(BY_BRAND_RE.search(original_text or ""))

#     # --- dims ---
#     dims = intent.dims or []
#     if task == "topn":
#         dims = [d for d in dims if d != "date"]
#     fixed_dims = set(filters.keys()) - ({"brand"} if brand_group else set())
#     dims = [d for d in dims if d not in fixed_dims]
#     if brand_group and "brand" not in dims:
#         dims = ["brand"] + dims  # put brand first for readability

#     # --- time range ---
#     mode = None
#     if any(k in t for k in ["mat", "moving annual total", "last 12", "last twelve"]):
#         mode = "MAT"
#     if any(k in t for k in ["ytd", "year to date", "year-to-date"]):
#         mode = "YTD"
#     if mode:
#         tr = {"mode": mode}
#     elif intent.time_range and intent.time_range.start and intent.time_range.end:
#         tr = {"start": intent.time_range.start, "end": intent.time_range.end}
#     else:
#         tr = None

#     # --- measures + explicit YoY flag ---
#     raw_measures = intent.measures or ["value_sales"]
#     asked_unit   = ("unit_sales" in raw_measures)
#     asked_value  = ("value_sales" in raw_measures)
#     asked_yoy    = ("yoy" in t) or any(m in raw_measures for m in ["value_yoy", "unit_yoy"])

#     # keep sales measure AND (optionally) the matching *_yoy token
#     if asked_unit:
#         measures = ["unit_sales"] + (["unit_yoy"] if asked_yoy else [])
#     elif asked_value:
#         measures = ["value_sales"] + (["value_yoy"] if asked_yoy else [])
#     else:
#         measures = ["value_sales"] + (["value_yoy"] if asked_yoy else [])

#     # --- Top-N detection (parser OR regex fallback) ---
#     top_n = None
#     if intent.sort and intent.sort.limit:
#         top_n = intent.sort.limit
#     else:
#         m = TOPN_RE.search(original_text or "")
#         if m:
#             top_n = int(m.group(1))

#     # --- MoM flag ---
#     is_mom = any(k in t for k in MOM_KEYWORDS)
#     if getattr(intent, "mom", False):
#         is_mom = True

#     # --- sorting defaults ---
#     sort_by    = (intent.sort.by if intent.sort else None)
#     sort_order = (intent.sort.order if intent.sort else "desc")
#     if is_mom and sort_by is None:
#         sort_by = "value_mom"
#     if asked_yoy and sort_by is None:
#         sort_by = "unit_yoy" if "unit_yoy" in measures else "value_yoy"

#     return {
#         "task": task,
#         "dims": dims,
#         "measures": measures,
#         "filters": filters,
#         "time_range": tr,
#         "top_n": top_n,   # ✅ now correctly detects "top 2", "top 3", etc.
#         "sort_by": sort_by,
#         "sort_order": sort_order,
#         "mom": is_mom,
#         "is_yoy": asked_yoy,            # ✅ explicit YoY flag
#         "brand_group": brand_group,
#         "has_brand_filter": ("brand" in filters),
#         "raw_text": original_text or "",
#     }






import re
from datetime import datetime, timedelta
from .intent_schema import Intent, TimeRange, SortSpec


# --- add near the top of parser.py (after imports) ---
import re
from datetime import datetime, timedelta
from .intent_schema import Intent, TimeRange, SortSpec

# map month words to month numbers (short or long)
_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# matches "jan 2024", "january 2024", etc.
# Month name + 4-digit year (e.g., "Jan 2024", "september 2025")
BY_BRAND_RE = re.compile(r"\bby\s+brand(s)?\b", re.IGNORECASE)

_MONTH_YR_RE = re.compile(r"""
    \b
    ( jan(?:uary)? |
      feb(?:ruary)? |
      mar(?:ch)? |
      apr(?:il)? |
      may |
      jun(?:e)? |
      jul(?:y)? |
      aug(?:ust)? |
      sep(?:t(?:ember)?)? |
      oct(?:ober)? |
      nov(?:ember)? |
      dec(?:ember)? )
    \W*           # space or punctuation between month and year
    (\d{4})
    \b
""", re.IGNORECASE | re.VERBOSE)


def _parse_month_year_range_freeform(text: str):
    """
    Find two month-year mentions in order and return ('YYYY-MM', 'YYYY-MM').
    Handles phrases like:
      - 'from Jan 2024 to Mar 2025'
      - 'between January 2024 and March 2025'
      - 'Jan 2024 to March 2025'
    If fewer than two mentions are found, returns None.
    """
    t = text.lower()
    hits = list(_MONTH_YR_RE.finditer(t))
    if len(hits) < 2:
        return None

    # prefer pairs connected by 'to' or 'and' if present; otherwise, first two hits
    # (simple heuristic that works well for natural queries)
    start_m, start_y = hits[0].group(1), hits[0].group(2)
    end_m, end_y     = hits[1].group(1), hits[1].group(2)

    sm = _MONTH_MAP[start_m]   # month number
    em = _MONTH_MAP[end_m]

    start = f"{int(start_y):04d}-{sm:02d}"
    end   = f"{int(end_y):04d}-{em:02d}"
    return start, end


# (existing) helper kept as-is
def _last_complete_month_anchor():
    today = datetime.utcnow()
    first_of_cur = today.replace(day=1)
    last_full = first_of_cur - timedelta(days=1)
    return last_full.year, last_full.month



# ---- measure keyword map (detect & normalize) ----
MEASURE_KEYWORDS = {
    "value": "value_sales",
    "sales": "value_sales",
    "value sales": "value_sales",

    # unit sales (aliases)
    "unit": "unit_sales",
    "units": "unit_sales",
    "unit sales": "unit_sales",

    "share": "share",
    "yoy": "value_yoy",
    "value_yoy": "value_yoy",
    "share_yoy": "share_yoy",
}

# ---- MoM trigger phrases (Month-over-Month) ----
MOM_KEYWORDS = [
    "mom",
    "m/m",
    "month over month",
    "monthly change",
    "mom growth",
]

# ---- helpers ----
def _last_complete_month_anchor():
    """Return (year, month) of the last fully complete calendar month (UTC)."""
    today = datetime.utcnow()
    first_of_cur = today.replace(day=1)
    last_full = first_of_cur - timedelta(days=1)
    return last_full.year, last_full.month


# -------------------------- INTENT PARSER --------------------------
def parse_user_text(text: str) -> Intent:
    """
    Parse a free-text question into a structured Intent (no SQL!).
    """
    t = text.lower()
    intent = Intent()

    # --- task ---
    if any(k in t for k in ["trend", "over time", "timeseries", "time series", "line chart", "chart"]):
        intent.task = "chart"
        if "date" not in intent.dims:
            intent.dims = ["date"]
    elif any(k in t for k in ["top", "bottom", "table", "rank"]):
        intent.task = "table"
    elif any(k in t for k in ["explain", "insight", "summary"]):
        intent.task = "text"

    # --- measures ---
    for k, m in MEASURE_KEYWORDS.items():
        if re.search(rf"\b{k}\b", t):
            if m not in intent.measures:
                intent.measures.append(m)
    if re.search(r"(share.*(change|delta|pp))|((change|delta).*\bshare\b)", t):
        if "share_change" not in intent.measures:
            intent.measures.append("share_change")
    if "unit_sales" in intent.measures and "value_sales" in intent.measures:
        intent.measures = ["unit_sales"]
    if not intent.measures:
        intent.measures = ["value_sales"]

    # --- dims ---
   # --- dims ---

# Only add BRAND if the user explicitly asks to group by it
# e.g. "by brand", "per brand", "brand-wise", or a ranking query (Top/Bottom)
  # --- NEW: infer "group by brand" from phrasing ---
    brand_group = False
    if re.search(r"\bby\s+brand\b", t) or re.search(r"\btop(\s+\d+)?\s+brands?\b", t):
        brand_group = True
    # but if user fixed a single brand, don't group
    if "brand" in intent.filters:
        brand_group = False

    # ensure 'brand' in dims when we'll group by brand
    if brand_group and "brand" not in intent.dims:
        intent.dims.append("brand")

    # carry the flag
    try:
        intent.brand_group = brand_group
    except Exception:
        pass


    # --- top N ---
    m = re.search(r"top\s+(\d+)", t)
    if m:
        n = int(m.group(1))
        intent.sort = SortSpec(by="value_sales", order="desc", limit=n)
    if "yoy" in t:
        if intent.sort is None:
            intent.sort = SortSpec()
        if intent.sort.by is None:
            intent.sort.by = "value_yoy"
    if ("yoy" in t or "value_yoy" in t) and any(k in t for k in ["top", "bottom"]):
        if intent.sort is None:
            intent.sort = SortSpec()
        intent.sort.by = "value_yoy"
        intent.dims = [d for d in intent.dims if d != "date"]
        if "brand" not in intent.dims:
            intent.dims.append("brand")

    # --- MoM ---
    if any(k in t for k in MOM_KEYWORDS):
        try:
            intent.mom = True
        except Exception:
            pass
        if intent.sort is None:
            intent.sort = SortSpec()
        if intent.sort.by is None:
            intent.sort.by = "value_mom"

    # --- explicit month-year ranges (NEW) ---
    rng = _parse_month_year_range_freeform(t)
    if rng:
        start, end = rng
        intent.time_range = TimeRange(start=start, end=end)

    # --- fallback ranges ---
    if not intent.time_range and ("last 12" in t or "last twelve" in t):
        y_end, m_end = _last_complete_month_anchor()
        start_idx = (y_end * 12 + (m_end - 1)) - 11
        start_y, start_m = divmod(start_idx, 12)
        start_m += 1
        intent.time_range = TimeRange(
            start=f"{start_y:04d}-{start_m:02d}",
            end=f"{y_end:04d}-{m_end:02d}",
        )
    if not intent.time_range and ("ytd" in t or "year to date" in t or "year-to-date" in t):
        y_end, m_end = _last_complete_month_anchor()
        intent.time_range = TimeRange(
            start=f"{y_end:04d}-01",
            end=f"{y_end:04d}-{m_end:02d}",
        )

    # --- filters ---
    # --- filters: category:"Biscuits", category:'Biscuits', or even category: Biscuits ---
    for dim in ["category", "market", "channel", "brand"]:
        # 1) quoted with "..." or '...'
        m = re.search(rf'{dim}\s*[:=]\s*([\'"])(.+?)\1', t, flags=re.IGNORECASE)
        if m:
            intent.filters[dim] = m.group(2).strip()
            continue
        # 2) unquoted single token (letters / spaces until next key or end)
        m = re.search(rf'{dim}\s*[:=]\s*([a-zA-Z][a-zA-Z\s\-&]+)', t, flags=re.IGNORECASE)
        if m:
            intent.filters[dim] = m.group(1).strip()

    return intent


# -------------------------- DICT CONVERTER (for pandas runner) --------------------------
import re

TOPN_RE = re.compile(r"\btop\s+(\d+)", re.IGNORECASE)

def intent_to_dict(intent: Intent, original_text: str = "") -> dict:
    t = (original_text or "").lower()

    # --- task ---
    task = intent.task or "table"
    if task == "table" and intent.sort and intent.sort.limit:
        task = "topn"

    filters = intent.filters or {}

    # --- "by brand" grouping intent ---
    brand_group = bool(BY_BRAND_RE.search(original_text or ""))

    # --- dims ---
    dims = intent.dims or []
    if task == "topn":
        dims = [d for d in dims if d != "date"]
    fixed_dims = set(filters.keys()) - ({"brand"} if brand_group else set())
    dims = [d for d in dims if d not in fixed_dims]
    if brand_group and "brand" not in dims:
        dims = ["brand"] + dims  # put brand first for readability

    # --- time range ---
    mode = None
    if any(k in t for k in ["mat", "moving annual total", "last 12", "last twelve"]):
        mode = "MAT"
    if any(k in t for k in ["ytd", "year to date", "year-to-date"]):
        mode = "YTD"
    if mode:
        tr = {"mode": mode}
    elif intent.time_range and intent.time_range.start and intent.time_range.end:
        tr = {"start": intent.time_range.start, "end": intent.time_range.end}
    else:
        tr = None

    # --- measures + explicit YoY flag ---
    raw_measures = intent.measures or ["value_sales"]
    asked_unit   = ("unit_sales" in raw_measures)
    asked_value  = ("value_sales" in raw_measures)
    asked_yoy    = ("yoy" in t) or any(m in raw_measures for m in ["value_yoy", "unit_yoy"])

    # keep sales measure AND (optionally) the matching *_yoy token
    if asked_unit:
        measures = ["unit_sales"] + (["unit_yoy"] if asked_yoy else [])
    elif asked_value:
        measures = ["value_sales"] + (["value_yoy"] if asked_yoy else [])
    else:
        measures = ["value_sales"] + (["value_yoy"] if asked_yoy else [])

    # --- Top-N detection (parser OR regex fallback) ---
    top_n = None
    if intent.sort and intent.sort.limit:
        top_n = intent.sort.limit
    else:
        m = TOPN_RE.search(original_text or "")
        if m:
            top_n = int(m.group(1))

    # --- MoM flag ---
    is_mom = any(k in t for k in MOM_KEYWORDS)
    if getattr(intent, "mom", False):
        is_mom = True

    # --- sorting defaults ---
    sort_by    = (intent.sort.by if intent.sort else None)
    sort_order = (intent.sort.order if intent.sort else "desc")
    if is_mom and sort_by is None:
        sort_by = "value_mom"
    if asked_yoy and sort_by is None:
        sort_by = "unit_yoy" if "unit_yoy" in measures else "value_yoy"

    return {
        "task": task,
        "dims": dims,
        "measures": measures,
        "filters": filters,
        "time_range": tr,
        "top_n": top_n,   # ✅ now correctly detects "top 2", "top 3", etc.
        "sort_by": sort_by,
        "sort_order": sort_order,
        "mom": is_mom,
        "is_yoy": asked_yoy,            # ✅ explicit YoY flag
        "brand_group": brand_group,
        "has_brand_filter": ("brand" in filters),
        "raw_text": original_text or "",
    }

