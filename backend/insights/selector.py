# backend/insights/selector.py
from typing import Dict, Any, List

def select_insight_types(stats: Dict[str, Any]) -> List[str]:
    """
    Returns e.g.: ["top_gainer_brand", "category_yoy_growth", "rank_up"]
    Priority rules: strong |yoy| > big rank move > big share delta > top/bottom.
    """
    types = []
    # simple thresholds; tune later
    if abs(stats["highlights"].get("yoy_pct", 0)) >= 3:
        types.append("category_yoy_growth")
    if stats["highlights"].get("rank_changes"):
        types.append("rank_up")
    if stats["highlights"].get("topn"):
        types.append("top_gainer_brand")
    return types[:3]
