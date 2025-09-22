#Front end working code without chart only table
# # frontend/app.py  (Version 2 with Debug box)
# import os
# import streamlit as st
# import requests
# import pandas as pd
# import plotly.express as px

# st.set_page_config(page_title="Nielsen Excel Q&A", layout="wide")

# API = os.getenv("API_URL", "http://localhost:8000")

# st.title("📊 Nielsen Excel Q&A — Starter")

# # ---------------- Sidebar: upload ----------------
# with st.sidebar:
#     st.header("1) Upload Nielsen Excel")
#     file = st.file_uploader("Upload .xlsx", type=["xlsx"])
#     if st.button("Upload", type="primary") and file:
#         files = {
#             "file": (
#                 file.name,
#                 file.getvalue(),
#                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             )
#         }
#         resp = requests.post(f"{API}/upload", files=files)
#         if resp.ok:
#             st.success(resp.json())
#         else:
#             st.error(resp.text)

# # ---------------- Ask ----------------
# st.header("2) Ask a question")
# q = st.text_input(
#     'Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart',
#     "",
# )

# if st.button("Ask", type="primary"):
#     resp = requests.post(f"{API}/ask", json={"question": q})
#     if not resp.ok:
#         st.error(resp.text)
#     else:
#         out = resp.json()

#         # ---------- intent + (legacy) sql ----------
#         st.subheader("Parsed intent")
#         st.json(out.get("intent", {}))
#         st.subheader("SQL")
#         st.code(out.get("sql"), language="sql")

#         # ---------- main result ----------
#         df = pd.DataFrame(out.get("data", []))
#         st.subheader("Result")
#         if df.empty:
#             st.warning("No data for this query.")
#         else:
#             st.dataframe(df, use_container_width=True)

#             # quick MoM sanity hint (optional)
#             if "mom" in q.lower() and not any(c.endswith("_mom") for c in df.columns):
#                 st.info("Query mentions MoM, but no `*_mom` column returned. "
#                         "Ensure your question includes a measure (value/unit) and MoM.")

#             # try a line chart if a date column exists
#             if "date" in df.columns and df["date"].notna().any():
#                 try:
#                     ycols = [
#                         c for c in df.columns
#                         if c in ("value_sales", "unit_sales", "share", "value_yoy", "share_yoy")
#                         or c.endswith("_yoy")
#                     ]
#                     if ycols:
#                         fig = px.line(df, x="date", y=ycols, markers=True, title="Trend")
#                         st.plotly_chart(fig, use_container_width=True)
#                 except Exception as e:
#                     st.info(f"Chart note: {e}")

#         # ---------- key insights ----------
#         st.subheader("Key insights")
#         for b in out.get("insights", []):
#             st.write(f"• {b}")

#         # ---------- 🔎 Debug box ----------
#         meta = out.get("meta", {})
#         with st.expander("🔎 Debug (resolved context)"):
#             st.write("**Measure:**", meta.get("measure"))
#             st.write("**Dims:**", meta.get("dims"))
#             st.write("**Filters:**", meta.get("filters"))
#             st.write("**Mode:**", meta.get("mode"))

#             win = meta.get("window") or {}
#             st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")

#             # MoM-specific anchor and months (shown only when present)
#             if "month_current" in meta or "month_previous" in meta:
#                 st.write("**MoM Anchor:**", meta.get("anchor"))
#                 cur = meta.get("month_current", {})
#                 prv = meta.get("month_previous", {})
#                 st.write("• Current month:", f"{cur.get('start')} → {cur.get('end')}")
#                 st.write("• Previous month:", f"{prv.get('start')} → {prv.get('end')}")

#             # YoY previous window (shown only when present)
#             dbg = meta.get("debug") or {}
#             if isinstance(dbg, dict) and "prev_window" in dbg:
#                 pw = dbg["prev_window"]
#                 st.write("**YoY previous window:**", f"{pw.get('start')} → {pw.get('end')}")

#             # raw meta (collapsed)
#             st.json(meta, expanded=False)

#New front end with chart functionality but Yoy not showing sales bar chart, MAT comparisons remaining

# # frontend/app.py
# # frontend/app.py
# import os
# import requests
# import pandas as pd
# import numpy as np
# import streamlit as st
# import plotly.express as px
# import plotly.io as pio

# st.set_page_config(page_title="Nielsen Excel Q&A", layout="wide")
# API = os.getenv("API_URL", "http://localhost:8000")

# st.title("📊 Nielsen Excel Q&A — Starter")

# # ---------------- Sidebar: upload ----------------
# with st.sidebar:
#     st.header("1) Upload Nielsen Excel")
#     file = st.file_uploader("Upload .xlsx", type=["xlsx"])
#     if st.button("Upload", type="primary") and file:
#         files = {
#             "file": (
#                 file.name,
#                 file.getvalue(),
#                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             )
#         }
#         resp = requests.post(f"{API}/upload", files=files)
#         if resp.ok:
#             st.success(resp.json())
#         else:
#             st.error(resp.text)

# # ---------------- Helpers ----------------
# CAT_CANDIDATES = ["brand", "category", "market", "channel", "manufacturer", "segment"]

# # --- helpers (put near your other helpers) ---
# def _preferred_measure_for_line(df: pd.DataFrame) -> str | None:
#     # prefer a single clean series to keep the trend readable
#     for c in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     # fallback: first numeric column that isn't an intermediate
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr")):
#             return c
#     return None

# def _month_category_order(df: pd.DataFrame) -> list[str]:
#     # Create a chronological order for the categorical month labels
#     # Works whether you have "month" (e.g. "Jan 2023") or a real datetime "date"
#     if "month" in df.columns:
#         tmp = (
#             df[["month"]]
#             .drop_duplicates()
#             .assign(_d=pd.to_datetime(df["month"], format="%b %Y", errors="coerce"))
#             .sort_values("_d")
#         )
#         return tmp["month"].tolist()
#     if "date" in df.columns:
#         tmp = (
#             df[["date"]]
#             .drop_duplicates()
#             .assign(_d=pd.to_datetime(df["date"]))
#             .sort_values("_d")
#             .assign(month=lambda x: x["_d"].dt.strftime("%b %Y"))
#         )
#         return tmp["month"].tolist()
#     return []


# def _numeric_cols(df: pd.DataFrame):
#     return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

# def _find_y_cols(df: pd.DataFrame):
#     # Prioritize meaningful measures
#     priority = [
#         "value_sales", "unit_sales", "share",
#         "value_yoy", "unit_yoy", "share_yoy",
#     ]
#     y = [c for c in priority if c in df.columns]
#     if not y:
#         y = [c for c in _numeric_cols(df) if not c.endswith("_prev") and not c.endswith("_curr")]
#     return y[:6]  # keep it readable

# def _find_x_cat(df: pd.DataFrame):
#     for c in CAT_CANDIDATES:
#         if c in df.columns:
#             return c
#     # fallback: first non-numeric column that isn't date
#     for c in df.columns:
#         if c != "date" and not pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     return None

# def _format_percent_axes(fig, y_cols):
#     if any(("yoy" in c) or ("share" in c) for c in y_cols):
#         fig.update_layout(yaxis_tickformat=".0%")

# def _parse_date_month(df: pd.DataFrame):
#     if "date" in df.columns:
#         try:
#             df = df.copy()
#             df["date"] = pd.to_datetime(df["date"])
#             # month labels like "Jan 2023"
#             df["date_label"] = df["date"].dt.strftime("%b %Y")
#             return df
#         except Exception:
#             return df
#     return df
# def render_chart(df: pd.DataFrame, meta: dict):
#     chart_type = (meta or {}).get("chart_type")
#     df = df.copy()

#     # If backend sent a real datetime "date", also add a month label for plotting
#     if "date" in df.columns:
#         try:
#             df["date"] = pd.to_datetime(df["date"])
#             df["month"] = df["date"].dt.strftime("%b %Y")
#         except Exception:
#             pass

#     # ---- LINE (trend) ----
#     if chart_type == "line" or ("date" in df.columns) or ("month" in df.columns):
#         y = _preferred_measure_for_line(df)
#         if not y:
#             st.info("No numeric series found to draw a trend.")
#             return

#         # x-axis: prefer "month" so each month label appears ONCE
#         x = "month" if "month" in df.columns else "date"

#         # multiple series? color by brand/category if present
#         color_col = None
#         for c in ["brand", "category", "market", "channel", "manufacturer", "segment"]:
#             if c in df.columns:
#                 color_col = c
#                 break

#         # sort chronologically without altering the displayed table
#         if x == "date":
#             plot_df = df.sort_values("date")
#         else:
#             # keep month as categorical, ordered by actual time
#             order = _month_category_order(df)
#             plot_df = df.copy()
#             plot_df["month"] = pd.Categorical(plot_df["month"], categories=order, ordered=True)
#             plot_df = plot_df.sort_values("month")

#         fig = px.line(
#             plot_df,
#             x=x,
#             y=y,
#             color=color_col,
#             markers=True,
#             title="Trend",
#         )

#         # nice month ticks
#         if x == "date":
#             fig.update_xaxes(tickformat="%b %Y")
#         else:
#             fig.update_xaxes(type="category", categoryorder="array", categoryarray=_month_category_order(df))

#         # percentage axis when yoy/share
#         if any(k in y for k in ["yoy", "share"]):
#             fig.update_layout(yaxis_tickformat=".0%")

#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- BAR (top-N / categorical comparisons) ----
#     # If no explicit chart_type, we'll try to infer a reasonable bar
#     xcat = next((c for c in ["brand", "category", "market", "channel", "manufacturer", "segment"] if c in df.columns), None)
#     ycols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr"))]

#     if xcat and ycols:
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols, var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value", color="metric", barmode="group", title="Bar chart")
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         if any(("yoy" in c) or ("share" in c) for c in ycols):
#             fig.update_layout(yaxis_tickformat=".0%")
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # If we reach here, we couldn't infer a chart
#     st.info("No chart rendered (not enough columns to infer a chart).")


# # ---------------- Ask ----------------
# st.header("2) Ask a question")
# q = st.text_input(
#     'Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart',
#     "",
# )

# if st.button("Ask", type="primary"):
#     resp = requests.post(f"{API}/ask", json={"question": q})
#     if not resp.ok:
#         st.error(resp.text)
#     else:
#         out = resp.json()

#         # ---------- intent + (legacy) sql ----------
#         st.subheader("Parsed intent")
#         st.json(out.get("intent", {}))
#         st.subheader("SQL")
#         st.code(out.get("sql"), language="sql")

#         # ---------- main result ----------
#         df = pd.DataFrame(out.get("data", []))
#         meta = out.get("meta", {}) or {}

#         st.subheader("Result")
#         if df.empty:
#             st.warning("No data for this query.")
#         else:
#             # show table exactly as returned
#             st.dataframe(df, use_container_width=True)

#             # quick MoM sanity hint (optional)
#             if "mom" in q.lower() and not any(c.endswith("_mom") for c in df.columns):
#                 st.info(
#                     "Query mentions MoM, but no `*_mom` column returned.\n"
#                     "Make sure your question includes a measure (value/unit) + MoM."
#                 )

#             # render chart from the result + meta.chart_type
#             render_chart(df, meta)

#         # ---------- key insights ----------
#         if out.get("insights"):
#             st.subheader("Key insights")
#             for b in out.get("insights", []):
#                 st.write(f"• {b}")

#         # ---------- 🔎 Debug box ----------
#         with st.expander("🔎 Debug (resolved context)"):
#             st.write("**Measure:**", meta.get("measure"))
#             st.write("**Dims:**", meta.get("dims"))
#             st.write("**Filters:**", meta.get("filters"))
#             st.write("**Mode:**", meta.get("mode"))
#             st.write("**Chart hint:**", meta.get("chart_type"))
#             win = meta.get("window") or {}
#             st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")
#             # MoM-specific fields (shown only when present)
#             if "month_current" in meta or "month_previous" in meta:
#                 st.write("**MoM Anchor:**", meta.get("anchor"))
#                 cur = meta.get("month_current", {})
#                 prv = meta.get("month_previous", {})
#                 st.write("• Current month:", f"{cur.get('start')} → {cur.get('end')}")
#                 st.write("• Previous month:", f"{prv.get('start')} → {prv.get('end')}")
#             # YoY previous window (shown only when present)
#             dbg = meta.get("debug") or {}
#             if isinstance(dbg, dict) and "prev_window" in dbg:
#                 pw = dbg["prev_window"]
#                 st.write("**YoY previous window:**", f"{pw.get('start')} → {pw.get('end')}")
#             st.json(meta, expanded=False)







#When querying about YoY then showing sales in bar chart, Line chart not working






# # frontend/app.py
# # frontend/app.py
# import os
# import requests
# import pandas as pd
# import numpy as np
# import streamlit as st
# import plotly.express as px
# import plotly.io as pio

# st.set_page_config(page_title="Nielsen Excel Q&A", layout="wide")
# API = os.getenv("API_URL", "http://localhost:8000")

# st.title("📊 Nielsen Excel Q&A — Starter")

# # ---------------- Sidebar: upload ----------------
# with st.sidebar:
#     st.header("1) Upload Nielsen Excel")
#     file = st.file_uploader("Upload .xlsx", type=["xlsx"])
#     if st.button("Upload", type="primary") and file:
#         files = {
#             "file": (
#                 file.name,
#                 file.getvalue(),
#                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             )
#         }
#         resp = requests.post(f"{API}/upload", files=files)
#         if resp.ok:
#             st.success(resp.json())
#         else:
#             st.error(resp.text)

# # ---------------- Helpers ----------------
# CAT_CANDIDATES = ["brand", "category", "market", "channel", "manufacturer", "segment"]

# # --- helpers (put near your other helpers) ---
# def _preferred_measure_for_line(df: pd.DataFrame) -> str | None:
#     # prefer a single clean series to keep the trend readable
#     for c in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     # fallback: first numeric column that isn't an intermediate
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr")):
#             return c
#     return None

# def _month_category_order(df: pd.DataFrame) -> list[str]:
#     # Create a chronological order for the categorical month labels
#     # Works whether you have "month" (e.g. "Jan 2023") or a real datetime "date"
#     if "month" in df.columns:
#         tmp = (
#             df[["month"]]
#             .drop_duplicates()
#             .assign(_d=pd.to_datetime(df["month"], format="%b %Y", errors="coerce"))
#             .sort_values("_d")
#         )
#         return tmp["month"].tolist()
#     if "date" in df.columns:
#         tmp = (
#             df[["date"]]
#             .drop_duplicates()
#             .assign(_d=pd.to_datetime(df["date"]))
#             .sort_values("_d")
#             .assign(month=lambda x: x["_d"].dt.strftime("%b %Y"))
#         )
#         return tmp["month"].tolist()
#     return []


# def _numeric_cols(df: pd.DataFrame):
#     return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

# def _find_y_cols(df: pd.DataFrame):
#     # Prioritize meaningful measures
#     priority = [
#         "value_sales", "unit_sales", "share",
#         "value_yoy", "unit_yoy", "share_yoy",
#     ]
#     y = [c for c in priority if c in df.columns]
#     if not y:
#         y = [c for c in _numeric_cols(df) if not c.endswith("_prev") and not c.endswith("_curr")]
#     return y[:6]  # keep it readable

# def _find_x_cat(df: pd.DataFrame):
#     for c in CAT_CANDIDATES:
#         if c in df.columns:
#             return c
#     # fallback: first non-numeric column that isn't date
#     for c in df.columns:
#         if c != "date" and not pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     return None

# def _format_percent_axes(fig, y_cols):
#     if any(("yoy" in c) or ("share" in c) for c in y_cols):
#         fig.update_layout(yaxis_tickformat=".0%")

# def _parse_date_month(df: pd.DataFrame):
#     if "date" in df.columns:
#         try:
#             df = df.copy()
#             df["date"] = pd.to_datetime(df["date"])
#             # month labels like "Jan 2023"
#             df["date_label"] = df["date"].dt.strftime("%b %Y")
#             return df
#         except Exception:
#             return df
#     return df
# def render_chart(df: pd.DataFrame, meta: dict):
#     chart_type = (meta or {}).get("chart_type")
#     measure_hint = (meta or {}).get("measure")  # e.g. "value_yoy", "unit_yoy", "value_sales", etc.

#     # Always try to coerce 'date' and create a monthly label (safe no-op if not present)
#     df = _parse_date_month(df)

#     # ---- Helper: pick y for YoY → use current-period sales, not the yoy % ----
#     def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
#         # Prefer explicit match first
#         if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
#             return ["value_sales_curr"]
#         if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
#             return ["unit_sales_curr"]
#         # Fallback: any "*_curr" numeric columns (e.g., when schema differs)
#         fallback = [c for c in _df.columns if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
#         return fallback[:1] if fallback else []

#     # ---- LINE CHART (trend) ----
#     if chart_type == "line":
#         if "date" not in df.columns:
#             st.info("No date column in result to draw a trend.")
#             return
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to plot as a trend.")
#             return
#         fig = px.line(
#             df.sort_values("date"),
#             x="date",
#             y=ycols,
#             markers=True,
#             labels={"date": "Month", "value": ", ".join(ycols)},
#             title="Trend",
#         )
#         fig.update_xaxes(tickformat="%b %Y")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- BAR CHART (categories / YoY tables) ----
#     if chart_type == "bar":
#         xcat = _find_x_cat(df)
#         if xcat is None:
#             st.info("Not enough columns to draw a bar chart.")
#             return

#         # If this is a YoY response, plot SALES (current period), not the YoY %
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ycols = _pick_y_for_yoy(df, measure_hint)
#             if not ycols:
#                 st.info("Could not find current-period sales column for YoY chart.")
#                 return
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
#             # (sales are absolute; no percent axis here)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#         # Non-YoY bar: pick standard y columns
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to draw a bar chart.")
#             return

#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols, var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value", color="metric", barmode="group", title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- No chart hint → try something sensible ----
#     if "date" in df.columns:
#         ycols = _find_y_cols(df)
#         if ycols:
#             fig = px.line(df.sort_values("date"), x="date", y=ycols, markers=True, title="Trend")
#             fig.update_xaxes(tickformat="%b %Y")
#             _format_percent_axes(fig, ycols)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#     xcat = _find_x_cat(df)
#     ycols = _find_y_cols(df)
#     if xcat and ycols:
#         # If this is a YoY response but no explicit bar hint was sent, still use sales
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ypick = _pick_y_for_yoy(df, measure_hint)
#             if ypick:
#                 fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
#                 st.plotly_chart(fig, use_container_width=True)
#                 return
#         fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)


#     # ---- BAR (top-N / categorical comparisons) ----
#     # If no explicit chart_type, we'll try to infer a reasonable bar
#     xcat = next((c for c in ["brand", "category", "market", "channel", "manufacturer", "segment"] if c in df.columns), None)
#     ycols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr"))]

#     if xcat and ycols:
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols, var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value", color="metric", barmode="group", title="Bar chart")
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         if any(("yoy" in c) or ("share" in c) for c in ycols):
#             fig.update_layout(yaxis_tickformat=".0%")
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # If we reach here, we couldn't infer a chart
#     st.info("No chart rendered (not enough columns to infer a chart).")


# # ---------------- Ask ----------------
# st.header("2) Ask a question")
# q = st.text_input(
#     'Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart',
#     "",
# )

# if st.button("Ask", type="primary"):
#     resp = requests.post(f"{API}/ask", json={"question": q})
#     if not resp.ok:
#         st.error(resp.text)
#     else:
#         out = resp.json()

#         # ---------- intent + (legacy) sql ----------
#         st.subheader("Parsed intent")
#         st.json(out.get("intent", {}))
#         st.subheader("SQL")
#         st.code(out.get("sql"), language="sql")

#         # ---------- main result ----------
#         df = pd.DataFrame(out.get("data", []))
#         meta = out.get("meta", {}) or {}

#         st.subheader("Result")
#         if df.empty:
#             st.warning("No data for this query.")
#         else:
#             # show table exactly as returned
#             st.dataframe(df, use_container_width=True)

#             # quick MoM sanity hint (optional)
#             if "mom" in q.lower() and not any(c.endswith("_mom") for c in df.columns):
#                 st.info(
#                     "Query mentions MoM, but no `*_mom` column returned.\n"
#                     "Make sure your question includes a measure (value/unit) + MoM."
#                 )

#             # render chart from the result + meta.chart_type
#             render_chart(df, meta)

#         # ---------- key insights ----------
#         if out.get("insights"):
#             st.subheader("Key insights")
#             for b in out.get("insights", []):
#                 st.write(f"• {b}")

#         # ---------- 🔎 Debug box ----------
#         with st.expander("🔎 Debug (resolved context)"):
#             st.write("**Measure:**", meta.get("measure"))
#             st.write("**Dims:**", meta.get("dims"))
#             st.write("**Filters:**", meta.get("filters"))
#             st.write("**Mode:**", meta.get("mode"))
#             st.write("**Chart hint:**", meta.get("chart_type"))
#             win = meta.get("window") or {}
#             st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")
#             # MoM-specific fields (shown only when present)
#             if "month_current" in meta or "month_previous" in meta:
#                 st.write("**MoM Anchor:**", meta.get("anchor"))
#                 cur = meta.get("month_current", {})
#                 prv = meta.get("month_previous", {})
#                 st.write("• Current month:", f"{cur.get('start')} → {cur.get('end')}")
#                 st.write("• Previous month:", f"{prv.get('start')} → {prv.get('end')}")
#             # YoY previous window (shown only when present)
#             dbg = meta.get("debug") or {}
#             if isinstance(dbg, dict) and "prev_window" in dbg:
#                 pw = dbg["prev_window"]
#                 st.write("**YoY previous window:**", f"{pw.get('start')} → {pw.get('end')}")
#             st.json(meta, expanded=False)



#Working code for YoY, Line chart is coming properly, chart for brand YoY not created, MAT comparisons pending

# frontend/app.py
# frontend/app.py
import os
import requests
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.io as pio

st.set_page_config(page_title="Nielsen Excel Q&A", layout="wide")
API = os.getenv("API_URL", "http://localhost:8000")

st.title("📊 Nielsen Excel Q&A — Starter")

# ---------------- Sidebar: upload ----------------
with st.sidebar:
    st.header("1) Upload Nielsen Excel")
    file = st.file_uploader("Upload .xlsx", type=["xlsx"])
    if st.button("Upload", type="primary") and file:
        files = {
            "file": (
                file.name,
                file.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        resp = requests.post(f"{API}/upload", files=files)
        if resp.ok:
            st.success(resp.json())
        else:
            st.error(resp.text)

# ---------------- Helpers ----------------
CAT_CANDIDATES = ["brand", "category", "market", "channel", "manufacturer", "segment"]

# --- helpers (put near your other helpers) ---
def _preferred_measure_for_line(df: pd.DataFrame) -> str | None:
    # prefer a single clean series to keep the trend readable
    for c in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            return c
    # fallback: first numeric column that isn't an intermediate
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr")):
            return c
    return None

def _month_category_order(df: pd.DataFrame) -> list[str]:
    # Create a chronological order for the categorical month labels
    # Works whether you have "month" (e.g. "Jan 2023") or a real datetime "date"
    if "month" in df.columns:
        tmp = (
            df[["month"]]
            .drop_duplicates()
            .assign(_d=pd.to_datetime(df["month"], format="%b %Y", errors="coerce"))
            .sort_values("_d")
        )
        return tmp["month"].tolist()
    if "date" in df.columns:
        tmp = (
            df[["date"]]
            .drop_duplicates()
            .assign(_d=pd.to_datetime(df["date"]))
            .sort_values("_d")
            .assign(month=lambda x: x["_d"].dt.strftime("%b %Y"))
        )
        return tmp["month"].tolist()
    return []


def _numeric_cols(df: pd.DataFrame):
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

def _find_y_cols(df: pd.DataFrame):
    # Prioritize meaningful measures
    priority = [
        "value_sales", "unit_sales", "share",
        "value_yoy", "unit_yoy", "share_yoy",
    ]
    y = [c for c in priority if c in df.columns]
    if not y:
        y = [c for c in _numeric_cols(df) if not c.endswith("_prev") and not c.endswith("_curr")]
    return y[:6]  # keep it readable

def _find_x_cat(df: pd.DataFrame):
    for c in CAT_CANDIDATES:
        if c in df.columns:
            return c
    # fallback: first non-numeric column that isn't date
    for c in df.columns:
        if c != "date" and not pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None

def _format_percent_axes(fig, y_cols):
    if any(("yoy" in c) or ("share" in c) for c in y_cols):
        fig.update_layout(yaxis_tickformat=".0%")

def _parse_date_month(df: pd.DataFrame):
    if "date" in df.columns:
        try:
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"])
            # month labels like "Jan 2023"
            df["date_label"] = df["date"].dt.strftime("%b %Y")
            return df
        except Exception:
            return df
    return df

def render_chart(df: pd.DataFrame, meta: dict):
    chart_type = (meta or {}).get("chart_type")
    measure_hint = (meta or {}).get("measure")  # e.g. "value_yoy", "unit_yoy", "value_sales"

    # --- ensure month label exists (without touching server logic) ---
    if "date" in df.columns and "month" not in df.columns:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.strftime("%b %Y")

    # Build a chronological key for month labels so Plotly doesn't sort alphabetically
    if "month" in df.columns and "_month_key" not in df.columns:
        df = df.copy()
        # Try the expected "%b %Y" first; fallback by prefixing a day
        try:
            df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
        except Exception:
            df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

    # ---- Helper: keep sales for YoY bars ----
    def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
        if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
            return ["value_sales_curr"]
        if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
            return ["unit_sales_curr"]
        fallback = [c for c in _df.columns
                    if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
        return fallback[:1] if fallback else []

    # ---- LINE CHART (trend) ----
    if chart_type == "line":
        xcol = "month" if "month" in df.columns else "date"
        if xcol not in df.columns:
            st.info("No date/month column in result to draw a trend.")
            return
        ycols = _find_y_cols(df)
        if not ycols:
            st.info("No numeric columns to plot as a trend.")
            return

        sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
        sdf = df.sort_values(sort_col)

        fig = px.line(
            sdf,
            x=xcol,
            y=ycols,
            markers=True,
            labels={xcol: "Month", "value": ", ".join(ycols)},
            title="Trend over time",
        )

        if xcol == "month":
            ordered = (
                sdf.dropna(subset=[sort_col])
                   .drop_duplicates(subset=["month"])
                   .sort_values(sort_col)["month"]
                   .tolist()
            )
            fig.update_xaxes(
                type="category",
                categoryorder="array",
                categoryarray=ordered
            )
        else:
            fig.update_xaxes(tickformat="%b %Y")

        _format_percent_axes(fig, ycols)
        st.plotly_chart(fig, use_container_width=True)
        return

    # ---- BAR CHART (Top-N / categories / YoY) ----
    if chart_type == "bar":
        xcat = _find_x_cat(df)
        if not xcat:
            st.info("Not enough columns to draw a bar chart.")
            return

        if measure_hint in ("value_yoy", "unit_yoy"):
            ycols = _pick_y_for_yoy(df, measure_hint)
            if not ycols:
                st.info("No current-period sales column for YoY chart.")
                return
            fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
            st.plotly_chart(fig, use_container_width=True)
            return

        ycols = _find_y_cols(df)
        if not ycols:
            st.info("No numeric columns to draw a bar chart.")
            return
        if len(ycols) > 1:
            long = df.melt(id_vars=[xcat], value_vars=ycols,
                           var_name="metric", value_name="value")
            fig = px.bar(long, x=xcat, y="value",
                         color="metric", barmode="group", title="Bar chart")
            _format_percent_axes(fig, ycols)
        else:
            fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
            _format_percent_axes(fig, ycols)
        st.plotly_chart(fig, use_container_width=True)
        return

    # ---- No chart hint: fallback to time trend if possible ----
    if ("month" in df.columns) or ("date" in df.columns):
        xcol = "month" if "month" in df.columns else "date"
        ycols = _find_y_cols(df)
        if ycols:
            sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
            sdf = df.sort_values(sort_col)
            fig = px.line(sdf, x=xcol, y=ycols, markers=True, title="Trend over time")
            if xcol == "month":
                ordered = (
                    sdf.dropna(subset=[sort_col])
                       .drop_duplicates(subset=["month"])
                       .sort_values(sort_col)["month"]
                       .tolist()
                )
                fig.update_xaxes(type="category",
                                 categoryorder="array",
                                 categoryarray=ordered)
            else:
                fig.update_xaxes(tickformat="%b %Y")
            _format_percent_axes(fig, ycols)
            st.plotly_chart(fig, use_container_width=True)
            return

    # ---- otherwise fallback bar ----
    xcat = _find_x_cat(df)
    ycols = _find_y_cols(df)
    if xcat and ycols:
        if measure_hint in ("value_yoy", "unit_yoy"):
            ypick = _pick_y_for_yoy(df, measure_hint)
            if ypick:
                fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
                st.plotly_chart(fig, use_container_width=True)
                return
        fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
        _format_percent_axes(fig, ycols)
        st.plotly_chart(fig, use_container_width=True)



    # If we reach here, we couldn't infer a chart
    st.info("No chart rendered (not enough columns to infer a chart).")


# ---------------- Ask ----------------
st.header("2) Ask a question")
q = st.text_input(
    'Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart',
    "",
)

if st.button("Ask", type="primary"):
    resp = requests.post(f"{API}/ask", json={"question": q})
    if not resp.ok:
        st.error(resp.text)
    else:
        out = resp.json()

        # ---------- intent + (legacy) sql ----------
        st.subheader("Parsed intent")
        st.json(out.get("intent", {}))
        st.subheader("SQL")
        st.code(out.get("sql"), language="sql")

        # ---------- main result ----------
        df = pd.DataFrame(out.get("data", []))
        meta = out.get("meta", {}) or {}

        st.subheader("Result")
        if df.empty:
            st.warning("No data for this query.")
        else:
            # show table exactly as returned
            st.dataframe(df, use_container_width=True)

            # quick MoM sanity hint (optional)
            if "mom" in q.lower() and not any(c.endswith("_mom") for c in df.columns):
                st.info(
                    "Query mentions MoM, but no `*_mom` column returned.\n"
                    "Make sure your question includes a measure (value/unit) + MoM."
                )

            # render chart from the result + meta.chart_type
            render_chart(df, meta)

        # ---------- key insights ----------
        if out.get("insights"):
            st.subheader("Key insights")
            for b in out.get("insights", []):
                st.write(f"• {b}")

        # ---------- 🔎 Debug box ----------
        with st.expander("🔎 Debug (resolved context)"):
            st.write("**Measure:**", meta.get("measure"))
            st.write("**Dims:**", meta.get("dims"))
            st.write("**Filters:**", meta.get("filters"))
            st.write("**Mode:**", meta.get("mode"))
            st.write("**Chart hint:**", meta.get("chart_type"))
            win = meta.get("window") or {}
            st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")
            # MoM-specific fields (shown only when present)
            if "month_current" in meta or "month_previous" in meta:
                st.write("**MoM Anchor:**", meta.get("anchor"))
                cur = meta.get("month_current", {})
                prv = meta.get("month_previous", {})
                st.write("• Current month:", f"{cur.get('start')} → {cur.get('end')}")
                st.write("• Previous month:", f"{prv.get('start')} → {prv.get('end')}")
            # YoY previous window (shown only when present)
            dbg = meta.get("debug") or {}
            if isinstance(dbg, dict) and "prev_window" in dbg:
                pw = dbg["prev_window"]
                st.write("**YoY previous window:**", f"{pw.get('start')} → {pw.get('end')}")
            st.json(meta, expanded=False)




