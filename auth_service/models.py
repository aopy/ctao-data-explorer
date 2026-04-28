from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from auth_service.db_base import Base


class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    iam_subject_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # fastapi-users fields
    hashed_password: Mapped[str] = mapped_column(String, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


__all__ = ["UserTable"]
