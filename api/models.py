from pydantic import BaseModel, Field
from typing import List, Any
from .db import Base
from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Column, Integer, String, DateTime, String, ForeignKey, Text, func
from sqlalchemy.orm import relationship

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
    # Relationship to saved datasets:
    saved_datasets = relationship(
        "SavedDataset",
        back_populates="user",
        cascade="all, delete-orphan"
    )

class SavedDataset(Base):
    __tablename__ = "saved_datasets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    obs_id = Column(String, nullable=False)
    dataset_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to the user
    user = relationship("UserTable", back_populates="saved_datasets")
