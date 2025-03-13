from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json
from .models import QueryHistory, UserTable
from .db import get_async_session
from .auth import current_active_user
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime

class QueryHistoryCreate(BaseModel):
    query_params: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None

class QueryHistoryRead(BaseModel):
    id: int
    user_id: int
    query_date: datetime
    query_params: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        extra = "ignore"

query_history_router = APIRouter(prefix="/query-history", tags=["query_history"])

@query_history_router.post("", response_model=QueryHistoryRead)
async def create_query_history(
    history: QueryHistoryCreate,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    new_history = QueryHistory(
        user_id=user.id,
        query_params=json.dumps(history.query_params) if history.query_params else None,
        results=json.dumps(history.results) if history.results else None,
    )
    session.add(new_history)
    await session.commit()
    await session.refresh(new_history)
    if new_history.query_params:
        new_history.query_params = json.loads(new_history.query_params)
    if new_history.results:
        new_history.results = json.loads(new_history.results)
    return QueryHistoryRead.from_orm(new_history)

@query_history_router.get("", response_model=List[QueryHistoryRead])
async def get_query_history(
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    result = await session.execute(
        select(QueryHistory).where(QueryHistory.user_id == user.id).order_by(QueryHistory.query_date.desc())
    )
    histories = result.scalars().all()
    # Convert JSON strings to dicts
    for history in histories:
        if history.query_params:
            history.query_params = json.loads(history.query_params)
        if history.results:
            history.results = json.loads(history.results)
    return [QueryHistoryRead.from_orm(history) for history in histories]