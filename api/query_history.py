from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json
from .models import QueryHistory
from .db import get_async_session
from .auth import get_required_session_user
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from fastapi import status

class QueryHistoryCreate(BaseModel):
    query_params: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None

class QueryHistoryRead(BaseModel):
    id: int
    query_date: datetime
    query_params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    # include results summary or keep full?
    results: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        from_attributes = True
        extra = "ignore"

query_history_router = APIRouter(prefix="/query-history", tags=["query_history"])

# @query_history_router.post("", response_model=QueryHistoryRead)
async def _internal_create_query_history(
        history: QueryHistoryCreate,
        app_user_id: int,  # Expect app_user_id directly
        session: AsyncSession
):
    """Creates a query history record."""

    try:
        new_history = QueryHistory(
            user_id=app_user_id,
            query_params=json.dumps(history.query_params) if history.query_params else None,
            results=json.dumps(history.results) if history.results else None,
        )
        session.add(new_history)
        await session.commit()
        await session.refresh(new_history)

        # Prepare response data
        response_data = QueryHistoryRead(
             id=new_history.id,
             query_date=new_history.query_date,
             query_params=json.loads(new_history.query_params) if new_history.query_params else None,
             results=json.loads(new_history.results) if new_history.results else None,
        )
        return response_data

    except json.JSONDecodeError as e:
         print(f"Error decoding JSON during history response preparation: {e}")
         raise HTTPException(status_code=500, detail="Failed to process history data for response.")
    except Exception as e:
         await session.rollback()
         print(f"Error creating query history: {e}")
         raise HTTPException(status_code=500, detail="Failed to save query history.")

@query_history_router.post("", response_model=QueryHistoryRead)
async def create_query_history(
    history: QueryHistoryCreate,
    # Get app_user_id from the new session dependency
    user_session_data: Dict[str, Any] = Depends(get_required_session_user),
    session: AsyncSession = Depends(get_async_session)
):
    app_user_id = user_session_data["app_user_id"]
    # Call the internal logic function
    return await _internal_create_query_history(history, app_user_id, session)

@query_history_router.get("", response_model=List[QueryHistoryRead])
async def get_query_history(
    user_session_data: Dict[str, Any] = Depends(get_required_session_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Retrieves the query history for the logged-in user."""
    app_user_id = user_session_data["app_user_id"]
    try:
        result = await session.execute(
            select(QueryHistory)
            .where(QueryHistory.user_id == app_user_id)
            .order_by(QueryHistory.query_date.desc())
            # .limit(100) # add limit?
        )
        histories = result.scalars().all()

        # Convert JSON strings to dicts for the response model
        response_list = []
        for db_history in histories:
            try:
                query_params_dict = json.loads(db_history.query_params) if db_history.query_params else None
                results_dict = json.loads(db_history.results) if db_history.results else None

                response_list.append(QueryHistoryRead(
                    id=db_history.id,
                    query_date=db_history.query_date,
                    query_params=query_params_dict,
                    results=results_dict,
                ))
            except json.JSONDecodeError as e:
                 print(f"Error decoding JSON for history ID {db_history.id}: {e}")
                 continue # Skip records with bad JSON for now

        return response_list
    except Exception as e:
        print(f"Error fetching query history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve query history.")


@query_history_router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query_history_item(
    history_id: int,
    user_session_data: Dict[str, Any] = Depends(get_required_session_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Deletes a specific query history item for the user."""
    app_user_id = user_session_data["app_user_id"]
    stmt = select(QueryHistory).where(
        QueryHistory.id == history_id,
        QueryHistory.user_id == app_user_id
    )
    result = await session.execute(stmt)
    history_item = result.scalars().first()

    if not history_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query history item not found.")

    try:
        await session.delete(history_item)
        await session.commit()
    except Exception as e:
        await session.rollback()
        print(f"Error deleting history item {history_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete history item.")

    return None
