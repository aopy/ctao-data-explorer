from __future__ import annotations

from typing import Any

from ctao_shared.db import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

USER_ID_FK = "users.id"


class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    iam_subject_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(
        String, nullable=False, server_default="dummy_hash_not_used"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserRefreshToken(Base):
    __tablename__ = "user_refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(USER_ID_FK, ondelete="CASCADE"), nullable=False)
    iam_provider_name: Mapped[str] = mapped_column(String, nullable=False, default="ctao")
    encrypted_refresh_token: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )
