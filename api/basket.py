from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import json
from .db import get_async_session
from .auth import current_active_user
from .models import SavedDataset, UserTable, BasketGroup
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

class BasketCreate(BaseModel):
    """Data the frontend sends when user adds a row to the basket."""
    obs_id: str
    dataset_dict: Dict[str, Any]
    basket_group_id: Optional[int] = None

class BasketItemRead(BaseModel):
    """Data we return to the frontend representing a saved item."""
    id: int
    obs_id: str
    dataset_json: Dict[str, Any]
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True
        extra = "ignore"

class BasketGroupCreate(BaseModel):
    name: str

class BasketGroupUpdate(BaseModel):
    name: str

class BasketGroupRead(BaseModel):
    id: int
    name: str
    created_at: Optional[datetime] = None
    items: List[BasketItemRead] = []
    class Config:
        from_attributes = True
        extra = "ignore"

basket_router = APIRouter(prefix="/basket", tags=["basket"])

@basket_router.get("/groups", response_model=List[BasketGroupRead])
async def get_basket_groups(
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(BasketGroup)
        .options(joinedload(BasketGroup.items))
        .where(BasketGroup.user_id == user.id)
        .order_by(BasketGroup.created_at.desc())
    )
    groups = result.unique().scalars().all()

    # Convert dataset_json from string to dict for each basket item
    for group in groups:
        for item in group.items:
            if isinstance(item.dataset_json, str):
                try:
                    item.dataset_json = json.loads(item.dataset_json)
                except Exception as e:
                    item.dataset_json = {}
    return groups


@basket_router.post("", response_model=BasketItemRead)
async def add_to_basket(
    basket_data: BasketCreate,
    user = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    if not basket_data.obs_id:
        raise HTTPException(status_code=400, detail="obs_id is required")

    # Check if this obs_id already exists for this user (across groups)
    existing = await session.execute(
        select(SavedDataset)
        .where(SavedDataset.user_id == user.id)
        .where(SavedDataset.obs_id == basket_data.obs_id)
    )
    existing_item = existing.scalars().first()

    if existing_item:
        raise HTTPException(
            status_code=409,
            detail=f"obs_id={basket_data.obs_id} is already in your basket"
        )

    saved_item = SavedDataset(
        user_id=user.id,
        obs_id=basket_data.obs_id,
        dataset_json=json.dumps(basket_data.dataset_dict),
        basket_group_id=basket_data.basket_group_id
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
    # Return as a list of BasketItemRead
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
        return {"detail": f"Item {item_id} not found; it may have been already deleted."}

    # delete
    await session.execute(
        SavedDataset.__table__.delete()
        .where(SavedDataset.id == item_id)
    )
    await session.commit()

    return {"detail": f"Removed item {item_id} from basket"}


@basket_router.post("/groups", response_model=BasketGroupRead)
async def create_basket_group(
    group_data: BasketGroupCreate,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    group = BasketGroup(
        user_id=user.id,
        name=group_data.name,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return BasketGroupRead(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        items=[]
    )

@basket_router.put("/groups/{group_id}", response_model=BasketGroupRead)
async def update_basket_group(
    group_id: int,
    group_data: BasketGroupUpdate,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(BasketGroup)
        .options(selectinload(BasketGroup.items))
        .where(BasketGroup.id == group_id, BasketGroup.user_id == user.id)
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Basket group not found")
    group.name = group_data.name
    await session.commit()
    await session.refresh(group)
    return BasketGroupRead(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        items=[
            BasketItemRead(
                id=item.id,
                obs_id=item.obs_id,
                dataset_json=json.loads(item.dataset_json),
                created_at=item.created_at
            ) for item in group.items
        ]
    )

@basket_router.delete("/groups/{group_id}")
async def delete_basket_group(
    group_id: int,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(BasketGroup).where(BasketGroup.id == group_id, BasketGroup.user_id == user.id)
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Basket group not found")
    await session.delete(group)
    await session.commit()
    return {"detail": f"Basket group {group_id} deleted"}
