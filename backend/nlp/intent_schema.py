from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class TimeRange(BaseModel):
    start: Optional[str] = None  # 'YYYY-MM'
    end: Optional[str] = None

class SortSpec(BaseModel):
    by: Optional[str] = None
    order: Optional[str] = "desc"
    limit: Optional[int] = 10

class Intent(BaseModel):
    task: str = Field(default="table")  # table | chart | text
    measures: List[str] = Field(default_factory=lambda: ["value_sales"])
    dims: List[str] = Field(default_factory=lambda: ["date"])
    filters: Dict[str, str] = Field(default_factory=dict)
    time_range: Optional[TimeRange] = None
    compare_to: Optional[str] = None  # "YoY" | "MAT" | None
    sort: Optional[SortSpec] = SortSpec()
    explain: bool = True
