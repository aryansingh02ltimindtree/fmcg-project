
# frontend/app.py  (Version 2 with Debug box)
import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

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
        st.subheader("Result")
        if df.empty:
            st.warning("No data for this query.")
        else:
            st.dataframe(df, use_container_width=True)

            # quick MoM sanity hint (optional)
            if "mom" in q.lower() and not any(c.endswith("_mom") for c in df.columns):
                st.info("Query mentions MoM, but no `*_mom` column returned. "
                        "Ensure your question includes a measure (value/unit) and MoM.")

            # try a line chart if a date column exists
            if "date" in df.columns and df["date"].notna().any():
                try:
                    ycols = [
                        c for c in df.columns
                        if c in ("value_sales", "unit_sales", "share", "value_yoy", "share_yoy")
                        or c.endswith("_yoy")
                    ]
                    if ycols:
                        fig = px.line(df, x="date", y=ycols, markers=True, title="Trend")
                        st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.info(f"Chart note: {e}")

        # ---------- key insights ----------
        st.subheader("Key insights")
        for b in out.get("insights", []):
            st.write(f"• {b}")

        # ---------- 🔎 Debug box ----------
        meta = out.get("meta", {})
        with st.expander("🔎 Debug (resolved context)"):
            st.write("**Measure:**", meta.get("measure"))
            st.write("**Dims:**", meta.get("dims"))
            st.write("**Filters:**", meta.get("filters"))
            st.write("**Mode:**", meta.get("mode"))

            win = meta.get("window") or {}
            st.write("**Window:**", f"{win.get('start')} → {win.get('end')}")

            # MoM-specific anchor and months (shown only when present)
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

            # raw meta (collapsed)
            st.json(meta, expanded=False)
