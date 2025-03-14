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
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    first_login_at = Column(DateTime(timezone=True), nullable=True)
    saved_datasets = relationship("SavedDataset", back_populates="user", cascade="all, delete-orphan")
    basket_groups = relationship("BasketGroup", back_populates="user", cascade="all, delete-orphan")
    query_history = relationship("QueryHistory", back_populates="user", cascade="all, delete-orphan")

class QueryHistory(Base):
    __tablename__ = "query_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    query_params = Column(Text, nullable=True)
    results = Column(Text, nullable=True)
    user = relationship("UserTable", back_populates="query_history")

class BasketGroup(Base):
    __tablename__ = "basket_groups"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False, default="My Basket")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    items = relationship("SavedDataset", back_populates="basket_group", cascade="all, delete-orphan")
    user = relationship("UserTable", back_populates="basket_groups")

class SavedDataset(Base):
    __tablename__ = "saved_datasets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    basket_group_id = Column(Integer, ForeignKey("basket_groups.id"), nullable=True)
    obs_id = Column(String, nullable=False)
    dataset_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("UserTable", back_populates="saved_datasets")
    basket_group = relationship("BasketGroup", back_populates="items")
