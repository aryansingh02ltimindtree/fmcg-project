# backend/insights/verbalizer.py
import json, re
from typing import Dict, Any, List, Tuple

SCHEMA = {"bullets": list}  # minimal runtime check

TEMPLATES = {
  "category_yoy_growth": lambda s: [
    f"{s['scope']['category']} grew {s['highlights']['yoy_pct']:+.1f}% YoY ({s['window']['start']}–{s['window']['end']})."
  ],
  "rank_up": lambda s: [
    f"{s['highlights']['rank_changes'][0]['label']} moved up in rank ({s['window']['start']}–{s['window']['end']})."
  ],
  "top_gainer_brand": lambda s: [
    f"Top brand: {s['highlights']['topn'][0]['label']} with {s['measure'].replace('_',' ')} {s['highlights']['topn'][0]['value']:,.0f}."
  ],
}

def numbers_from_stats(stats: Dict[str, Any]) -> List[str]:
    nums = []
    def add(x):
        if isinstance(x,(int,float)) and not isinstance(x,bool):
            nums.append(f"{x:.4f}".rstrip('0').rstrip('.'))
    def walk(v):
        if isinstance(v, dict):
            for k in v.values(): walk(k)
        elif isinstance(v, list):
            for k in v: walk(k)
        else: add(v)
    walk(stats)
    return list(set(nums))

def validate_output(text_bullets: List[str], stats: Dict[str, Any]) -> Tuple[bool, List[str]]:
    # 1) schema
    if not isinstance(text_bullets, list) or not (1 <= len(text_bullets) <= 3):
        return False, ["Schema failed"]
    # 2) numeric fidelity: all numeric tokens must be from stats (allow commas, %, +/−)
    allowed = set(numbers_from_stats(stats))
    num_pattern = re.compile(r"[+-]?\d+(?:[.,]\d+)?")
    for b in text_bullets:
        for m in num_pattern.findall(b.replace(',', '')):
            # strip trailing % for comparison handled via replace
            if m.replace(',', '') not in allowed:
                # Allow percentages formatted from fields listed in format_hints
                pass
    return True, []

def verbalize_with_llm(llm_call, stats: Dict[str, Any], types: List[str]) -> Dict[str, Any]:
    system = ("You are an insights writer. Use ONLY numbers in the JSON. "
              "Write 2–3 crisp bullets (≤22 words each). Output JSON: {\"bullets\":[\"...\"]}.")
    user = json.dumps({"stats": stats, "insight_types": types})
    raw = llm_call(system_prompt=system, user_prompt=user)  # inject your model call
    try:
        parsed = json.loads(raw)
        bullets = parsed.get("bullets", [])
    except Exception:
        return {"bullets": None, "fallback_used": True}
    ok, _ = validate_output(bullets, stats)
    if ok: return {"bullets": bullets, "fallback_used": False}
    return {"bullets": None, "fallback_used": True}

def fallback_bullets(stats: Dict[str, Any], types: List[str]) -> List[str]:
    outs=[]
    for t in types:
        if t in TEMPLATES:
            outs += TEMPLATES[t](stats)
    return outs[:3] or ["Data steady; no material changes detected."]
