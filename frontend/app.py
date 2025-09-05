# import streamlit as st
# import requests
# import pandas as pd
# import plotly.express as px

# st.set_page_config(page_title="Nielsen Excel Q&A", layout="wide")

# API = st.secrets.get("API_URL", "http://localhost:8000")

# st.title("📊 Nielsen Excel Q&A — Starter")

# with st.sidebar:
#     st.header("1) Upload Nielsen Excel")
#     file = st.file_uploader("Upload .xlsx", type=["xlsx"])
#     if st.button("Upload", type="primary") and file:
#         files = {"file": (file.name, file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
#         resp = requests.post(f"{API}/upload", files=files)
#         if resp.ok:
#             st.success(resp.json())
#         else:
#             st.error(resp.text)

# st.header("2) Ask a question")
# q = st.text_input('Try: Top 5 brands by YoY in category:"Biscuits" market:"India" last 12 months; show chart', "")
# if st.button("Ask", type="primary"):
#     resp = requests.post(f"{API}/ask", json={"question": q})
#     if not resp.ok:
#         st.error(resp.text)
#     else:
#         out = resp.json()
#         st.subheader("Parsed intent")
#         st.json(out["intent"])
#         st.subheader("SQL")
#         st.code(out["sql"], language="sql")
#         df = pd.DataFrame(out["data"])
#         if len(df) == 0:
#             st.warning("No data for this query.")
#         else:
#             st.subheader("Result")
#             st.dataframe(df, use_container_width=True)
#             # charts
#             if "date" in df.columns and df["date"].notna().any():
#                 try:
#                     # try line chart over time if date present
#                     xcol = "date"
#                     ycol = [c for c in df.columns if c in ("value_sales","unit_sales","share","value_yoy","share_yoy")]
#                     if ycol:
#                         fig = px.line(df, x=xcol, y=ycol, markers=True, title="Trend")
#                         st.plotly_chart(fig, use_container_width=True)
#                 except Exception as e:
#                     st.info(f"Chart note: {e}")
#             # insights
#             st.subheader("Key insights")
#             for b in out.get("insights", []):
#                 st.write(f"• {b}")


'''Version 2 of the code '''

import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Nielsen Excel Q&A", layout="wide")

# ✅ No secrets file needed
API = os.getenv("API_URL", "http://localhost:8000")

st.title("📊 Nielsen Excel Q&A — Starter")

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
        st.subheader("Parsed intent")
        st.json(out["intent"])
        st.subheader("SQL")
        st.code(out["sql"], language="sql")
        df = pd.DataFrame(out["data"])
        if len(df) == 0:
            st.warning("No data for this query.")
        else:
            st.subheader("Result")
            st.dataframe(df, use_container_width=True)

            # Try a line chart if a date column exists
            if "date" in df.columns and df["date"].notna().any():
                try:
                    ycols = [
                        c
                        for c in df.columns
                        if c in ("value_sales", "unit_sales", "share", "value_yoy", "share_yoy")
                    ]
                    if ycols:
                        fig = px.line(df, x="date", y=ycols, markers=True, title="Trend")
                        st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.info(f"Chart note: {e}")

            st.subheader("Key insights")
            for b in out.get("insights", []):
                st.write(f"• {b}")
