# backend/insights/stats_engine.py
from typing import Dict, Any, List
import pandas as pd

def build_stats(df: pd.DataFrame, intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a compact numbers-only JSON like:
    {
      "mode": "YTD",
      "window": {"start":"2025-01-01","end":"2025-09-30"},
      "scope": {"category":"Biscuits","market":"India","dims":["brand"]},
      "measure": "value_sales",
      "highlights": {
         "yoy_pct": 12.3, "mom_pct": -1.8,
         "rank_changes": [{"label":"Alpha","from":2,"to":1}],
         "topn": [{"label":"Alpha","value":12_345_678.9},{"label":"Beta","value":11_482_775.4}],
         "share_changes": [{"label":"Alpha","delta_pp":0.6}]
      },
      "format_hints": {"percent_keys":["yoy_pct","mom_pct","delta_pp"], "decimals":1}
    }
    """
    # -> Use your existing MAT/YTD windows and groupby logic to fill this dict.
    # Keep it deterministic and small.
    raise NotImplementedError
