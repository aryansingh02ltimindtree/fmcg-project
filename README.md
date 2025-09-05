# Nielsen Excel Q&A Chatbot — Starter Repo

This is a minimal **FastAPI + Streamlit + DuckDB** starter that lets you:
- Upload Nielsen-like Excel
- Ask natural-language questions
- Get a table/chart + 3 bullet insights
- See the generated SQL (for trust & debugging)

## Quickstart

### 0) Create & activate a virtual environment (optional but recommended)
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 1) Install dependencies
```bash
pip install -r requirements.txt
```

### 2) Start the backend (FastAPI)
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open docs at: http://localhost:8000/docs

### 3) Start the frontend (Streamlit)
In a new terminal:
```bash
streamlit run frontend/app.py
```

Frontend will open in your browser.

---

## What’s inside

```
backend/
  main.py                 # FastAPI: /upload, /ask, /sql
  sql/runner.py           # DuckDB connection & safe SQL run
  nlp/intent_schema.py    # JSON schema for parser output
  nlp/parser.py           # Tiny rule-based NL -> intent -> SQL
  ingest/excel_ingest.py  # Excel -> tidy parquet + DuckDB table
  ingest/validators.py    # Basic schema & sanity checks
  data/                   # DuckDB DB and parquet stored here

frontend/
  app.py                  # Streamlit UI

configs/
  settings.yaml           # App config (paths, limits)

data/
  sample_nielsen.xlsx     # 24 months of tiny sample data
  mapper_config.example.json
```

## Notes
- **Security**: This is a demo. SQL is whitelisted to a single table; still, don’t expose publicly as-is.
- **Accuracy**: NL→SQL is heuristic. Add more examples or plug a stronger LLM later.
- **Scaling**: For larger data, move to Postgres; use async queries & caching.

Enjoy! 🚀
