from pydantic import BaseModel, Field
from typing import List, Any

class SearchResult(BaseModel):
    columns: List[str] = Field(..., title="Column Names", description="List of column names in the result set")
    data: List[List[Any]] = Field(..., title="Data Rows", description="List of data rows")
