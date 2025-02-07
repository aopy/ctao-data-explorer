from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import json
from .db import get_async_session
from .auth import current_active_user
from .models import SavedDataset, UserTable
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
from sqlalchemy import select

class BasketCreate(BaseModel):
    """Data the frontend sends when user adds a row to the basket."""
    obs_id: str
    dataset_dict: Dict[str, Any]

class BasketItemRead(BaseModel):
    """Data we return to the frontend representing a saved item."""
    id: int
    obs_id: str
    dataset_json: Dict[str, Any]
    created_at: datetime

basket_router = APIRouter(prefix="/basket", tags=["basket"])


@basket_router.post("", response_model=BasketItemRead)
async def add_to_basket(
    basket_data: BasketCreate,
    user = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Add a dataset row to the user's basket.
    """
    # Make sure obs_id is present
    if not basket_data.obs_id:
        raise HTTPException(status_code=400, detail="obs_id is required")

    # Create the new record
    saved_item = SavedDataset(
        user_id=user.id,
        obs_id=basket_data.obs_id,
        dataset_json=json.dumps(basket_data.dataset_dict),  # store as text
    )
    session.add(saved_item)
    await session.commit()
    await session.refresh(saved_item)

    return BasketItemRead(
        id=saved_item.id,
        obs_id=saved_item.obs_id,
        dataset_json=json.loads(saved_item.dataset_json),
        created_at=saved_item.created_at,
    )

@basket_router.get("")
async def get_basket(
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(SavedDataset)
        .where(SavedDataset.user_id == user.id)
        .order_by(SavedDataset.created_at.desc())
    )
    rows = result.scalars().all()
    # Return them as a list of BasketItemRead
    return [
       BasketItemRead(
           id=row.id,
           obs_id=row.obs_id,
           dataset_json=json.loads(row.dataset_json),
           created_at=row.created_at
       )
       for row in rows
    ]

@basket_router.get("/{item_id}", response_model=BasketItemRead)
async def get_basket_item(
    item_id: int,
    user = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Retrieve a single saved dataset by ID. Check ownership.
    """
    result = await session.execute(
        SavedDataset.__table__.select()
        .where(SavedDataset.id == item_id, SavedDataset.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    saved = row
    return BasketItemRead(
        id=saved.id,
        obs_id=saved.obs_id,
        dataset_json=json.loads(saved.dataset_json),
        created_at=saved.created_at,
    )

@basket_router.delete("/{item_id}")
async def remove_from_basket(
    item_id: int,
    user = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Remove item from basket if belongs to user.
    """
    result = await session.execute(
        SavedDataset.__table__.select()
        .where(SavedDataset.id == item_id, SavedDataset.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    # delete
    await session.execute(
        SavedDataset.__table__.delete()
        .where(SavedDataset.id == item_id)
    )
    await session.commit()

    return {"detail": f"Removed item {item_id} from basket"}
