from pydantic import BaseModel, Field
from typing import List, Any
from .db import Base
from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Column, Integer, String, DateTime

class SearchResult(BaseModel):
    columns: List[str] = Field(..., title="Column Names", description="List of column names in the result set")
    data: List[List[Any]] = Field(..., title="Data Rows", description="List of data rows")

class UserTable(Base, SQLAlchemyBaseUserTable):
    __tablename__ = "users"
    # The primary key column
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    # Store the first time the user logged in
    first_login_at = Column(DateTime(timezone=True), nullable=True)