from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

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


class UserTable(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    iam_subject_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(
        String, nullable=False, server_default="dummy_hash_not_used"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    saved_datasets: Mapped[list[SavedDataset]] = relationship(
        "SavedDataset", back_populates="user", cascade="all, delete-orphan"
    )
    basket_groups: Mapped[list[BasketGroup]] = relationship(
        "BasketGroup", back_populates="user", cascade="all, delete-orphan"
    )
    query_history: Mapped[list[QueryHistory]] = relationship(
        "QueryHistory", back_populates="user", cascade="all, delete-orphan"
    )

    refresh_tokens: Mapped[list[UserRefreshToken]] = relationship(
        "UserRefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class QueryHistory(Base):
    __tablename__ = "query_history"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    query_date: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    query_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[str | None] = mapped_column(Text, nullable=True)
    user: Mapped[UserTable] = relationship("UserTable", back_populates="query_history")


class BasketGroup(Base):
    __tablename__ = "basket_groups"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="My Basket")
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    saved_datasets: Mapped[list[SavedDataset]] = relationship(
        "SavedDataset",
        secondary=basket_items_association,
        back_populates="basket_groups",  # ,
        # cascade="all, delete"
    )
    user: Mapped[UserTable] = relationship("UserTable", back_populates="basket_groups")


class SavedDataset(Base):
    __tablename__ = "saved_datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    obs_id: Mapped[str] = mapped_column(String, nullable=False)
    dataset_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[UserTable] = relationship("UserTable", back_populates="saved_datasets")
    # Relationship back to BasketGroup via association table
    basket_groups: Mapped[list[BasketGroup]] = relationship(
        "BasketGroup",
        secondary=basket_items_association,
        back_populates="saved_datasets",
    )


class UserRefreshToken(Base):
    __tablename__ = "user_refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    iam_provider_name: Mapped[str] = mapped_column(String, nullable=False, default="ctao")
    encrypted_refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    user: Mapped[UserTable] = relationship("UserTable", back_populates="refresh_tokens")
