from fastapi import APIRouter, HTTPException, Request, Body
from typing import Any, Dict
import json

# from backend.llm.gemini import llm_insights_from_stats

router = APIRouter()

def _strip_for_llm(stats: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(stats))  # deep copy
    out.pop("insights", None)            # avoid confusing the model
    return out

def _fallback_bullets(stats: Dict[str, Any]) -> list[str]:
    # simple safe fallback
    if (stats.get("mode","").upper().startswith("MAT")
        and isinstance(stats.get("mat_compare",{}).get("periods"), list)
        and stats["mat_compare"]["periods"]):
        top = max(stats["mat_compare"]["periods"], key=lambda x: x.get("value_sales", 0))
        return [f"{top.get('mat_label','MAT')} leads with value sales {top.get('value_sales',0):,.0f}."]
    bar = (stats.get("bar") or {}).get("items") or []
    if bar:
        top = bar[0]
        ykey = stats.get("measure","value_sales").replace("_"," ")
        return [f"Top: {top.get('label')} with {ykey} {top.get('value',0):,.0f}."]
    return ["Data steady; no standout changes detected."]

@router.post("/ask")
async def ask_question(request: Request, body: Dict[str, Any] = Body(...)):
    df = request.app.state.df
    if df is None:
        raise HTTPException(400, "No data uploaded. Call /upload first.")

    intent = body.get("intent") or {}
    if not intent and body.get("question"):
        ql = body["question"].lower()
        intent = {
            "task":"topn","top_n":2,"dims":["brand"],
            "measure":"unit_sales" if "unit" in ql else "value_sales",
            "filters":{"category":"biscuits" if "biscuits" in ql else None,
                       "market":"india" if "india" in ql else None},
            "time_range":{"mode":"YTD" if "ytd" in ql else ("MAT" if "mat" in ql else "ALL")},
            "is_yoy":("yoy" in ql),
        }
    if not intent:
        raise HTTPException(422, "Provide 'intent' or 'question' in body.")

    # Your existing payload builder exposed from main.py via app.state
    build_payload = request.app.state.build_llm_payload_json
    if not build_payload:
        raise HTTPException(500, "build_llm_payload_json not attached to app.state")

    stats = build_payload(df, intent)
    clean_stats = _strip_for_llm(stats)

    bullets = llm_insights_from_stats(clean_stats)
    if not bullets:
        return {"stats": stats, "bullets": _fallback_bullets(clean_stats), "engine": "fallback"}

    return {"stats": stats, "bullets": bullets, "engine": "gemini"}
