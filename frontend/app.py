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



#Working code for YoY, Line chart is coming properly, chart for brand YoY not created, MAT comparisons working

# frontend/app.py
# frontend/app.py
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
#     measure_hint = (meta or {}).get("measure")  # e.g. "value_yoy", "unit_yoy", "value_sales"

#     # --- ensure month label exists (without touching server logic) ---
#     if "date" in df.columns and "month" not in df.columns:
#         df = df.copy()
#         df["date"] = pd.to_datetime(df["date"])
#         df["month"] = df["date"].dt.strftime("%b %Y")

#     # Build a chronological key for month labels so Plotly doesn't sort alphabetically
#     if "month" in df.columns and "_month_key" not in df.columns:
#         df = df.copy()
#         # Try the expected "%b %Y" first; fallback by prefixing a day
#         try:
#             df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
#         except Exception:
#             df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

#     # ---- Helper: keep sales for YoY bars ----
#     def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
#         if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
#             return ["value_sales_curr"]
#         if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
#             return ["unit_sales_curr"]
#         fallback = [c for c in _df.columns
#                     if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
#         return fallback[:1] if fallback else []

#     # ---- LINE CHART (trend) ----
#     if chart_type == "line":
#         xcol = "month" if "month" in df.columns else "date"
#         if xcol not in df.columns:
#             st.info("No date/month column in result to draw a trend.")
#             return
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to plot as a trend.")
#             return

#         sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
#         sdf = df.sort_values(sort_col)

#         fig = px.line(
#             sdf,
#             x=xcol,
#             y=ycols,
#             markers=True,
#             labels={xcol: "Month", "value": ", ".join(ycols)},
#             title="Trend over time",
#         )

#         if xcol == "month":
#             ordered = (
#                 sdf.dropna(subset=[sort_col])
#                    .drop_duplicates(subset=["month"])
#                    .sort_values(sort_col)["month"]
#                    .tolist()
#             )
#             fig.update_xaxes(
#                 type="category",
#                 categoryorder="array",
#                 categoryarray=ordered
#             )
#         else:
#             fig.update_xaxes(tickformat="%b %Y")

#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- BAR CHART (Top-N / categories / YoY) ----
#     if chart_type == "bar":
#         xcat = _find_x_cat(df)
#         if not xcat:
#             st.info("Not enough columns to draw a bar chart.")
#             return

#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ycols = _pick_y_for_yoy(df, measure_hint)
#             if not ycols:
#                 st.info("No current-period sales column for YoY chart.")
#                 return
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
#             st.plotly_chart(fig, use_container_width=True)
#             return

#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to draw a bar chart.")
#             return
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols,
#                            var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value",
#                          color="metric", barmode="group", title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- No chart hint: fallback to time trend if possible ----
#     if ("month" in df.columns) or ("date" in df.columns):
#         xcol = "month" if "month" in df.columns else "date"
#         ycols = _find_y_cols(df)
#         if ycols:
#             sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
#             sdf = df.sort_values(sort_col)
#             fig = px.line(sdf, x=xcol, y=ycols, markers=True, title="Trend over time")
#             if xcol == "month":
#                 ordered = (
#                     sdf.dropna(subset=[sort_col])
#                        .drop_duplicates(subset=["month"])
#                        .sort_values(sort_col)["month"]
#                        .tolist()
#                 )
#                 fig.update_xaxes(type="category",
#                                  categoryorder="array",
#                                  categoryarray=ordered)
#             else:
#                 fig.update_xaxes(tickformat="%b %Y")
#             _format_percent_axes(fig, ycols)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#     # ---- otherwise fallback bar ----
#     xcat = _find_x_cat(df)
#     ycols = _find_y_cols(df)
#     if xcat and ycols:
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ypick = _pick_y_for_yoy(df, measure_hint)
#             if ypick:
#                 fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
#                 st.plotly_chart(fig, use_container_width=True)
#                 return
#         fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)



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








#Working code bad insights



#FInal working code frontend rule based Intent parser

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
# import random

# def derive_insights_from_table(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Works for:
#       • Top-N (bar) tables like: [brand, value_sales] or [brand, unit_sales]
#       • YoY bar tables like: [brand, value_sales_curr, value_sales_prev, value_yoy]
#       • Simple totals (no dims)
#       • Trend tables with date/month (falls back to simple delta)
#     Returns a short list of natural-language bullets.
#     """
#     if df is None or df.empty:
#         return []

#     tips: list[str] = []
#     m = (meta or {}).get("measure") or ""
#     dims = (meta or {}).get("dims") or []
#     cols = list(df.columns)
#     colset = set(cols)

#     # ---------- pick a primary numeric column ----------
#     # Prefer ..._curr for YoY responses → then value_sales / unit_sales → else first numeric
#     numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
#     prefer_order = []
#     prefer_order += [c for c in ["value_sales_curr", "unit_sales_curr"] if c in colset]
#     prefer_order += [c for c in ["value_sales", "unit_sales"] if c in colset]
#     if m and m in colset and m not in prefer_order:
#         prefer_order.insert(0, m)
#     primary = next((c for c in prefer_order if c in colset), None) or (numeric_cols[0] if numeric_cols else None)
#     if primary is None:
#         return tips

#     # ---------- detect the single category (x) column for bar charts ----------
#     cat_candidates = [c for c in ["brand","category","market","channel","segment","manufacturer"] if c in colset]
#     # If API already told us a dim, keep it; otherwise guess a single non-numeric column (not date/month)
#     if not cat_candidates:
#         cat_candidates = [c for c in cols if (c not in ("date","month","month_year")) and not pd.api.types.is_numeric_dtype(df[c])]
#     xcat = cat_candidates[0] if cat_candidates else None

#     # ---------- BAR / TOP-N INSIGHTS ----------
#     if xcat:
#         sub = df[[xcat, primary]].dropna()
#         # protect against duplicated keys (group if needed)
#         if sub[xcat].duplicated().any():
#             sub = sub.groupby(xcat, dropna=False)[primary].sum().reset_index()

#         if not sub.empty:
#             sub = sub.sort_values(primary, ascending=False)
#             leader_row = sub.iloc[0]
#             leader, lead_val = leader_row[xcat], float(leader_row[primary])

#             # 1) Leader
#             tips.append(f"{xcat.title()} “{leader}” leads on {primary.replace('_',' ')} ({lead_val:,.0f}).")

#             # 2) Gap vs #2 (if exists)
#             if len(sub) >= 2:
#                 runner_row = sub.iloc[1]
#                 runner, run_val = runner_row[xcat], float(runner_row[primary])
#                 gap = lead_val - run_val
#                 gap_pc = gap / (run_val + 1e-9)
#                 tips.append(f"Lead over #{2} “{runner}” is {gap:,.0f} ({gap_pc:+.0%}).")

#             # 3) Share of top brand (within the shown list)
#             total = float(sub[primary].sum())
#             if total > 0:
#                 top_share = lead_val / total
#                 tips.append(f"Top item holds {top_share:.0%} of the shown total.")

#             # 4) Concentration hint (HHI-ish)
#             share = sub[primary] / max(total, 1e-9)
#             hhi = float((share ** 2).sum())
#             if hhi >= 0.20:
#                 tips.append("Market looks concentrated among a few items.")
#             elif hhi <= 0.10:
#                 tips.append("Market looks fairly fragmented.")
#         # YoY extras
#         yoy_col = next((c for c in cols if c.endswith("_yoy")), None)
#         if yoy_col:
#             # Best YoY mover
#             yy = df[[xcat, yoy_col]].dropna()
#             if not yy.empty and pd.api.types.is_numeric_dtype(yy[yoy_col]):
#                 yy = yy.sort_values(yoy_col, ascending=False)
#                 best = yy.iloc[0]
#                 tips.append(f"Best {yoy_col.replace('_',' ')}: “{best[xcat]}” at {float(best[yoy_col]):+.1%}.")

#         return tips

#     # ---------- NO CATEGORY: totals or trend fallback ----------
#     # Trend: if there is a date/month column, comment on change over time
#     time_col = "month" if "month" in colset else ("date" if "date" in colset else None)
#     if time_col and pd.api.types.is_numeric_dtype(df[primary]):
#         try:
#             t = pd.to_datetime(df[time_col], errors="coerce")
#             s = df.loc[t.notna()].sort_values(t.name)[primary]
#             if len(s) >= 2:
#                 first, last = float(s.iloc[0]), float(s.iloc[-1])
#                 delta = (last - first) / (abs(first) + 1e-9)
#                 tips.append(f"{primary.replace('_',' ')} changed {delta:+.1%} across the period.")
#         except Exception:
#             pass

#     # If still nothing, provide a safe message
#     if not tips:
#         tips.append("No obvious spikes or gaps; values look stable.")
#     return tips

#     # ========== Build insights ==========

#     # --- MoM change ---
   



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
#     import plotly.express as px
#     chart_type = (meta or {}).get("chart_type")
#     measure_hint = (meta or {}).get("measure")  # e.g. "value_yoy", "unit_yoy", "value_sales"
#     import pandas as pd

#     # --- ensure month label exists (without touching server logic) ---
#     if "date" in df.columns and "month" not in df.columns:
#         df = df.copy()
#         df["date"] = pd.to_datetime(df["date"])
#         df["month"] = df["date"].dt.strftime("%b %Y")

#     # Build a chronological key for month labels so Plotly doesn't sort alphabetically
#     if "month" in df.columns and "_month_key" not in df.columns:
#         df = df.copy()
#         # Try the expected "%b %Y" first; fallback by prefixing a day
#         try:
#             df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
#         except Exception:
#             df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

#     # ---- Helper: keep sales for YoY bars ----
   
#     def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
#         if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
#             return ["value_sales_curr"]
#         if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
#             return ["unit_sales_curr"]
#         fallback = [c for c in _df.columns
#                     if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
#         return fallback[:1] if fallback else []

#     # ---- LINE CHART (trend) ----
#         # ---- LINE CHART (trend) ----
#     if chart_type == "line":
#         import pandas as pd
#         import plotly.express as px

#         # pick the x axis column
#         if "month_year" in df.columns:
#             xcol = "month_year"
#         elif "month" in df.columns:
#             xcol = "month"
#         elif "date" in df.columns:
#             xcol = "date"
#         else:
#             st.info("No date/month column in result to draw a trend.")
#             return

#         # find numeric column(s)
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to plot as a trend.")
#             return
#         y = ycols[0]   # take the first numeric measure

#         # choose a color grouping if available
#         color_col = None
#         for cand in ["brand", "category", "market", "channel", "segment", "manufacturer"]:
#             if cand in df.columns:
#                 color_col = cand
#                 break

#     # ---- BAR CHART (Top-N / categories / YoY) ----
#     if chart_type == "bar":
#         xcat = _find_x_cat(df)
#         if not xcat:
#             st.info("Not enough columns to draw a bar chart.")
#             return

#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ycols = _pick_y_for_yoy(df, measure_hint)
#             if not ycols:
#                 st.info("No current-period sales column for YoY chart.")
#                 return
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
#             st.plotly_chart(fig, use_container_width=True)
#             return

#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to draw a bar chart.")
#             return
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols,
#                            var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value",
#                          color="metric", barmode="group", title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- No chart hint: fallback to time trend if possible ----
#     if ("month" in df.columns) or ("date" in df.columns):
#         xcol = "month" if "month" in df.columns else "date"
#         ycols = _find_y_cols(df)
#         if ycols:
#             sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
#             sdf = df.sort_values(sort_col)
#             fig = px.line(sdf, x=xcol, y=ycols,color=color_col, markers=True, title="Trend over time")
#             if xcol == "month":
#                 ordered = (
#                     sdf.dropna(subset=[sort_col])
#                        .drop_duplicates(subset=["month"])
#                        .sort_values(sort_col)["month"]
#                        .tolist()
#                 )
#                 fig.update_xaxes(type="category",
#                                  categoryorder="array",
#                                  categoryarray=ordered)
#             else:
#                 fig.update_xaxes(tickformat="%b %Y")
#             _format_percent_axes(fig, ycols)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#     # ---- otherwise fallback bar ----
#     xcat = _find_x_cat(df)
#     ycols = _find_y_cols(df)
#     if xcat and ycols:
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ypick = _pick_y_for_yoy(df, measure_hint)
#             if ypick:
#                 fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
#                 st.plotly_chart(fig, use_container_width=True)
#                 return
#         fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)



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
#         if "date" in df.columns.tolist():
#             df["month"]=pd.to_datetime(df["date"]).dt.strftime("%b %Y")
#             df=df.drop(columns=["date"])
        


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
#        # ---------- key insights ----------
#         st.subheader("Key insights")
#         try:
#             insights = derive_insights_from_table(df, meta)
#             if insights:
#                 for s in insights:
#                     st.write(f"• {s}")
#             else:
#                 st.caption("No obvious insights for this result.")
#         except Exception as e:
#             st.caption(f"(Couldn’t generate insights: {e})")

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








# frontend/app.py
# frontend/app.py
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
# import random

# def derive_insights_from_table(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Works for:
#       • Top-N (bar) tables like: [brand, value_sales] or [brand, unit_sales]
#       • YoY bar tables like: [brand, value_sales_curr, value_sales_prev, value_yoy]
#       • Simple totals (no dims)
#       • Trend tables with date/month (falls back to simple delta)
#     Returns a short list of natural-language bullets.
#     """
#     if df is None or df.empty:
#         return []

#     tips: list[str] = []
#     m = (meta or {}).get("measure") or ""
#     dims = (meta or {}).get("dims") or []
#     cols = list(df.columns)
#     colset = set(cols)

#     # ---------- pick a primary numeric column ----------
#     # Prefer ..._curr for YoY responses → then value_sales / unit_sales → else first numeric
#     numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
#     prefer_order = []
#     prefer_order += [c for c in ["value_sales_curr", "unit_sales_curr"] if c in colset]
#     prefer_order += [c for c in ["value_sales", "unit_sales"] if c in colset]
#     if m and m in colset and m not in prefer_order:
#         prefer_order.insert(0, m)
#     primary = next((c for c in prefer_order if c in colset), None) or (numeric_cols[0] if numeric_cols else None)
#     if primary is None:
#         return tips

#     # ---------- detect the single category (x) column for bar charts ----------
#     cat_candidates = [c for c in ["brand","category","market","channel","segment","manufacturer"] if c in colset]
#     # If API already told us a dim, keep it; otherwise guess a single non-numeric column (not date/month)
#     if not cat_candidates:
#         cat_candidates = [c for c in cols if (c not in ("date","month","month_year")) and not pd.api.types.is_numeric_dtype(df[c])]
#     xcat = cat_candidates[0] if cat_candidates else None

#     # ---------- BAR / TOP-N INSIGHTS ----------
#     if xcat:
#         sub = df[[xcat, primary]].dropna()
#         # protect against duplicated keys (group if needed)
#         if sub[xcat].duplicated().any():
#             sub = sub.groupby(xcat, dropna=False)[primary].sum().reset_index()

#         if not sub.empty:
#             sub = sub.sort_values(primary, ascending=False)
#             leader_row = sub.iloc[0]
#             leader, lead_val = leader_row[xcat], float(leader_row[primary])

#             # 1) Leader
#             tips.append(f"{xcat.title()} “{leader}” leads on {primary.replace('_',' ')} ({lead_val:,.0f}).")

#             # 2) Gap vs #2 (if exists)
#             if len(sub) >= 2:
#                 runner_row = sub.iloc[1]
#                 runner, run_val = runner_row[xcat], float(runner_row[primary])
#                 gap = lead_val - run_val
#                 gap_pc = gap / (run_val + 1e-9)
#                 tips.append(f"Lead over #{2} “{runner}” is {gap:,.0f} ({gap_pc:+.0%}).")

#             # 3) Share of top brand (within the shown list)
#             total = float(sub[primary].sum())
#             if total > 0:
#                 top_share = lead_val / total
#                 tips.append(f"Top item holds {top_share:.0%} of the shown total.")

#             # 4) Concentration hint (HHI-ish)
#             share = sub[primary] / max(total, 1e-9)
#             hhi = float((share ** 2).sum())
#             if hhi >= 0.20:
#                 tips.append("Market looks concentrated among a few items.")
#             elif hhi <= 0.10:
#                 tips.append("Market looks fairly fragmented.")
#         # YoY extras
#         yoy_col = next((c for c in cols if c.endswith("_yoy")), None)
#         if yoy_col:
#             # Best YoY mover
#             yy = df[[xcat, yoy_col]].dropna()
#             if not yy.empty and pd.api.types.is_numeric_dtype(yy[yoy_col]):
#                 yy = yy.sort_values(yoy_col, ascending=False)
#                 best = yy.iloc[0]
#                 tips.append(f"Best {yoy_col.replace('_',' ')}: “{best[xcat]}” at {float(best[yoy_col]):+.1%}.")

#         return tips

#     # ---------- NO CATEGORY: totals or trend fallback ----------
#     # Trend: if there is a date/month column, comment on change over time
#     time_col = "month" if "month" in colset else ("date" if "date" in colset else None)
#     if time_col and pd.api.types.is_numeric_dtype(df[primary]):
#         try:
#             t = pd.to_datetime(df[time_col], errors="coerce")
#             s = df.loc[t.notna()].sort_values(t.name)[primary]
#             if len(s) >= 2:
#                 first, last = float(s.iloc[0]), float(s.iloc[-1])
#                 delta = (last - first) / (abs(first) + 1e-9)
#                 tips.append(f"{primary.replace('_',' ')} changed {delta:+.1%} across the period.")
#         except Exception:
#             pass

#     # If still nothing, provide a safe message
#     if not tips:
#         tips.append("No obvious spikes or gaps; values look stable.")
#     return tips

#     # ========== Build insights ==========

#     # --- MoM change ---
   



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
#     import plotly.express as px
#     chart_type = (meta or {}).get("chart_type")
#     measure_hint = (meta or {}).get("measure")  # e.g. "value_yoy", "unit_yoy", "value_sales"
#     import pandas as pd

#     # --- ensure month label exists (without touching server logic) ---
#     if "date" in df.columns and "month" not in df.columns:
#         df = df.copy()
#         df["date"] = pd.to_datetime(df["date"])
#         df["month"] = df["date"].dt.strftime("%b %Y")

#     # Build a chronological key for month labels so Plotly doesn't sort alphabetically
#     if "month" in df.columns and "_month_key" not in df.columns:
#         df = df.copy()
#         # Try the expected "%b %Y" first; fallback by prefixing a day
#         try:
#             df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
#         except Exception:
#             df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

#     # ---- Helper: keep sales for YoY bars ----
   
#     def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
#         if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
#             return ["value_sales_curr"]
#         if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
#             return ["unit_sales_curr"]
#         fallback = [c for c in _df.columns
#                     if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
#         return fallback[:1] if fallback else []

#     # ---- LINE CHART (trend) ----
#         # ---- LINE CHART (trend) ----
#     if chart_type == "line":
#         import pandas as pd
#         import plotly.express as px

#         # pick the x axis column
#         if "month_year" in df.columns:
#             xcol = "month_year"
#         elif "month" in df.columns:
#             xcol = "month"
#         elif "date" in df.columns:
#             xcol = "date"
#         else:
#             st.info("No date/month column in result to draw a trend.")
#             return

#         # find numeric column(s)
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to plot as a trend.")
#             return
#         y = ycols[0]   # take the first numeric measure

#         # choose a color grouping if available
#         color_col = None
#         for cand in ["brand", "category", "market", "channel", "segment", "manufacturer"]:
#             if cand in df.columns:
#                 color_col = cand
#                 break

#     # ---- BAR CHART (Top-N / categories / YoY) ----
    
#     if chart_type == "bar":
#         xcat = _find_x_cat(df)
#         # print(xcat)
#         if not xcat:
#             st.info("Not enough columns to draw a bar chart.")
#             return
        

#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ycols = _pick_y_for_yoy(df, measure_hint)
#             if not ycols:
#                 st.info("No current-period sales column for YoY chart.")
#                 return
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
#             st.plotly_chart(fig, use_container_width=True)
#             return

#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to draw a bar chart.")
#             return
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols,
#                            var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value",
#                          color="metric", barmode="group", title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- No chart hint: fallback to time trend if possible ----
#     if ("month" in df.columns) or ("date" in df.columns):
#         xcol = "month" if "month" in df.columns else "date"
#         ycols = _find_y_cols(df)
#         if ycols:
#             sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
#             sdf = df.sort_values(sort_col)
#             fig = px.line(sdf, x=xcol, y=ycols,color=color_col, markers=True, title="Trend over time")
#             if xcol == "month":
#                 ordered = (
#                     sdf.dropna(subset=[sort_col])
#                        .drop_duplicates(subset=["month"])
#                        .sort_values(sort_col)["month"]
#                        .tolist()
#                 )
#                 fig.update_xaxes(type="category",
#                                  categoryorder="array",
#                                  categoryarray=ordered)
#             else:
#                 fig.update_xaxes(tickformat="%b %Y")
#             _format_percent_axes(fig, ycols)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#     # ---- otherwise fallback bar ----
#     xcat = _find_x_cat(df)
#     ycols = _find_y_cols(df)
#     if xcat and ycols:
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ypick = _pick_y_for_yoy(df, measure_hint)
#             if ypick:
#                 fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
#                 st.plotly_chart(fig, use_container_width=True)
#                 return
#         fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)



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
#         if "date" in df.columns.tolist():
#             df["month"]=pd.to_datetime(df["date"]).dt.strftime("%b %Y")
#             df=df.drop(columns=["date"])
        


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
#        # ---------- key insights ----------
#         st.subheader("Key insights")
#         try:
#             insights = derive_insights_from_table(df, meta)
#             if insights:
#                 for s in insights:
#                     st.write(f"• {s}")
#             else:
#                 st.caption("No obvious insights for this result.")
#         except Exception as e:
#             st.caption(f"(Couldn’t generate insights: {e})")

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











#Working old frontend code


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
# import random

# def derive_insights_from_table(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Works for:
#       • Top-N (bar) tables like: [brand, value_sales] or [brand, unit_sales]
#       • YoY bar tables like: [brand, value_sales_curr, value_sales_prev, value_yoy]
#       • Simple totals (no dims)
#       • Trend tables with date/month (falls back to simple delta)
#     Returns a short list of natural-language bullets.
#     """
#     if df is None or df.empty:
#         return []

#     tips: list[str] = []
#     m = (meta or {}).get("measure") or ""
#     dims = (meta or {}).get("dims") or []
#     cols = list(df.columns)
#     colset = set(cols)

#     # ---------- pick a primary numeric column ----------
#     # Prefer ..._curr for YoY responses → then value_sales / unit_sales → else first numeric
#     numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
#     prefer_order = []
#     prefer_order += [c for c in ["value_sales_curr", "unit_sales_curr"] if c in colset]
#     prefer_order += [c for c in ["value_sales", "unit_sales"] if c in colset]
#     if m and m in colset and m not in prefer_order:
#         prefer_order.insert(0, m)
#     primary = next((c for c in prefer_order if c in colset), None) or (numeric_cols[0] if numeric_cols else None)
#     if primary is None:
#         return tips

#     # ---------- detect the single category (x) column for bar charts ----------
#     cat_candidates = [c for c in ["brand","category","market","channel","segment","manufacturer"] if c in colset]
#     # If API already told us a dim, keep it; otherwise guess a single non-numeric column (not date/month)
#     if not cat_candidates:
#         cat_candidates = [c for c in cols if (c not in ("date","month","month_year")) and not pd.api.types.is_numeric_dtype(df[c])]
#     xcat = cat_candidates[0] if cat_candidates else None

#     # ---------- BAR / TOP-N INSIGHTS ----------
#     if xcat:
#         sub = df[[xcat, primary]].dropna()
#         # protect against duplicated keys (group if needed)
#         if sub[xcat].duplicated().any():
#             sub = sub.groupby(xcat, dropna=False)[primary].sum().reset_index()

#         if not sub.empty:
#             sub = sub.sort_values(primary, ascending=False)
#             leader_row = sub.iloc[0]
#             leader, lead_val = leader_row[xcat], float(leader_row[primary])

#             # 1) Leader
#             tips.append(f"{xcat.title()} “{leader}” leads on {primary.replace('_',' ')} ({lead_val:,.0f}).")

#             # 2) Gap vs #2 (if exists)
#             if len(sub) >= 2:
#                 runner_row = sub.iloc[1]
#                 runner, run_val = runner_row[xcat], float(runner_row[primary])
#                 gap = lead_val - run_val
#                 gap_pc = gap / (run_val + 1e-9)
#                 tips.append(f"Lead over #{2} “{runner}” is {gap:,.0f} ({gap_pc:+.0%}).")

#             # 3) Share of top brand (within the shown list)
#             total = float(sub[primary].sum())
#             if total > 0:
#                 top_share = lead_val / total
#                 tips.append(f"Top item holds {top_share:.0%} of the shown total.")

#             # 4) Concentration hint (HHI-ish)
#             share = sub[primary] / max(total, 1e-9)
#             hhi = float((share ** 2).sum())
#             if hhi >= 0.20:
#                 tips.append("Market looks concentrated among a few items.")
#             elif hhi <= 0.10:
#                 tips.append("Market looks fairly fragmented.")
#         # YoY extras
#         yoy_col = next((c for c in cols if c.endswith("_yoy")), None)
#         if yoy_col:
#             # Best YoY mover
#             yy = df[[xcat, yoy_col]].dropna()
#             if not yy.empty and pd.api.types.is_numeric_dtype(yy[yoy_col]):
#                 yy = yy.sort_values(yoy_col, ascending=False)
#                 best = yy.iloc[0]
#                 tips.append(f"Best {yoy_col.replace('_',' ')}: “{best[xcat]}” at {float(best[yoy_col]):+.1%}.")

#         return tips

#     # ---------- NO CATEGORY: totals or trend fallback ----------
#     # Trend: if there is a date/month column, comment on change over time
#     time_col = "month" if "month" in colset else ("date" if "date" in colset else None)
#     if time_col and pd.api.types.is_numeric_dtype(df[primary]):
#         try:
#             t = pd.to_datetime(df[time_col], errors="coerce")
#             s = df.loc[t.notna()].sort_values(t.name)[primary]
#             if len(s) >= 2:
#                 first, last = float(s.iloc[0]), float(s.iloc[-1])
#                 delta = (last - first) / (abs(first) + 1e-9)
#                 tips.append(f"{primary.replace('_',' ')} changed {delta:+.1%} across the period.")
#         except Exception:
#             pass

#     # If still nothing, provide a safe message
#     if not tips:
#         tips.append("No obvious spikes or gaps; values look stable.")
#     return tips

#     # ========== Build insights ==========

#     # --- MoM change ---
   



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
#     import plotly.express as px
#     chart_type = (meta or {}).get("chart_type")
#     measure_hint = (meta or {}).get("measure")  # e.g. "value_yoy", "unit_yoy", "value_sales"
#     import pandas as pd

#     # --- ensure month label exists (without touching server logic) ---
#     if "date" in df.columns and "month" not in df.columns:
#         df = df.copy()
#         df["date"] = pd.to_datetime(df["date"])
#         df["month"] = df["date"].dt.strftime("%b %Y")

#     # Build a chronological key for month labels so Plotly doesn't sort alphabetically
#     if "month" in df.columns and "_month_key" not in df.columns:
#         df = df.copy()
#         # Try the expected "%b %Y" first; fallback by prefixing a day
#         try:
#             df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
#         except Exception:
#             df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

#     # ---- Helper: keep sales for YoY bars ----
   
#     def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
#         if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
#             return ["value_sales_curr"]
#         if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
#             return ["unit_sales_curr"]
#         fallback = [c for c in _df.columns
#                     if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
#         return fallback[:1] if fallback else []

#     # ---- LINE CHART (trend) ----
#         # ---- LINE CHART (trend) ----
#     if chart_type == "line":
#         import pandas as pd
#         import plotly.express as px

#         # pick the x axis column
#         if "month_year" in df.columns:
#             xcol = "month_year"
#         elif "month" in df.columns:
#             xcol = "month"
#         elif "date" in df.columns:
#             xcol = "date"
#         else:
#             st.info("No date/month column in result to draw a trend.")
#             return

#         # find numeric column(s)
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to plot as a trend.")
#             return
#         y = ycols[0]   # take the first numeric measure

#         # choose a color grouping if available
#         color_col = None
#         for cand in ["brand", "category", "market", "channel", "segment", "manufacturer"]:
#             if cand in df.columns:
#                 color_col = cand
#                 break

#     # ---- BAR CHART (Top-N / categories / YoY) ----
    
#     if chart_type == "bar":
#         xcat = _find_x_cat(df)
#         # print(xcat)
#         if not xcat:
#             st.info("Not enough columns to draw a bar chart.")
#             return
        

#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ycols = _pick_y_for_yoy(df, measure_hint)
#             if not ycols:
#                 st.info("No current-period sales column for YoY chart.")
#                 return
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
#             st.plotly_chart(fig, use_container_width=True)
#             return

#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to draw a bar chart.")
#             return
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols,
#                            var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value",
#                          color="metric", barmode="group", title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # ---- No chart hint: fallback to time trend if possible ----
#     if ("month" in df.columns) or ("date" in df.columns):
#         xcol = "month" if "month" in df.columns else "date"
#         ycols = _find_y_cols(df)
#         if ycols:
#             sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
#             sdf = df.sort_values(sort_col)
#             fig = px.line(sdf, x=xcol, y=ycols,color=color_col, markers=True, title="Trend over time")
#             if xcol == "month":
#                 ordered = (
#                     sdf.dropna(subset=[sort_col])
#                        .drop_duplicates(subset=["month"])
#                        .sort_values(sort_col)["month"]
#                        .tolist()
#                 )
#                 fig.update_xaxes(type="category",
#                                  categoryorder="array",
#                                  categoryarray=ordered)
#             else:
#                 fig.update_xaxes(tickformat="%b %Y")
#             _format_percent_axes(fig, ycols)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#     # ---- otherwise fallback bar ----
#     xcat = _find_x_cat(df)
#     ycols = _find_y_cols(df)
#     if xcat and ycols:
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ypick = _pick_y_for_yoy(df, measure_hint)
#             if ypick:
#                 fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
#                 st.plotly_chart(fig, use_container_width=True)
#                 return
#         fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)



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
#         # st.title("New Insights block")
#         # st.text("Automatically derived insights from the data:")
        

#         # ---------- intent + (legacy) sql ----------
#         st.subheader("Parsed intent")
#         st.json(out.get("intent", {}))
#         st.subheader("SQL")
#         st.code(out.get("sql"), language="sql")

#         # ---------- main result ----------
#         df = pd.DataFrame(out.get("data", []))
#         if "date" in df.columns.tolist():
#             df["month"]=pd.to_datetime(df["date"]).dt.strftime("%b %Y")
#             df=df.drop(columns=["date"])
        


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
#        # ---------- key insights ----------
#         st.subheader("Key insights")
#         try:
#             # insights = derive_insights_from_table(df, meta)
#             # if insights:
#             #     for s in insights:
#             #         st.write(f"• {s}")
#             # else:
#             #     st.caption("No obvious insights for this result.")
#             for s in out['insights']['bullets']:
#                     st.write(f"• {s}")
#             # st.write(f"{out.get('insights','No insights generated.')}")
#         except Exception as e:
#             st.caption(f"(Couldn’t generate insights: {e})")

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








# Code working for normal time series analysis to add server 




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

# import random

# def derive_insights_from_table(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Works for:
#       • Top-N (bar) tables like: [brand, value_sales] or [brand, unit_sales]
#       • YoY bar tables like: [brand, value_sales_curr, value_sales_prev, value_yoy]
#       • Simple totals (no dims)
#       • Trend tables with date/month (falls back to simple delta)
#     Returns a short list of natural-language bullets.
#     """
#     if df is None or df.empty:
#         return []

#     tips: list[str] = []
#     m = (meta or {}).get("measure") or ""
#     cols = list(df.columns)
#     colset = set(cols)

#     # pick primary numeric column
#     numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
#     prefer_order = []
#     prefer_order += [c for c in ["value_sales_curr", "unit_sales_curr"] if c in colset]
#     prefer_order += [c for c in ["value_sales", "unit_sales"] if c in colset]
#     if m and m in colset and m not in prefer_order:
#         prefer_order.insert(0, m)
#     primary = next((c for c in prefer_order if c in colset), None) or (numeric_cols[0] if numeric_cols else None)
#     if primary is None:
#         return tips

#     # category axis guess
#     cat_candidates = [c for c in ["brand","category","market","channel","segment","manufacturer"] if c in colset]
#     if not cat_candidates:
#         cat_candidates = [c for c in cols if (c not in ("date","month","month_year")) and not pd.api.types.is_numeric_dtype(df[c])]
#     xcat = cat_candidates[0] if cat_candidates else None

#     # BAR / TOP-N INSIGHTS
#     if xcat:
#         sub = df[[xcat, primary]].dropna()
#         if sub[xcat].duplicated().any():
#             sub = sub.groupby(xcat, dropna=False)[primary].sum().reset_index()

#         if not sub.empty:
#             sub = sub.sort_values(primary, ascending=False)
#             leader_row = sub.iloc[0]
#             leader, lead_val = leader_row[xcat], float(leader_row[primary])

#             tips.append(f"{xcat.title()} “{leader}” leads on {primary.replace('_',' ')} ({lead_val:,.0f}).")

#             if len(sub) >= 2:
#                 runner_row = sub.iloc[1]
#                 runner, run_val = runner_row[xcat], float(runner_row[primary])
#                 gap = lead_val - run_val
#                 gap_pc = gap / (run_val + 1e-9)
#                 tips.append(f"Lead over #{2} “{runner}” is {gap:,.0f} ({gap_pc:+.0%}).")

#             total = float(sub[primary].sum())
#             if total > 0:
#                 top_share = lead_val / total
#                 tips.append(f"Top item holds {top_share:.0%} of the shown total.")

#             share = sub[primary] / max(total, 1e-9)
#             hhi = float((share ** 2).sum())
#             if hhi >= 0.20:
#                 tips.append("Market looks concentrated among a few items.")
#             elif hhi <= 0.10:
#                 tips.append("Market looks fairly fragmented.")

#         yoy_col = next((c for c in cols if c.endswith("_yoy")), None)
#         if yoy_col:
#             yy = df[[xcat, yoy_col]].dropna()
#             if not yy.empty and pd.api.types.is_numeric_dtype(yy[yoy_col]):
#                 yy = yy.sort_values(yoy_col, ascending=False)
#                 best = yy.iloc[0]
#                 tips.append(f"Best {yoy_col.replace('_',' ')}: “{best[xcat]}” at {float(best[yoy_col]):+.1%}.")
#         return tips

#     # Trend fallback
#     time_col = "month" if "month" in colset else ("date" if "date" in colset else None)
#     if time_col and pd.api.types.is_numeric_dtype(df[primary]):
#         try:
#             t = pd.to_datetime(df[time_col], errors="coerce")
#             s = df.loc[t.notna()].sort_values(t.name)[primary]
#             if len(s) >= 2:
#                 first, last = float(s.iloc[0]), float(s.iloc[-1])
#                 delta = (last - first) / (abs(first) + 1e-9)
#                 tips.append(f"{primary.replace('_',' ')} changed {delta:+.1%} across the period.")
#         except Exception:
#             pass

#     if not tips:
#         tips.append("No obvious spikes or gaps; values look stable.")
#     return tips


# def _preferred_measure_for_line(df: pd.DataFrame) -> str | None:
#     for c in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr")):
#             return c
#     return None

# def _month_category_order(df: pd.DataFrame) -> list[str]:
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
#     priority = ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]
#     y = [c for c in priority if c in df.columns]
#     if not y:
#         y = [c for c in _numeric_cols(df) if not c.endswith("_prev") and not c.endswith("_curr")]
#     return y[:6]

# def _find_x_cat(df: pd.DataFrame):
#     for c in CAT_CANDIDATES:
#         if c in df.columns:
#             return c
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
#             df["date_label"] = df["date"].dt.strftime("%b %Y")
#             return df
#         except Exception:
#             return df
#     return df

# def render_chart(df: pd.DataFrame, meta: dict):
#     chart_type = (meta or {}).get("chart_type")
#     measure_hint = (meta or {}).get("measure")

#     # add month label if only date present
#     if "date" in df.columns and "month" not in df.columns:
#         df = df.copy()
#         df["date"] = pd.to_datetime(df["date"])
#         df["month"] = df["date"].dt.strftime("%b %Y")

#     if "month" in df.columns and "_month_key" not in df.columns:
#         df = df.copy()
#         try:
#             df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
#         except Exception:
#             df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

#     def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
#         if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
#             return ["value_sales_curr"]
#         if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
#             return ["unit_sales_curr"]
#         fallback = [c for c in _df.columns if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
#         return fallback[:1] if fallback else []

#     # Explicit BAR
#     if chart_type == "bar":
#         xcat = _find_x_cat(df)
#         if not xcat:
#             st.info("Not enough columns to draw a bar chart.")
#             return
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ycols = _pick_y_for_yoy(df, measure_hint)
#             if not ycols:
#                 st.info("No current-period sales column for YoY chart.")
#                 return
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
#             st.plotly_chart(fig, use_container_width=True)
#             return
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to draw a bar chart.")
#             return
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols,
#                            var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value",
#                          color="metric", barmode="group", title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # Fallback Trend
#     if ("month" in df.columns) or ("date" in df.columns):
#         xcol = "month" if "month" in df.columns else "date"
#         ycols = _find_y_cols(df)
#         if ycols:
#             sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
#             sdf = df.sort_values(sort_col)
#             # choose a color/grouping if available
#             color_col = None
#             for cand in ["brand", "category", "market", "channel", "segment", "manufacturer"]:
#                 if cand in df.columns:
#                     color_col = cand
#                     break
#             fig = px.line(sdf, x=xcol, y=ycols, color=color_col, markers=True, title="Trend over time")
#             if xcol == "month":
#                 ordered = (
#                     sdf.dropna(subset=[sort_col])
#                        .drop_duplicates(subset=["month"])
#                        .sort_values(sort_col)["month"]
#                        .tolist()
#                 )
#                 fig.update_xaxes(type="category", categoryorder="array", categoryarray=ordered)
#             else:
#                 fig.update_xaxes(tickformat="%b %Y")
#             _format_percent_axes(fig, ycols)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#     # If we reach here, fallback bar if possible
#     xcat = _find_x_cat(df)
#     ycols = _find_y_cols(df)
#     if xcat and ycols:
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ypick = _pick_y_for_yoy(df, measure_hint)
#             if ypick:
#                 fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
#                 st.plotly_chart(fig, use_container_width=True)
#                 return
#         fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     st.info("No chart rendered (not enough columns to infer a chart).")


# # ---------------- Section: Ask ----------------
# st.header("2) Ask a question")

# # New controls (we pass these to backend)
# c1, c2, c3 = st.columns([3,1,1])
# with c1:
#     q = st.text_input(
#         'Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart',
#         "",
#     )
# with c2:
#     do_fc = st.toggle("Forecast", value=False, help="Ask backend to include 1–3 month forecast in response")
# with c3:
#     show_sig = st.toggle("Signals", value=True, help="Ask backend to include anomaly/share-jump signals")

# if st.button("Ask", type="primary"):
#     payload = {"question": q, "forecast": do_fc, "signals": show_sig}
#     resp = requests.post(f"{API}/ask", json=payload)
#     if not resp.ok:
#         st.error(resp.text)
#     else:
#         st.session_state["out"] = resp.json()

# # ---------------- Render Tabs ----------------
# out = st.session_state.get("out")
# if out:
#     # Parsed intent + SQL (kept for transparency; moved into Debug tab later)
#     meta = out.get("meta", {}) or {}
#     df = pd.DataFrame(out.get("data", []))

#     # Add month label for convenience
#     if "date" in df.columns.tolist():
#         df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%b %Y")
#         if "date" in df.columns:
#             df = df.drop(columns=["date"])

#     tabs = st.tabs(["Table", "Chart", "Insights", "Signals", "Forecast", "Time Series", "Debug"])

#     # ---- Table Tab ----
#     with tabs[0]:
#         st.subheader("Result")
#         if df.empty:
#             st.warning("No data for this query.")
#         else:
#             st.dataframe(df, use_container_width=True)
#             st.download_button("Download CSV", df.to_csv(index=False), "result.csv")

#     # ---- Chart Tab ----
#     with tabs[1]:
#         if df.empty:
#             st.info("No data to chart.")
#         else:
#             render_chart(df, meta)

#     # ---- Insights Tab ----
#     with tabs[2]:
#         st.subheader("Key insights")
#         try:
#             if "insights" in out and out["insights"] and out["insights"].get("bullets"):
#                 for s in out["insights"]["bullets"]:
#                     st.write(f"• {s}")
#             else:
#                 # Fallback: derive quick tips locally
#                 local_bullets = derive_insights_from_table(df, meta)
#                 if local_bullets:
#                     for s in local_bullets:
#                         st.write(f"• {s}")
#                 else:
#                     st.caption("No obvious insights for this result.")
#             if isinstance(out.get("insights", {}), dict) and out["insights"].get("evidence_note"):
#                 st.caption(out["insights"]["evidence_note"])
#         except Exception as e:
#             st.caption(f"(Couldn’t render insights: {e})")

#     # ---- Signals Tab ----
#     with tabs[3]:
#         st.subheader("Signals (anomalies, share jumps)")
#         events = out.get("events", [])
#         if events:
#             for ev in events:
#                 st.info(f"{ev.get('date')}: {ev.get('event_type')} (strength: {ev.get('strength')}) — {ev.get('details')}")
#         else:
#             st.caption("No signals provided (enable 'Signals' or implement server-side events).")

#     # ---- Forecast Tab (server-provided) ----
#     with tabs[4]:
#         st.subheader("Short-horizon forecast")
#         fc = out.get("forecast")
#         if fc and isinstance(fc, dict) and fc.get("figure"):
#             # If backend sends Plotly JSON
#             st.plotly_chart(fc["figure"], use_container_width=True)
#             if "backtest_mape" in fc:
#                 st.caption(f"Backtest MAPE ~ {fc['backtest_mape']:.1%}")
#         else:
#             st.caption("No forecast in response. Toggle 'Forecast' above or implement forecast in /ask.")

#     # ---- Time Series Tab (local analysis + simple seasonal-naive forecast) ----
#     # ---- Time Series Tab (robust) ----
#     with tabs[5]:
#         st.subheader("Time Series Analysis")

#         if df.empty:
#             st.info("Run a query that returns a monthly time series to analyze.")
#         else:
#             # 0) Detect a usable time column (be generous with names)
#             time_candidates = [
#                 c for c in df.columns
#                 if str(c).lower() in ("month","month_year","monthdate","month_date","date","period")
#             ]
#             time_col = time_candidates[0] if time_candidates else None

#             if not time_col:
#                 st.warning("No time column found. Expecting one of: month / month_year / month_date / date.")
#                 st.write("Columns I see:", list(df.columns))
#             else:
#                 # 1) Choose a numeric measure; fallback to first numeric col
#                 num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
#                 if not num_cols:
#                     st.warning("No numeric measure available in the result to analyze.")
#                     st.write("Columns I see:", list(df.columns))
#                 else:
#                     c1, c2, c3 = st.columns([2,2,2])
#                     with c1:
#                         measure = st.selectbox("Measure", num_cols, index=0)
#                     # Optional dimension focus (if multiple series exist)
#                     cat_cols = [c for c in df.columns if c not in [time_col] + num_cols]
#                     with c2:
#                         focus_dim = st.selectbox("Optional dimension", ["(none)"] + cat_cols, index=0)
#                     with c3:
#                         focus_val = None
#                         if focus_dim and focus_dim != "(none)":
#                             vals = ["(all)"] + sorted([str(v) for v in df[focus_dim].dropna().unique().tolist()])
#                             focus_val = st.selectbox("Value", vals, index=0)
#                             if focus_val == "(all)":
#                                 focus_val = None

#                     sdf = df.copy()
#                     if focus_dim and focus_dim != "(none)" and focus_val:
#                         sdf = sdf[sdf[focus_dim].astype(str) == focus_val]

#                     # 2) Build a DatetimeIndex key from time_col (handle many formats)
#                     #    Accepts "Jan 2023", "2023-01-01", "2023-01", etc.
#                     _raw = sdf[time_col].astype(str)
#                     # First attempt: strict Month Year like "Jan 2023"
#                     _mkey = pd.to_datetime(_raw, format="%b %Y", errors="coerce")
#                     # Fallback: try plain to_datetime (will parse ISO, %Y-%m, etc.)
#                     mask = _mkey.isna()
#                     if mask.any():
#                         _mkey.loc[mask] = pd.to_datetime(_raw[mask], errors="coerce")

#                     sdf = sdf.assign(_mkey=_mkey)
#                     # Diagnostics
#                     st.caption(f"Parsed {sdf['_mkey'].notna().sum()} rows into valid months; "
#                             f"{sdf['_mkey'].isna().sum()} rows failed parsing and will be ignored.")

#                     # 3) Collapse duplicates per month (sum; switch to mean() if you prefer)
#                     ts = (
#                         sdf.dropna(subset=["_mkey"])
#                         .groupby("_mkey")[measure]
#                         .sum(min_count=1)
#                         .astype(float)
#                         .sort_index()
#                     )

#                     if ts.empty:
#                         st.warning("No time series points after filtering/aggregation.")
#                         with st.expander("See sample of filtered data"):
#                             st.dataframe(sdf.head(20))
#                     else:
#                         # 4) Normalize index to month start — NO 'MS' with Period
#                         ts.index = ts.index.to_period("M").to_timestamp(how="start")
#                         # paranoia: collapse remaining dups after normalization
#                         ts = ts.groupby(level=0).sum(min_count=1).sort_index()

#                         # 5) Create complete monthly range (DatetimeIndex with freq='MS')
#                         start = ts.index.min().replace(day=1)
#                         end   = ts.index.max().replace(day=1)
#                         full_idx = pd.date_range(start, end, freq="MS")
#                         ts = ts.reindex(full_idx)

#                         # 6) Plot base series + rolling mean
#                         win = st.slider("Rolling mean window (months)", 1, 12, 3, help="Set ≥2 to draw")
#                         ts_df = ts.reset_index()
#                         ts_df.columns = ["month_date", measure]

#                         fig_ts = px.line(ts_df, x="month_date", y=measure, markers=True, title="Time series")
#                         if win >= 2:
#                             roll = ts.rolling(win, min_periods=win).mean().reset_index()
#                             roll.columns = ["month_date", "rolling_mean"]
#                             fig_ts.add_scatter(x=roll["month_date"], y=roll["rolling_mean"],
#                                             mode="lines", name=f"Rolling mean ({win})")
#                         fig_ts.update_xaxes(tickformat="%b %Y")
#                         st.plotly_chart(fig_ts, use_container_width=True)

#                         # 7) ACF (simple)
#                         st.markdown("**Autocorrelation (ACF)**")
#                         max_lag = st.slider("Max lag", 1, 18, 12)
#                         base = ts - ts.mean()
#                         denom = float((base**2).sum(skipna=True)) or 0.0
#                         acf_vals = []
#                         for lag in range(1, max_lag+1):
#                             num = (base.shift(lag) * base).dropna().sum()
#                             acf_vals.append(float(num) / denom if denom else 0.0)
#                         acf_df = pd.DataFrame({"lag": list(range(1, max_lag+1)), "acf": acf_vals})
#                         fig_acf = px.bar(acf_df, x="lag", y="acf", title="ACF (naive)")
#                         st.plotly_chart(fig_acf, use_container_width=True)

#                         # 8) Seasonal-naive forecast (local quick look)
#                         st.markdown("**Seasonal-naive forecast**")
#                         horizon = st.slider("Horizon (months)", 1, 6, 3)
#                         future_idx = pd.date_range(ts.index.max() + pd.offsets.MonthBegin(1),
#                                                 periods=horizon, freq="MS")
#                         if len(ts.dropna()) >= 12:
#                             fcast = []
#                             for fi in future_idx:
#                                 src = fi - pd.DateOffset(years=1)
#                                 val = ts.get(src, default=np.nan)
#                                 if pd.isna(val):
#                                     val = ts.iloc[-1]
#                                 fcast.append(float(val))
#                         else:
#                             last_val = float(ts.dropna().iloc[-1])
#                             fcast = [last_val]*horizon

#                         fc_df = pd.DataFrame({"month_date": future_idx, "forecast": fcast})
#                         fig_fc = px.line(fc_df, x="month_date", y="forecast", markers=True,
#                                         title="Seasonal-naive forecast")
#                         fig_fc.update_xaxes(tickformat="%b %Y")
#                         st.plotly_chart(fig_fc, use_container_width=True)
#                         st.dataframe(fc_df.assign(month=lambda x: x["month_date"].dt.strftime("%b %Y"))
#                                         .drop(columns=["month_date"]))

#                         # 9) (Optional) Use backend ARIMA/SARIMA/Prophet
#                         st.divider()
#                         st.markdown("**Model-based forecast (server)**")
#                         colm1, colm2, colm3 = st.columns([2,1,1])
#                         with colm1:
#                             model_choice = st.selectbox("Model", ["ARIMA","SARIMA","Prophet"])
#                         with colm2:
#                             h = st.number_input("Horizon (months)", 1, 24, 6)
#                         run_server_fc = st.button("Run server forecast")
#                         if run_server_fc:
#                             # Expect a backend route that accepts {points: [{date, value}], model, horizon}
#                             # You can wire this to your notebook code moved into FastAPI.
#                             payload_fc = {
#                                 "model": model_choice,
#                                 "horizon": int(h),
#                                 "series": [
#                                     {"date": d.strftime("%Y-%m-%d"), "value": (0.0 if pd.isna(v) else float(v))}
#                                     for d, v in ts.items()
#                                 ],
#                                 "measure": measure,
#                                 "filters": {focus_dim: focus_val} if focus_dim and focus_val else {}
#                             }
#                             try:
#                                 rfc = requests.post(f"{API}/forecast", json=payload_fc, timeout=120)
#                                 if rfc.ok:
#                                     fr = rfc.json()
#                                     if "figure" in fr:
#                                         st.plotly_chart(fr["figure"], use_container_width=True)
#                                     elif "fcst" in fr:
#                                         fdf = pd.DataFrame(fr["fcst"])
#                                         fig_srv = px.line(fdf, x=fdf.columns[0], y=fdf.columns[1], markers=True,
#                                                         title=f"{model_choice} forecast (server)")
#                                         st.plotly_chart(fig_srv, use_container_width=True)
#                                         st.dataframe(fdf)
#                                     if "mape" in fr:
#                                         st.caption(f"Backtest MAPE: {fr['mape']:.2%}")
#                                 else:
#                                     st.error(rfc.text)
#                             except Exception as ex:
#                                 st.error(f"Server forecast call failed: {ex}")

#             # Tiny debug readout
#             with st.expander("🔎 Time Series debug"):
#                 st.write("Detected time column:", time_col)
#                 st.write("Rows in df:", len(df))
#                 if not df.empty:
#                     st.write("Numeric columns:", num_cols if 'num_cols' in locals() else [])
#                     st.write("Example head:", df.head(5))

#     # ---- Debug Tab ----
#     with tabs[6]:
#         st.subheader("Parsed intent")
#         st.json(out.get("intent", {}))
#         st.subheader("SQL")
#         st.code(out.get("sql"), language="sql")
#         st.subheader("Resolved meta")
#         win = meta.get("window") or {}
#         st.write("**Measure:**", meta.get("measure"))
#         st.write("**Dims:**", meta.get("dims"))
#         st.write("**Filters:**", meta.get("filters"))
#         st.write("**Mode:**", meta.get("mode"))
#         st.write("**Chart hint:**", meta.get("chart_type"))
#         st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")
#         if "month_current" in meta or "month_previous" in meta:
#             st.write("**MoM Anchor:**", meta.get("anchor"))
#             cur = meta.get("month_current", {})
#             prv = meta.get("month_previous", {})
#             st.write("• Current month:", f"{cur.get('start')} → {cur.get('end')}")
#             st.write("• Previous month:", f"{prv.get('start')} → {prv.get('end')}")
#         dbg = meta.get("debug") or {}
#         if isinstance(dbg, dict) and "prev_window" in dbg:
#             pw = dbg["prev_window"]
#             st.write("**YoY previous window:**", f"{pw.get('start')} → {pw.get('end')}")
#         st.json(meta, expanded=False)
# else:
#     st.caption("Tip: upload an Excel, type a query, toggle Forecast/Signals if needed, and click Ask.")










#Code working for time series analysis with prophet, sarima and arima based model forecasting





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

# import random
# def run_server_forecast(API_BASE: str, ts: pd.Series, model: str, horizon: int):
#     """
#     Send a monthly-start DatetimeIndex series to FastAPI /forecast and return a DataFrame.
#     ts must already be normalized to a monthly DatetimeIndex (freq='MS') with numeric values.
#     """
#     # drop NaNs; backend can interpolate/missings but cleaner to send non-nulls
#     ser = ts.dropna()
#     if ser.empty:
#         raise ValueError("No non-null points to send for forecasting.")

#     payload = {
#         "model": model,            # "ARIMA" | "SARIMA" | "Prophet"
#         "horizon": int(horizon),
#         "series": [
#             {"date": d.strftime("%Y-%m-%d"), "value": float(v)}
#             for d, v in ser.items()
#         ],
#         "measure": None,
#         "filters": {}
#     }

#     r = requests.post(f"{API_BASE}/forecast", json=payload, timeout=120)
#     if not r.ok:
#         # surface FastAPI error cleanly
#         try:
#             err = r.json().get("detail", r.text)
#         except Exception:
#             err = r.text
#         raise RuntimeError(f"Server forecast failed: {err}")

#     out = r.json() or {}
#     fcst = out.get("fcst") or []
#     if not fcst:
#         raise RuntimeError("Server returned no forecast points.")

#     # The backend returns [{"month":"Jan 2026","yhat":..., "yhat_lo":..., "yhat_hi":...}, ...]
#     fdf = pd.DataFrame(fcst)

#     # Normalize columns for plotting
#     # Prefer datetime x if you want: we can reconstruct from last observed + horizon
#     if "month" in fdf.columns:
#         # keep month labels for category x-axis
#         x = fdf["month"]
#     else:
#         # fallback: make a simple 1..H horizon index
#         x = list(range(1, len(fdf) + 1))
#         fdf.insert(0, "step", x)

#     return fdf


# def derive_insights_from_table(df: pd.DataFrame, meta: dict) -> list[str]:
#     """
#     Works for:
#       • Top-N (bar) tables like: [brand, value_sales] or [brand, unit_sales]
#       • YoY bar tables like: [brand, value_sales_curr, value_sales_prev, value_yoy]
#       • Simple totals (no dims)
#       • Trend tables with date/month (falls back to simple delta)
#     Returns a short list of natural-language bullets.
#     """
#     if df is None or df.empty:
#         return []

#     tips: list[str] = []
#     m = (meta or {}).get("measure") or ""
#     cols = list(df.columns)
#     colset = set(cols)

#     # pick primary numeric column
#     numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
#     prefer_order = []
#     prefer_order += [c for c in ["value_sales_curr", "unit_sales_curr"] if c in colset]
#     prefer_order += [c for c in ["value_sales", "unit_sales"] if c in colset]
#     if m and m in colset and m not in prefer_order:
#         prefer_order.insert(0, m)
#     primary = next((c for c in prefer_order if c in colset), None) or (numeric_cols[0] if numeric_cols else None)
#     if primary is None:
#         return tips

#     # category axis guess
#     cat_candidates = [c for c in ["brand","category","market","channel","segment","manufacturer"] if c in colset]
#     if not cat_candidates:
#         cat_candidates = [c for c in cols if (c not in ("date","month","month_year")) and not pd.api.types.is_numeric_dtype(df[c])]
#     xcat = cat_candidates[0] if cat_candidates else None

#     # BAR / TOP-N INSIGHTS
#     if xcat:
#         sub = df[[xcat, primary]].dropna()
#         if sub[xcat].duplicated().any():
#             sub = sub.groupby(xcat, dropna=False)[primary].sum().reset_index()

#         if not sub.empty:
#             sub = sub.sort_values(primary, ascending=False)
#             leader_row = sub.iloc[0]
#             leader, lead_val = leader_row[xcat], float(leader_row[primary])

#             tips.append(f"{xcat.title()} “{leader}” leads on {primary.replace('_',' ')} ({lead_val:,.0f}).")

#             if len(sub) >= 2:
#                 runner_row = sub.iloc[1]
#                 runner, run_val = runner_row[xcat], float(runner_row[primary])
#                 gap = lead_val - run_val
#                 gap_pc = gap / (run_val + 1e-9)
#                 tips.append(f"Lead over #{2} “{runner}” is {gap:,.0f} ({gap_pc:+.0%}).")

#             total = float(sub[primary].sum())
#             if total > 0:
#                 top_share = lead_val / total
#                 tips.append(f"Top item holds {top_share:.0%} of the shown total.")

#             share = sub[primary] / max(total, 1e-9)
#             hhi = float((share ** 2).sum())
#             if hhi >= 0.20:
#                 tips.append("Market looks concentrated among a few items.")
#             elif hhi <= 0.10:
#                 tips.append("Market looks fairly fragmented.")

#         yoy_col = next((c for c in cols if c.endswith("_yoy")), None)
#         if yoy_col:
#             yy = df[[xcat, yoy_col]].dropna()
#             if not yy.empty and pd.api.types.is_numeric_dtype(yy[yoy_col]):
#                 yy = yy.sort_values(yoy_col, ascending=False)
#                 best = yy.iloc[0]
#                 tips.append(f"Best {yoy_col.replace('_',' ')}: “{best[xcat]}” at {float(best[yoy_col]):+.1%}.")
#         return tips

#     # Trend fallback
#     time_col = "month" if "month" in colset else ("date" if "date" in colset else None)
#     if time_col and pd.api.types.is_numeric_dtype(df[primary]):
#         try:
#             t = pd.to_datetime(df[time_col], errors="coerce")
#             s = df.loc[t.notna()].sort_values(t.name)[primary]
#             if len(s) >= 2:
#                 first, last = float(s.iloc[0]), float(s.iloc[-1])
#                 delta = (last - first) / (abs(first) + 1e-9)
#                 tips.append(f"{primary.replace('_',' ')} changed {delta:+.1%} across the period.")
#         except Exception:
#             pass

#     if not tips:
#         tips.append("No obvious spikes or gaps; values look stable.")
#     return tips


# def _preferred_measure_for_line(df: pd.DataFrame) -> str | None:
#     for c in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
#         if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
#             return c
#     for c in df.columns:
#         if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr")):
#             return c
#     return None

# def _month_category_order(df: pd.DataFrame) -> list[str]:
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
#     priority = ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]
#     y = [c for c in priority if c in df.columns]
#     if not y:
#         y = [c for c in _numeric_cols(df) if not c.endswith("_prev") and not c.endswith("_curr")]
#     return y[:6]

# def _find_x_cat(df: pd.DataFrame):
#     for c in CAT_CANDIDATES:
#         if c in df.columns:
#             return c
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
#             df["date_label"] = df["date"].dt.strftime("%b %Y")
#             return df
#         except Exception:
#             return df
#     return df

# def render_chart(df: pd.DataFrame, meta: dict):
#     chart_type = (meta or {}).get("chart_type")
#     measure_hint = (meta or {}).get("measure")

#     # add month label if only date present
#     if "date" in df.columns and "month" not in df.columns:
#         df = df.copy()
#         df["date"] = pd.to_datetime(df["date"])
#         df["month"] = df["date"].dt.strftime("%b %Y")

#     if "month" in df.columns and "_month_key" not in df.columns:
#         df = df.copy()
#         try:
#             df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
#         except Exception:
#             df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

#     def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
#         if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
#             return ["value_sales_curr"]
#         if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
#             return ["unit_sales_curr"]
#         fallback = [c for c in _df.columns if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
#         return fallback[:1] if fallback else []

#     # Explicit BAR
#     if chart_type == "bar":
#         xcat = _find_x_cat(df)
#         if not xcat:
#             st.info("Not enough columns to draw a bar chart.")
#             return
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ycols = _pick_y_for_yoy(df, measure_hint)
#             if not ycols:
#                 st.info("No current-period sales column for YoY chart.")
#                 return
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Current-period Sales")
#             st.plotly_chart(fig, use_container_width=True)
#             return
#         ycols = _find_y_cols(df)
#         if not ycols:
#             st.info("No numeric columns to draw a bar chart.")
#             return
#         if len(ycols) > 1:
#             long = df.melt(id_vars=[xcat], value_vars=ycols,
#                            var_name="metric", value_name="value")
#             fig = px.bar(long, x=xcat, y="value",
#                          color="metric", barmode="group", title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         else:
#             fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#             _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     # Fallback Trend
#     if ("month" in df.columns) or ("date" in df.columns):
#         xcol = "month" if "month" in df.columns else "date"
#         ycols = _find_y_cols(df)
#         if ycols:
#             sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
#             sdf = df.sort_values(sort_col)
#             # choose a color/grouping if available
#             color_col = None
#             for cand in ["brand", "category", "market", "channel", "segment", "manufacturer"]:
#                 if cand in df.columns:
#                     color_col = cand
#                     break
#             fig = px.line(sdf, x=xcol, y=ycols, color=color_col, markers=True, title="Trend over time")
#             if xcol == "month":
#                 ordered = (
#                     sdf.dropna(subset=[sort_col])
#                        .drop_duplicates(subset=["month"])
#                        .sort_values(sort_col)["month"]
#                        .tolist()
#                 )
#                 fig.update_xaxes(type="category", categoryorder="array", categoryarray=ordered)
#             else:
#                 fig.update_xaxes(tickformat="%b %Y")
#             _format_percent_axes(fig, ycols)
#             st.plotly_chart(fig, use_container_width=True)
#             return

#     # If we reach here, fallback bar if possible
#     xcat = _find_x_cat(df)
#     ycols = _find_y_cols(df)
#     if xcat and ycols:
#         if measure_hint in ("value_yoy", "unit_yoy"):
#             ypick = _pick_y_for_yoy(df, measure_hint)
#             if ypick:
#                 fig = px.bar(df, x=xcat, y=ypick[0], title="Current-period Sales")
#                 st.plotly_chart(fig, use_container_width=True)
#                 return
#         fig = px.bar(df, x=xcat, y=ycols[0], title="Bar chart")
#         _format_percent_axes(fig, ycols)
#         st.plotly_chart(fig, use_container_width=True)
#         return

#     st.info("No chart rendered (not enough columns to infer a chart).")


# # ---------------- Section: Ask ----------------
# st.header("2) Ask a question")

# # New controls (we pass these to backend)
# c1, c2, c3 = st.columns([3,1,1])
# with c1:
#     q = st.text_input(
#         'Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart',
#         "",
#     )
# with c2:
#     do_fc = st.toggle("Forecast", value=False, help="Ask backend to include 1–3 month forecast in response")
# with c3:
#     show_sig = st.toggle("Signals", value=True, help="Ask backend to include anomaly/share-jump signals")

# if st.button("Ask", type="primary"):
#     payload = {"question": q, "forecast": do_fc, "signals": show_sig}
#     resp = requests.post(f"{API}/ask", json=payload)
#     if not resp.ok:
#         st.error(resp.text)
#     else:
#         st.session_state["out"] = resp.json()

# # ---------------- Render Tabs ----------------
# out = st.session_state.get("out")
# if out:
#     # Parsed intent + SQL (kept for transparency; moved into Debug tab later)
#     meta = out.get("meta", {}) or {}
#     df = pd.DataFrame(out.get("data", []))

#     # Add month label for convenience
#     if "date" in df.columns.tolist():
#         df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%b %Y")
#         if "date" in df.columns:
#             df = df.drop(columns=["date"])

#     tabs = st.tabs(["Table", "Chart", "Insights", "Signals", "Forecast", "Time Series", "Debug"])

#     # ---- Table Tab ----
#     with tabs[0]:
#         st.subheader("Result")
#         if df.empty:
#             st.warning("No data for this query.")
#         else:
#             st.dataframe(df, use_container_width=True)
#             st.download_button("Download CSV", df.to_csv(index=False), "result.csv")

#     # ---- Chart Tab ----
#     with tabs[1]:
#         if df.empty:
#             st.info("No data to chart.")
#         else:
#             render_chart(df, meta)

#     # ---- Insights Tab ----
#     with tabs[2]:
#         st.subheader("Key insights")
#         try:
#             if "insights" in out and out["insights"] and out["insights"].get("bullets"):
#                 for s in out["insights"]["bullets"]:
#                     st.write(f"• {s}")
#             else:
#                 # Fallback: derive quick tips locally
#                 local_bullets = derive_insights_from_table(df, meta)
#                 if local_bullets:
#                     for s in local_bullets:
#                         st.write(f"• {s}")
#                 else:
#                     st.caption("No obvious insights for this result.")
#             if isinstance(out.get("insights", {}), dict) and out["insights"].get("evidence_note"):
#                 st.caption(out["insights"]["evidence_note"])
#         except Exception as e:
#             st.caption(f"(Couldn’t render insights: {e})")

#     # ---- Signals Tab ----
#     with tabs[3]:
#         st.subheader("Signals (anomalies, share jumps)")
#         events = out.get("events", [])
#         if events:
#             for ev in events:
#                 st.info(f"{ev.get('date')}: {ev.get('event_type')} (strength: {ev.get('strength')}) — {ev.get('details')}")
#         else:
#             st.caption("No signals provided (enable 'Signals' or implement server-side events).")

#     # ---- Forecast Tab (server-provided) ----
#     with tabs[4]:
#         st.subheader("Short-horizon forecast")
#         fc = out.get("forecast")
#         if fc and isinstance(fc, dict) and fc.get("figure"):
#             # If backend sends Plotly JSON
#             st.plotly_chart(fc["figure"], use_container_width=True)
#             if "backtest_mape" in fc:
#                 st.caption(f"Backtest MAPE ~ {fc['backtest_mape']:.1%}")
#         else:
#             st.caption("No forecast in response. Toggle 'Forecast' above or implement forecast in /ask.")

#     # ---- Time Series Tab (local analysis + simple seasonal-naive forecast) ----
#     # ---- Time Series Tab (robust) ----
#     with tabs[5]:
#         st.subheader("Time Series Analysis")

#         if df.empty:
#             st.info("Run a query that returns a monthly time series to analyze.")
#         else:
#             # 0) Detect a usable time column (be generous with names)
#             time_candidates = [
#                 c for c in df.columns
#                 if str(c).lower() in ("month","month_year","monthdate","month_date","date","period")
#             ]
#             time_col = time_candidates[0] if time_candidates else None

#             if not time_col:
#                 st.warning("No time column found. Expecting one of: month / month_year / month_date / date.")
#                 st.write("Columns I see:", list(df.columns))
#             else:
#                 # 1) Choose a numeric measure; fallback to first numeric col
#                 num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
#                 if not num_cols:
#                     st.warning("No numeric measure available in the result to analyze.")
#                     st.write("Columns I see:", list(df.columns))
#                 else:
#                     c1, c2, c3 = st.columns([2,2,2])
#                     with c1:
#                         measure = st.selectbox("Measure", num_cols, index=0)
#                     # Optional dimension focus (if multiple series exist)
#                     cat_cols = [c for c in df.columns if c not in [time_col] + num_cols]
#                     with c2:
#                         focus_dim = st.selectbox("Optional dimension", ["(none)"] + cat_cols, index=0)
#                     with c3:
#                         focus_val = None
#                         if focus_dim and focus_dim != "(none)":
#                             vals = ["(all)"] + sorted([str(v) for v in df[focus_dim].dropna().unique().tolist()])
#                             focus_val = st.selectbox("Value", vals, index=0)
#                             if focus_val == "(all)":
#                                 focus_val = None

#                     sdf = df.copy()
#                     if focus_dim and focus_dim != "(none)" and focus_val:
#                         sdf = sdf[sdf[focus_dim].astype(str) == focus_val]

#                     # 2) Build a DatetimeIndex key from time_col (handle many formats)
#                     #    Accepts "Jan 2023", "2023-01-01", "2023-01", etc.
#                     _raw = sdf[time_col].astype(str)
#                     # First attempt: strict Month Year like "Jan 2023"
#                     _mkey = pd.to_datetime(_raw, format="%b %Y", errors="coerce")
#                     # Fallback: try plain to_datetime (will parse ISO, %Y-%m, etc.)
#                     mask = _mkey.isna()
#                     if mask.any():
#                         _mkey.loc[mask] = pd.to_datetime(_raw[mask], errors="coerce")

#                     sdf = sdf.assign(_mkey=_mkey)
#                     # Diagnostics
#                     st.caption(f"Parsed {sdf['_mkey'].notna().sum()} rows into valid months; "
#                             f"{sdf['_mkey'].isna().sum()} rows failed parsing and will be ignored.")

#                     # 3) Collapse duplicates per month (sum; switch to mean() if you prefer)
#                     ts = (
#                         sdf.dropna(subset=["_mkey"])
#                         .groupby("_mkey")[measure]
#                         .sum(min_count=1)
#                         .astype(float)
#                         .sort_index()
#                     )

#                     if ts.empty:
#                         st.warning("No time series points after filtering/aggregation.")
#                         with st.expander("See sample of filtered data"):
#                             st.dataframe(sdf.head(20))
#                     else:
#                         # 4) Normalize index to month start — NO 'MS' with Period
#                         ts.index = ts.index.to_period("M").to_timestamp(how="start")
#                         # paranoia: collapse remaining dups after normalization
#                         ts = ts.groupby(level=0).sum(min_count=1).sort_index()

#                         # 5) Create complete monthly range (DatetimeIndex with freq='MS')
#                         start = ts.index.min().replace(day=1)
#                         end   = ts.index.max().replace(day=1)
#                         full_idx = pd.date_range(start, end, freq="MS")
#                         ts = ts.reindex(full_idx)

#                         # 6) Plot base series + rolling mean
#                         win = st.slider("Rolling mean window (months)", 1, 12, 3, help="Set ≥2 to draw")
#                         ts_df = ts.reset_index()
#                         ts_df.columns = ["month_date", measure]

#                         fig_ts = px.line(ts_df, x="month_date", y=measure, markers=True, title="Time series")
#                         if win >= 2:
#                             roll = ts.rolling(win, min_periods=win).mean().reset_index()
#                             roll.columns = ["month_date", "rolling_mean"]
#                             fig_ts.add_scatter(x=roll["month_date"], y=roll["rolling_mean"],
#                                             mode="lines", name=f"Rolling mean ({win})")
#                         fig_ts.update_xaxes(tickformat="%b %Y")
#                         st.plotly_chart(fig_ts, use_container_width=True)

#                         # 7) ACF (simple)
#                         st.markdown("**Autocorrelation (ACF)**")
#                         max_lag = st.slider("Max lag", 1, 18, 12)
#                         base = ts - ts.mean()
#                         denom = float((base**2).sum(skipna=True)) or 0.0
#                         acf_vals = []
#                         for lag in range(1, max_lag+1):
#                             num = (base.shift(lag) * base).dropna().sum()
#                             acf_vals.append(float(num) / denom if denom else 0.0)
#                         acf_df = pd.DataFrame({"lag": list(range(1, max_lag+1)), "acf": acf_vals})
#                         fig_acf = px.bar(acf_df, x="lag", y="acf", title="ACF (naive)")
#                         st.plotly_chart(fig_acf, use_container_width=True)

#                         # 8) Seasonal-naive forecast (local quick look)
#                         st.markdown("**Seasonal-naive forecast**")
#                         horizon = st.slider("Horizon (months)", 1, 6, 3)
#                         future_idx = pd.date_range(ts.index.max() + pd.offsets.MonthBegin(1),
#                                                 periods=horizon, freq="MS")
#                         if len(ts.dropna()) >= 12:
#                             fcast = []
#                             for fi in future_idx:
#                                 src = fi - pd.DateOffset(years=1)
#                                 val = ts.get(src, default=np.nan)
#                                 if pd.isna(val):
#                                     val = ts.iloc[-1]
#                                 fcast.append(float(val))
#                         else:
#                             last_val = float(ts.dropna().iloc[-1])
#                             fcast = [last_val]*horizon

#                         fc_df = pd.DataFrame({"month_date": future_idx, "forecast": fcast})
#                         fig_fc = px.line(fc_df, x="month_date", y="forecast", markers=True,
#                                         title="Seasonal-naive forecast")
#                         fig_fc.update_xaxes(tickformat="%b %Y")
#                         st.plotly_chart(fig_fc, use_container_width=True)
#                         st.dataframe(fc_df.assign(month=lambda x: x["month_date"].dt.strftime("%b %Y"))
#                                         .drop(columns=["month_date"]))

#                        # 9) (Server) Model-based forecast (ARIMA / SARIMA / Prophet via FastAPI)
#                         st.divider()
#                         st.markdown("**Model-based forecast (server)**")

#                         col1, col2, col3 = st.columns([2,1,1])
#                         with col1:
#                             model_choice = st.selectbox("Model", ["SARIMA","ARIMA","Prophet"], index=0)
#                         with col2:
#                             h = st.number_input("Horizon (months)", 1, 36, 6)
#                         do_srv = st.button("Run server forecast")

#                         if do_srv:
#                             try:
#                                 with st.spinner("Calling server /forecast..."):
#                                     fdf = run_server_forecast(API, ts, model_choice, int(h))

#                                 # Decide x-axis
#                                 use_month_labels = "month" in fdf.columns
#                                 xcol = "month" if use_month_labels else ("step" if "step" in fdf.columns else fdf.columns[0])

#                                 # Plot forecast; handle optional intervals
#                                 import plotly.graph_objects as go
#                                 fig = go.Figure()
#                                 # Underlay: last 24 months of history for context (if available)
#                                 hist_df = ts.dropna().reset_index()
#                                 hist_df.columns = ["month_date", "value"]
#                                 if not hist_df.empty:
#                                     # Show last up to 24 points for readability
#                                     hist_df = hist_df.tail(24)
#                                     fig.add_trace(go.Scatter(
#                                         x=hist_df["month_date"], y=hist_df["value"],
#                                         mode="lines+markers", name="History"
#                                     ))

#                                 # Forecast mean
#                                 fig.add_trace(go.Scatter(
#                                     x=fdf[xcol], y=fdf.get("yhat", fdf.iloc[:, -1]),
#                                     mode="lines+markers", name=f"{model_choice} forecast"
#                                 ))

#                                 # Optional intervals
#                                 if "yhat_lo" in fdf.columns and "yhat_hi" in fdf.columns:
#                                     fig.add_trace(go.Scatter(
#                                         x=fdf[xcol], y=fdf["yhat_lo"],
#                                         mode="lines", name="Lower", line=dict(dash="dot")
#                                     ))
#                                     fig.add_trace(go.Scatter(
#                                         x=fdf[xcol], y=fdf["yhat_hi"],
#                                         mode="lines", name="Upper", line=dict(dash="dot")
#                                     ))

#                                 fig.update_layout(
#                                     title=f"{model_choice} forecast (server)",
#                                     xaxis_title="Month" if use_month_labels else "Step",
#                                     yaxis_title="Value",
#                                     hovermode="x unified"
#                                 )
#                                 if use_month_labels:
#                                     fig.update_xaxes(type="category")  # keep forecast months in given order
#                                 else:
#                                     fig.update_xaxes(dtick=1)

#                                 st.plotly_chart(fig, use_container_width=True)
#                                 st.dataframe(fdf)

#                             except Exception as ex:
#                                 st.error(str(ex))


#             # Tiny debug readout
#             with st.expander("🔎 Time Series debug"):
#                 st.write("Detected time column:", time_col)
#                 st.write("Rows in df:", len(df))
#                 if not df.empty:
#                     st.write("Numeric columns:", num_cols if 'num_cols' in locals() else [])
#                     st.write("Example head:", df.head(5))

#     # ---- Debug Tab ----
#     with tabs[6]:
#         st.subheader("Parsed intent")
#         st.json(out.get("intent", {}))
#         st.subheader("SQL")
#         st.code(out.get("sql"), language="sql")
#         st.subheader("Resolved meta")
#         win = meta.get("window") or {}
#         st.write("**Measure:**", meta.get("measure"))
#         st.write("**Dims:**", meta.get("dims"))
#         st.write("**Filters:**", meta.get("filters"))
#         st.write("**Mode:**", meta.get("mode"))
#         st.write("**Chart hint:**", meta.get("chart_type"))
#         st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")
#         if "month_current" in meta or "month_previous" in meta:
#             st.write("**MoM Anchor:**", meta.get("anchor"))
#             cur = meta.get("month_current", {})
#             prv = meta.get("month_previous", {})
#             st.write("• Current month:", f"{cur.get('start')} → {cur.get('end')}")
#             st.write("• Previous month:", f"{prv.get('start')} → {prv.get('end')}")
#         dbg = meta.get("debug") or {}
#         if isinstance(dbg, dict) and "prev_window" in dbg:
#             pw = dbg["prev_window"]
#             st.write("**YoY previous window:**", f"{pw.get('start')} → {pw.get('end')}")
#         st.json(meta, expanded=False)
# else:
#     st.caption("Tip: upload an Excel, type a query, toggle Forecast/Signals if needed, and click Ask.")


























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

import random
def run_server_forecast(API_BASE: str, ts: pd.Series, model: str, horizon: int):
    """
    Send a monthly-start DatetimeIndex series to FastAPI /forecast and return a DataFrame.
    ts must already be normalized to a monthly DatetimeIndex (freq='MS') with numeric values.
    """
    # drop NaNs; backend can interpolate/missings but cleaner to send non-nulls
    ser = ts.dropna()
    if ser.empty:
        raise ValueError("No non-null points to send for forecasting.")

    payload = {
        "model": model,            # "ARIMA" | "SARIMA" | "Prophet"
        "horizon": int(horizon),
        "series": [
            {"date": d.strftime("%Y-%m-%d"), "value": float(v)}
            for d, v in ser.items()
        ],
        "measure": None,
        "filters": {}
    }

    r = requests.post(f"{API_BASE}/forecast", json=payload, timeout=120)
    if not r.ok:
        # surface FastAPI error cleanly
        try:
            err = r.json().get("detail", r.text)
        except Exception:
            err = r.text
        raise RuntimeError(f"Server forecast failed: {err}")

    out = r.json() or {}
    fcst = out.get("fcst") or []
    if not fcst:
        raise RuntimeError("Server returned no forecast points.")

    # The backend returns [{"month":"Jan 2026","yhat":..., "yhat_lo":..., "yhat_hi":...}, ...]
    fdf = pd.DataFrame(fcst)

    # Normalize columns for plotting
    # Prefer datetime x if you want: we can reconstruct from last observed + horizon
    if "month" in fdf.columns:
        # keep month labels for category x-axis
        x = fdf["month"]
    else:
        # fallback: make a simple 1..H horizon index
        x = list(range(1, len(fdf) + 1))
        fdf.insert(0, "step", x)

    return fdf


def derive_insights_from_table(df: pd.DataFrame, meta: dict) -> list[str]:
    """
    Works for:
      • Top-N (bar) tables like: [brand, value_sales] or [brand, unit_sales]
      • YoY bar tables like: [brand, value_sales_curr, value_sales_prev, value_yoy]
      • Simple totals (no dims)
      • Trend tables with date/month (falls back to simple delta)
    Returns a short list of natural-language bullets.
    """
    if df is None or df.empty:
        return []

    tips: list[str] = []
    m = (meta or {}).get("measure") or ""
    cols = list(df.columns)
    colset = set(cols)

    # pick primary numeric column
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    prefer_order = []
    prefer_order += [c for c in ["value_sales_curr", "unit_sales_curr"] if c in colset]
    prefer_order += [c for c in ["value_sales", "unit_sales"] if c in colset]
    if m and m in colset and m not in prefer_order:
        prefer_order.insert(0, m)
    primary = next((c for c in prefer_order if c in colset), None) or (numeric_cols[0] if numeric_cols else None)
    if primary is None:
        return tips

    # category axis guess
    cat_candidates = [c for c in ["brand","category","market","channel","segment","manufacturer"] if c in colset]
    if not cat_candidates:
        cat_candidates = [c for c in cols if (c not in ("date","month","month_year")) and not pd.api.types.is_numeric_dtype(df[c])]
    xcat = cat_candidates[0] if cat_candidates else None

    # BAR / TOP-N INSIGHTS
    if xcat:
        sub = df[[xcat, primary]].dropna()
        if sub[xcat].duplicated().any():
            sub = sub.groupby(xcat, dropna=False)[primary].sum().reset_index()

        if not sub.empty:
            sub = sub.sort_values(primary, ascending=False)
            leader_row = sub.iloc[0]
            leader, lead_val = leader_row[xcat], float(leader_row[primary])

            tips.append(f"{xcat.title()} “{leader}” leads on {primary.replace('_',' ')} ({lead_val:,.0f}).")

            if len(sub) >= 2:
                runner_row = sub.iloc[1]
                runner, run_val = runner_row[xcat], float(runner_row[primary])
                gap = lead_val - run_val
                gap_pc = gap / (run_val + 1e-9)
                tips.append(f"Lead over #{2} “{runner}” is {gap:,.0f} ({gap_pc:+.0%}).")

            total = float(sub[primary].sum())
            if total > 0:
                top_share = lead_val / total
                tips.append(f"Top item holds {top_share:.0%} of the shown total.")

            share = sub[primary] / max(total, 1e-9)
            hhi = float((share ** 2).sum())
            if hhi >= 0.20:
                tips.append("Market looks concentrated among a few items.")
            elif hhi <= 0.10:
                tips.append("Market looks fairly fragmented.")

        yoy_col = next((c for c in cols if c.endswith("_yoy")), None)
        if yoy_col:
            yy = df[[xcat, yoy_col]].dropna()
            if not yy.empty and pd.api.types.is_numeric_dtype(yy[yoy_col]):
                yy = yy.sort_values(yoy_col, ascending=False)
                best = yy.iloc[0]
                tips.append(f"Best {yoy_col.replace('_',' ')}: “{best[xcat]}” at {float(best[yoy_col]):+.1%}.")
        return tips

    # Trend fallback
    time_col = "month" if "month" in colset else ("date" if "date" in colset else None)
    if time_col and pd.api.types.is_numeric_dtype(df[primary]):
        try:
            t = pd.to_datetime(df[time_col], errors="coerce")
            s = df.loc[t.notna()].sort_values(t.name)[primary]
            if len(s) >= 2:
                first, last = float(s.iloc[0]), float(s.iloc[-1])
                delta = (last - first) / (abs(first) + 1e-9)
                tips.append(f"{primary.replace('_',' ')} changed {delta:+.1%} across the period.")
        except Exception:
            pass

    if not tips:
        tips.append("No obvious spikes or gaps; values look stable.")
    return tips


def _preferred_measure_for_line(df: pd.DataFrame) -> str | None:
    for c in ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]:
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            return c
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_prev", "_curr")):
            return c
    return None

def _month_category_order(df: pd.DataFrame) -> list[str]:
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
    priority = ["value_sales", "unit_sales", "share", "value_yoy", "unit_yoy", "share_yoy"]
    y = [c for c in priority if c in df.columns]
    if not y:
        y = [c for c in _numeric_cols(df) if not c.endswith("_prev") and not c.endswith("_curr")]
    return y[:6]

def _find_x_cat(df: pd.DataFrame):
    for c in CAT_CANDIDATES:
        if c in df.columns:
            return c
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
            df["date_label"] = df["date"].dt.strftime("%b %Y")
            return df
        except Exception:
            return df
    return df

def render_chart(df: pd.DataFrame, meta: dict):
    chart_type = (meta or {}).get("chart_type")
    measure_hint = (meta or {}).get("measure")

    # add month label if only date present
    if "date" in df.columns and "month" not in df.columns:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.strftime("%b %Y")

    if "month" in df.columns and "_month_key" not in df.columns:
        df = df.copy()
        try:
            df["_month_key"] = pd.to_datetime(df["month"], format="%b %Y")
        except Exception:
            df["_month_key"] = pd.to_datetime("01 " + df["month"], errors="coerce")

    def _pick_y_for_yoy(_df: pd.DataFrame, _measure_hint: str):
        if _measure_hint == "value_yoy" and "value_sales_curr" in _df.columns:
            return ["value_sales_curr"]
        if _measure_hint == "unit_yoy" and "unit_sales_curr" in _df.columns:
            return ["unit_sales_curr"]
        fallback = [c for c in _df.columns if c.endswith("_curr") and pd.api.types.is_numeric_dtype(_df[c])]
        return fallback[:1] if fallback else []

    # Explicit BAR
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

    # Fallback Trend
    if ("month" in df.columns) or ("date" in df.columns):
        xcol = "month" if "month" in df.columns else "date"
        ycols = _find_y_cols(df)
        if ycols:
            sort_col = "_month_key" if xcol == "month" and "_month_key" in df.columns else xcol
            sdf = df.sort_values(sort_col)
            # choose a color/grouping if available
            color_col = None
            for cand in ["brand", "category", "market", "channel", "segment", "manufacturer"]:
                if cand in df.columns:
                    color_col = cand
                    break
            fig = px.line(sdf, x=xcol, y=ycols, color=color_col, markers=True, title="Trend over time")
            if xcol == "month":
                ordered = (
                    sdf.dropna(subset=[sort_col])
                       .drop_duplicates(subset=["month"])
                       .sort_values(sort_col)["month"]
                       .tolist()
                )
                fig.update_xaxes(type="category", categoryorder="array", categoryarray=ordered)
            else:
                fig.update_xaxes(tickformat="%b %Y")
            _format_percent_axes(fig, ycols)
            st.plotly_chart(fig, use_container_width=True)
            return

    # If we reach here, fallback bar if possible
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
        return

    st.info("No chart rendered (not enough columns to infer a chart).")


# ---------------- Section: Ask ----------------
st.header("2) Ask a question")

# New controls (we pass these to backend)
c1, c2, c3 = st.columns([3,1,1])
with c1:
    q = st.text_input(
        'Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart',
        "",
    )
with c2:
    do_fc = st.toggle("Forecast", value=False, help="Ask backend to include 1–3 month forecast in response")
with c3:
    show_sig = st.toggle("Signals", value=True, help="Ask backend to include anomaly/share-jump signals")

if st.button("Ask", type="primary"):
    payload = {"question": q, "forecast": do_fc, "signals": show_sig}
    resp = requests.post(f"{API}/ask", json=payload)
    if not resp.ok:
        st.error(resp.text)
    else:
        st.session_state["out"] = resp.json()

# ---------------- Render Tabs ----------------
out = st.session_state.get("out")
if out:
    # Parsed intent + SQL (kept for transparency; moved into Debug tab later)
    meta = out.get("meta", {}) or {}
    df = pd.DataFrame(out.get("data", []))

    # Add month label for convenience
    if "date" in df.columns.tolist():
        df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%b %Y")
        if "date" in df.columns:
            df = df.drop(columns=["date"])

    tabs = st.tabs(["Table", "Chart", "Insights", "Signals", "Forecast", "Time Series", "Debug"])

    # ---- Table Tab ----
    with tabs[0]:
        st.subheader("Result")
        if df.empty:
            st.warning("No data for this query.")
        else:
            st.dataframe(df, use_container_width=True)
            st.download_button("Download CSV", df.to_csv(index=False), "result.csv")

    # ---- Chart Tab ----
    with tabs[1]:
        if df.empty:
            st.info("No data to chart.")
        else:
            render_chart(df, meta)

    # ---- Insights Tab ----
    with tabs[2]:
        st.subheader("Rule based insights")
        try:
            if "insights" in out and out["insights"] and out["insights"].get("rule_based_bullets"):
                
                for s in out["insights"]["rule_based_bullets"]:
                    st.write(f"• {s}")
            
            
            else:
                # Fallback: derive quick tips locally
                local_bullets = derive_insights_from_table(df, meta)
                if local_bullets:
                    for s in local_bullets:
                        st.write(f"• {s}")
                else:
                    st.caption("No obvious insights for this result.")
            if isinstance(out.get("insights", {}), dict) and out["insights"].get("evidence_note"):
                st.caption(out["insights"]["evidence_note"])
            
        except Exception as e:
            st.caption(f"(Couldn’t render insights: {e})")
        #LLM based insights
        st.subheader("LLM based insights")
        try:
            if "insights" in out and out["insights"] and out["insights"].get("llm_based_bullets"):
                
                for s in out["insights"]["llm_based_bullets"]:
                    st.write(f"• {s}")
            
            
            else:
                # Fallback: derive quick tips locally
                local_bullets = derive_insights_from_table(df, meta)
                if local_bullets:
                    for s in local_bullets:
                        st.write(f"• {s}")
                else:
                    st.caption("No obvious insights for this result.")
            if isinstance(out.get("insights", {}), dict) and out["insights"].get("evidence_note"):
                st.caption(out["insights"]["evidence_note"])
            
        except Exception as e:
            st.caption(f"(Couldn’t render insights: {e})")


    # ---- Signals Tab ----
    with tabs[3]:
        st.subheader("Signals (anomalies, share jumps)")
        events = out.get("events", [])
        if events:
            for ev in events:
                st.info(f"{ev.get('date')}: {ev.get('event_type')} (strength: {ev.get('strength')}) — {ev.get('details')}")
        else:
            st.caption("No signals provided (enable 'Signals' or implement server-side events).")

    # ---- Forecast Tab (server-provided) ----
    with tabs[4]:
        st.subheader("Short-horizon forecast")
        fc = out.get("forecast")
        if fc and isinstance(fc, dict) and fc.get("figure"):
            # If backend sends Plotly JSON
            st.plotly_chart(fc["figure"], use_container_width=True)
            if "backtest_mape" in fc:
                st.caption(f"Backtest MAPE ~ {fc['backtest_mape']:.1%}")
        else:
            st.caption("No forecast in response. Toggle 'Forecast' above or implement forecast in /ask.")

    # ---- Time Series Tab (local analysis + simple seasonal-naive forecast) ----
    # ---- Time Series Tab (robust) ----
    with tabs[5]:
        st.subheader("Time Series Analysis")

        if df.empty:
            st.info("Run a query that returns a monthly time series to analyze.")
        else:
            # 0) Detect a usable time column (be generous with names)
            time_candidates = [
                c for c in df.columns
                if str(c).lower() in ("month","month_year","monthdate","month_date","date","period")
            ]
            time_col = time_candidates[0] if time_candidates else None

            if not time_col:
                st.warning("No time column found. Expecting one of: month / month_year / month_date / date.")
                st.write("Columns I see:", list(df.columns))
            else:
                # 1) Choose a numeric measure; fallback to first numeric col
                num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                if not num_cols:
                    st.warning("No numeric measure available in the result to analyze.")
                    st.write("Columns I see:", list(df.columns))
                else:
                    c1, c2, c3 = st.columns([2,2,2])
                    with c1:
                        measure = st.selectbox("Measure", num_cols, index=0)
                    # Optional dimension focus (if multiple series exist)
                    cat_cols = [c for c in df.columns if c not in [time_col] + num_cols]
                    with c2:
                        focus_dim = st.selectbox("Optional dimension", ["(none)"] + cat_cols, index=0)
                    with c3:
                        focus_val = None
                        if focus_dim and focus_dim != "(none)":
                            vals = ["(all)"] + sorted([str(v) for v in df[focus_dim].dropna().unique().tolist()])
                            focus_val = st.selectbox("Value", vals, index=0)
                            if focus_val == "(all)":
                                focus_val = None

                    sdf = df.copy()
                    if focus_dim and focus_dim != "(none)" and focus_val:
                        sdf = sdf[sdf[focus_dim].astype(str) == focus_val]

                    # 2) Build a DatetimeIndex key from time_col (handle many formats)
                    #    Accepts "Jan 2023", "2023-01-01", "2023-01", etc.
                    _raw = sdf[time_col].astype(str)
                    # First attempt: strict Month Year like "Jan 2023"
                    _mkey = pd.to_datetime(_raw, format="%b %Y", errors="coerce")
                    # Fallback: try plain to_datetime (will parse ISO, %Y-%m, etc.)
                    mask = _mkey.isna()
                    if mask.any():
                        _mkey.loc[mask] = pd.to_datetime(_raw[mask], errors="coerce")

                    sdf = sdf.assign(_mkey=_mkey)
                    # Diagnostics
                    st.caption(f"Parsed {sdf['_mkey'].notna().sum()} rows into valid months; "
                            f"{sdf['_mkey'].isna().sum()} rows failed parsing and will be ignored.")

                    # 3) Collapse duplicates per month (sum; switch to mean() if you prefer)
                    ts = (
                        sdf.dropna(subset=["_mkey"])
                        .groupby("_mkey")[measure]
                        .sum(min_count=1)
                        .astype(float)
                        .sort_index()
                    )

                    if ts.empty:
                        st.warning("No time series points after filtering/aggregation.")
                        with st.expander("See sample of filtered data"):
                            st.dataframe(sdf.head(20))
                    else:
                        # 4) Normalize index to month start — NO 'MS' with Period
                        ts.index = ts.index.to_period("M").to_timestamp(how="start")
                        # paranoia: collapse remaining dups after normalization
                        ts = ts.groupby(level=0).sum(min_count=1).sort_index()

                        # 5) Create complete monthly range (DatetimeIndex with freq='MS')
                        start = ts.index.min().replace(day=1)
                        end   = ts.index.max().replace(day=1)
                        full_idx = pd.date_range(start, end, freq="MS")
                        ts = ts.reindex(full_idx)

                        # 6) Plot base series + rolling mean
                        win = st.slider("Rolling mean window (months)", 1, 12, 3, help="Set ≥2 to draw")
                        ts_df = ts.reset_index()
                        ts_df.columns = ["month_date", measure]

                        fig_ts = px.line(ts_df, x="month_date", y=measure, markers=True, title="Time series")
                        if win >= 2:
                            roll = ts.rolling(win, min_periods=win).mean().reset_index()
                            roll.columns = ["month_date", "rolling_mean"]
                            fig_ts.add_scatter(x=roll["month_date"], y=roll["rolling_mean"],
                                            mode="lines", name=f"Rolling mean ({win})")
                        fig_ts.update_xaxes(tickformat="%b %Y")
                        st.plotly_chart(fig_ts, use_container_width=True)

                        # 7) ACF (simple)
                        st.markdown("**Autocorrelation (ACF)**")
                        max_lag = st.slider("Max lag", 1, 18, 12)
                        base = ts - ts.mean()
                        denom = float((base**2).sum(skipna=True)) or 0.0
                        acf_vals = []
                        for lag in range(1, max_lag+1):
                            num = (base.shift(lag) * base).dropna().sum()
                            acf_vals.append(float(num) / denom if denom else 0.0)
                        acf_df = pd.DataFrame({"lag": list(range(1, max_lag+1)), "acf": acf_vals})
                        fig_acf = px.bar(acf_df, x="lag", y="acf", title="ACF (naive)")
                        st.plotly_chart(fig_acf, use_container_width=True)

                        # 8) Seasonal-naive forecast (local quick look)
                        st.markdown("**Seasonal-naive forecast**")
                        horizon = st.slider("Horizon (months)", 1, 6, 3)
                        future_idx = pd.date_range(ts.index.max() + pd.offsets.MonthBegin(1),
                                                periods=horizon, freq="MS")
                        if len(ts.dropna()) >= 12:
                            fcast = []
                            for fi in future_idx:
                                src = fi - pd.DateOffset(years=1)
                                val = ts.get(src, default=np.nan)
                                if pd.isna(val):
                                    val = ts.iloc[-1]
                                fcast.append(float(val))
                        else:
                            last_val = float(ts.dropna().iloc[-1])
                            fcast = [last_val]*horizon

                        fc_df = pd.DataFrame({"month_date": future_idx, "forecast": fcast})
                        fig_fc = px.line(fc_df, x="month_date", y="forecast", markers=True,
                                        title="Seasonal-naive forecast")
                        fig_fc.update_xaxes(tickformat="%b %Y")
                        st.plotly_chart(fig_fc, use_container_width=True)
                        st.dataframe(fc_df.assign(month=lambda x: x["month_date"].dt.strftime("%b %Y"))
                                        .drop(columns=["month_date"]))

                       # 9) (Server) Model-based forecast (ARIMA / SARIMA / Prophet via FastAPI)
            #             st.divider()
            #             st.markdown("**Model-based forecast (server)**")

            #             col1, col2, col3 = st.columns([2,1,1])
            #             with col1:
            #                 model_choice = st.selectbox("Model", ["SARIMA","ARIMA","Prophet"], index=0)
            #             with col2:
            #                 h = st.number_input("Horizon (months)", 1, 36, 6)
            #             do_srv = st.button("Run server forecast")

            #             if do_srv:
            #                 try:
            #                     with st.spinner("Calling server /forecast..."):
            #                         fdf = run_server_forecast(API, ts, model_choice, int(h))

            #                     # Decide x-axis
            #                     use_month_labels = "month" in fdf.columns
            #                     xcol = "month" if use_month_labels else ("step" if "step" in fdf.columns else fdf.columns[0])

            #                     # Plot forecast; handle optional intervals
            #                     # ---------------- Build figure: history + forecast ----------------
            #                     import plotly.graph_objects as go
            #                     fig = go.Figure()

            #                     # === History (actuals) ===
            #                     hist = ts.dropna()
            #                     if not hist.empty:
            #                         # OPTIONAL: user control for how many months of history to show
            #                         total_months = len(hist)
            #                         show_all = st.toggle("Show full history", value=True, help="Turn off to limit history window")
            #                         if show_all:
            #                             hist_to_plot = hist
            #                         else:
            #                             # let user pick a window (default 24)
            #                             win = st.slider("History window (months)", 6, total_months, min(24, total_months))
            #                             hist_to_plot = hist.tail(win)
            #                         hist_to_plot = hist.copy()
            #                         hist_to_plot.index = hist_to_plot.index.to_period("M").to_timestamp(how="start")
            #                         month_labels = hist_to_plot.index.strftime("%b %Y")

            #                         fig.add_trace(go.Scatter(
            #                             x=month_labels,
            #                             y=hist_to_plot.values,
            #                             mode="lines+markers",
            #                             name="History"
            #                         ))

            #                     # Forecast mean
            #                     fig.add_trace(go.Scatter(
            #                         x=fdf[xcol], y=fdf.get("yhat", fdf.iloc[:, -1]),
            #                         mode="lines+markers", name=f"{model_choice} forecast"
            #                     ))

            #                     # Optional intervals
            #                     if "yhat_lo" in fdf.columns and "yhat_hi" in fdf.columns:
            #                         fig.add_trace(go.Scatter(
            #                             x=fdf[xcol], y=fdf["yhat_lo"],
            #                             mode="lines", name="Lower", line=dict(dash="dot")
            #                         ))
            #                         fig.add_trace(go.Scatter(
            #                             x=fdf[xcol], y=fdf["yhat_hi"],
            #                             mode="lines", name="Upper", line=dict(dash="dot")
            #                         ))

            #                     fig.update_layout(
            #                             title=f"{model_choice} forecast (server)",
            #                             xaxis_title="Month",
            #                             yaxis_title="Value",
            #                             hovermode="x unified"
            #                         )
            #                     fig.update_xaxes(tickformat="%b %Y", ticklabelmode="period")

            #                     if use_month_labels:
            #                         fig.update_xaxes(type="category")  # keep forecast months in given order
            #                     else:
            #                         fig.update_xaxes(dtick=1)

            #                     st.plotly_chart(fig, use_container_width=True)
            #                     st.dataframe(fdf)

            #                 except Exception as ex:
            #                     st.error(str(ex))

                            

                        # 9) (Server) Model-based forecast (ARIMA / SARIMA / Prophet via FastAPI)
                        st.divider()
                        st.markdown("**Model-based forecast (server)**")

                        col1, col2 = st.columns([2,1])
                        with col1:
                            model_choice = st.selectbox("Model", ["SARIMA","ARIMA","Prophet"], index=0)
                        with col2:
                            h = st.number_input("Horizon (months)", 1, 36, 6)

                        if st.button("Run server forecast"):
                            try:
                                with st.spinner("Calling server /forecast..."):
                                    fdf = run_server_forecast(API, ts, model_choice, int(h))
                                st.session_state["forecast_df"] = fdf  # ✅ Save in session_state
                                st.session_state["forecast_model"] = model_choice
                            except Exception as ex:
                                st.error(str(ex))

                        # ---------------- Show chart if forecast exists ----------------
                        if "forecast_df" in st.session_state:
                            fdf = st.session_state["forecast_df"]
                            model_choice = st.session_state.get("forecast_model", "Forecast")

                            # Parse forecast months
                            if "month" in fdf.columns:
                                x_fc = pd.to_datetime("01 " + fdf["month"].astype(str), errors="coerce")
                            elif "month_date" in fdf.columns:
                                x_fc = pd.to_datetime(fdf["month_date"], errors="coerce")
                            else:
                                last_obs = ts.dropna().index.max()
                                x_fc = pd.date_range(last_obs + pd.offsets.MonthBegin(1), periods=len(fdf), freq="MS")

                            fdf = fdf.copy()
                            fdf["x_dt"] = x_fc
                            fdf["month_label"] = fdf["x_dt"].dt.strftime("%b %Y")

                            # ---------------- History (slider) ----------------
                            hist = ts.dropna()
                            if not hist.empty:
                                total_points = len(hist)
                                win = st.slider(
                                    "History window (months)", 
                                    min_value=6, max_value=total_points, value=min(24, total_points), step=1
                                )
                                hist = hist.tail(win)

                            hist_idx = hist.index.to_period("M").to_timestamp(how="start")
                            hist_labels = hist_idx.strftime("%b %Y")

                            # ---------------- Plot ----------------
                            import plotly.graph_objects as go
                            fig = go.Figure()

                            # Actuals
                            fig.add_trace(go.Scatter(
                                x=hist_labels, y=hist.values,
                                mode="lines+markers", name="History"
                            ))

                            # Forecast mean
                            fig.add_trace(go.Scatter(
                                x=fdf["month_label"], y=fdf.get("yhat", fdf.iloc[:, -1]),
                                mode="lines+markers", name=f"{model_choice} forecast"
                            ))

                            # Forecast intervals
                            if {"yhat_lo","yhat_hi"}.issubset(fdf.columns):
                                fig.add_trace(go.Scatter(
                                    x=fdf["month_label"], y=fdf["yhat_lo"],
                                    mode="lines", name="Lower", line=dict(dash="dot")
                                ))
                                fig.add_trace(go.Scatter(
                                    x=fdf["month_label"], y=fdf["yhat_hi"],
                                    mode="lines", name="Upper", line=dict(dash="dot")
                                ))

                            fig.update_layout(
                                title=f"{model_choice} forecast (server)",
                                xaxis_title="Month", yaxis_title="Value",
                                hovermode="x unified"
                            )
                            fig.update_xaxes(type="category")

                            st.plotly_chart(fig, use_container_width=True)

                            # Forecast table
                            cols = ["month_label","yhat"]
                            if "yhat_lo" in fdf.columns and "yhat_hi" in fdf.columns:
                                cols += ["yhat_lo","yhat_hi"]
                            st.dataframe(fdf[cols])
                            st.download_button("Download forecast CSV", fdf.to_csv(index=False), "forecast.csv")    

# Forecast
            # Tiny debug readout
            with st.expander("🔎 Time Series debug"):
                st.write("Detected time column:", time_col)
                st.write("Rows in df:", len(df))
                if not df.empty:
                    st.write("Numeric columns:", num_cols if 'num_cols' in locals() else [])
                    st.write("Example head:", df.head(5))

            # 9) (Server) Model-based forecast (ARIMA / SARIMA / Prophet via FastAPI)



    # ---- Debug Tab ----
    with tabs[6]:
        st.subheader("Parsed intent")
        st.json(out.get("intent", {}))
        st.subheader("SQL")
        st.code(out.get("sql"), language="sql")
        st.subheader("Resolved meta")
        win = meta.get("window") or {}
        st.write("**Measure:**", meta.get("measure"))
        st.write("**Dims:**", meta.get("dims"))
        st.write("**Filters:**", meta.get("filters"))
        st.write("**Mode:**", meta.get("mode"))
        st.write("**Chart hint:**", meta.get("chart_type"))
        st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")
        if "month_current" in meta or "month_previous" in meta:
            st.write("**MoM Anchor:**", meta.get("anchor"))
            cur = meta.get("month_current", {})
            prv = meta.get("month_previous", {})
            st.write("• Current month:", f"{cur.get('start')} → {cur.get('end')}")
            st.write("• Previous month:", f"{prv.get('start')} → {prv.get('end')}")
        dbg = meta.get("debug") or {}
        if isinstance(dbg, dict) and "prev_window" in dbg:
            pw = dbg["prev_window"]
            st.write("**YoY previous window:**", f"{pw.get('start')} → {pw.get('end')}")
        st.json(meta, expanded=False)
else:
    st.caption("Tip: upload an Excel, type a query, toggle Forecast/Signals if needed, and click Ask.")
