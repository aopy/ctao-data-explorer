from __future__ import annotations

from typing import Any

from ctao_shared.db import Base
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

USER_ID_FK = "users.id"

basket_items_association = Table(
    "basket_items_association",
    Base.metadata,
    Column("basket_group_id", Integer, ForeignKey("basket_groups.id"), primary_key=True),
    Column("saved_dataset_id", Integer, ForeignKey("saved_datasets.id"), primary_key=True),
)


class SearchResult(BaseModel):
    columns: list[str] = Field(
        ..., title="Column Names", description="List of column names in the result set"
    )
    data: list[list[Any]] = Field(..., title="Data Rows", description="List of data rows")


class QueryHistory(Base):
    __tablename__ = "query_history"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(USER_ID_FK), nullable=False)
    query_date: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    query_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[str | None] = mapped_column(Text, nullable=True)
    # user: Mapped[UserTable] = relationship("UserTable", back_populates="query_history")


class BasketGroup(Base):
    __tablename__ = "basket_groups"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(USER_ID_FK), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="My Basket")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    saved_datasets: Mapped[list[SavedDataset]] = relationship(
        "SavedDataset",
        secondary=basket_items_association,
        back_populates="basket_groups",  # ,
        # cascade="all, delete"
    )
    # user: Mapped[UserTable] = relationship("UserTable", back_populates="basket_groups")


class SavedDataset(Base):
    __tablename__ = "saved_datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(USER_ID_FK), nullable=False)
    obs_id: Mapped[str] = mapped_column(String, nullable=False)
    dataset_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # user: Mapped[UserTable] = relationship("UserTable", back_populates="saved_datasets")
    # Relationship back to BasketGroup via association table
    basket_groups: Mapped[list[BasketGroup]] = relationship(
        "BasketGroup",
        secondary=basket_items_association,
        back_populates="saved_datasets",
    )
