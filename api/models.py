from pydantic import BaseModel, Field
from typing import List, Any
from .db import Base
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    func,
    ForeignKey,
    Table,
    Boolean,
)
from sqlalchemy.orm import relationship


basket_items_association = Table(
    "basket_items_association",
    Base.metadata,
    Column(
        "basket_group_id", Integer, ForeignKey("basket_groups.id"), primary_key=True
    ),
    Column(
        "saved_dataset_id", Integer, ForeignKey("saved_datasets.id"), primary_key=True
    ),
)


class SearchResult(BaseModel):
    columns: List[str] = Field(
        ..., title="Column Names", description="List of column names in the result set"
    )
    data: List[List[Any]] = Field(
        ..., title="Data Rows", description="List of data rows"
    )


class UserTable(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)  # internal app user ID
    iam_subject_id = Column(
        String, unique=True, index=True, nullable=False
    )  # IAM's sub
    # email = Column(String, unique=True, index=True, nullable=True)
    # first_name, last_name, first_login_at are removed
    hashed_password = Column(
        String, nullable=False, server_default="dummy_hash_not_used"
    )
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)

    saved_datasets = relationship(
        "SavedDataset", back_populates="user", cascade="all, delete-orphan"
    )
    basket_groups = relationship(
        "BasketGroup", back_populates="user", cascade="all, delete-orphan"
    )
    query_history = relationship(
        "QueryHistory", back_populates="user", cascade="all, delete-orphan"
    )
    # Relationship to stored refresh tokens
    refresh_tokens = relationship(
        "UserRefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class QueryHistory(Base):
    __tablename__ = "query_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query_date = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
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

    saved_datasets = relationship(
        "SavedDataset",
        secondary=basket_items_association,
        back_populates="basket_groups",  # ,
        # cascade="all, delete"
    )
    user = relationship("UserTable", back_populates="basket_groups")


class SavedDataset(Base):
    __tablename__ = "saved_datasets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    obs_id = Column(String, nullable=False)
    dataset_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("UserTable", back_populates="saved_datasets")
    # Relationship back to BasketGroup via association table
    basket_groups = relationship(
        "BasketGroup",
        secondary=basket_items_association,
        back_populates="saved_datasets",
    )


class UserRefreshToken(Base):
    __tablename__ = "user_refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    iam_provider_name = Column(String, nullable=False, default="ctao")  # multiple IAMs?
    encrypted_refresh_token = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    user = relationship("UserTable", back_populates="refresh_tokens")
