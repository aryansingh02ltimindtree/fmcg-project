import json

def strip_for_llm(stats: dict) -> dict:
    """
    Remove text-like fields (like 'insights') so the LLM only sees numbers/labels.
    """
    clean = json.loads(json.dumps(stats))  # deep copy
    clean.pop("insights", None)
    return clean

def fallback_bullets(stats: dict) -> list[str]:
    """
    Very simple backup if LLM fails.
    """
    if "mat_compare" in stats and isinstance(stats["mat_compare"].get("periods"), list):
        periods = stats["mat_compare"]["periods"]
        if periods:
            top = max(periods, key=lambda x: x.get("value_sales", 0))
            return [f"{top.get('mat_label','MAT')} leads with value sales {top.get('value_sales',0):,.0f}."]
    bar_items = (stats.get("bar") or {}).get("items") or []
    if bar_items:
        top = bar_items[0]
        label = top.get("label")
        val = top.get("value", 0)
        m = stats.get("measure", "value_sales").replace("_", " ")
        return [f"Top: {label} with {m} {val:,.0f}."]
    return ["Data steady; no standout changes detected."]
