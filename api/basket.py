from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import json
from .db import get_async_session
from .auth import current_active_user
from .models import SavedDataset, UserTable, BasketGroup, basket_items_association
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload, Session


class BasketCreate(BaseModel):
    """Data the frontend sends when user adds a row to the basket."""
    obs_id: str
    dataset_dict: Dict[str, Any]
    basket_group_id: int

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
    saved_datasets: List[BasketItemRead] = Field(default_factory=list)
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
        .options(selectinload(BasketGroup.saved_datasets))
        .where(BasketGroup.user_id == user.id)
        .order_by(BasketGroup.created_at.desc())
    )
    groups = result.unique().scalars().all()

    # Convert dataset_json from string to dict for each basket item
    for group in groups:
        for item in group.saved_datasets:
            if isinstance(item.dataset_json, str):
                try:
                    item.dataset_json = json.loads(item.dataset_json)
                except json.JSONDecodeError:
                    item.dataset_json = {"error": "invalid json"}
            elif item.dataset_json is None:
                item.dataset_json = {"error": "missing json"}
    return groups


@basket_router.post("/items", response_model=BasketItemRead)
async def add_item_to_basket(
    basket_data: BasketCreate,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Adds a dataset (identified by obs_id) to a specific basket group.
    Creates the base SavedDataset if it doesn't exist for the user.
    Prevents adding the same dataset to the same group multiple times.
    """
    if not basket_data.obs_id:
        raise HTTPException(status_code=400, detail="obs_id is required")
    if not basket_data.basket_group_id:
         raise HTTPException(status_code=400, detail="basket_group_id is required")

    stmt_find = select(SavedDataset).where(
        SavedDataset.user_id == user.id,
        SavedDataset.obs_id == basket_data.obs_id
    )
    result = await session.execute(stmt_find)
    saved_dataset = result.scalars().first()

    if not saved_dataset:
        saved_dataset = SavedDataset(
            user_id=user.id,
            obs_id=basket_data.obs_id,
            dataset_json=json.dumps(basket_data.dataset_dict),
        )
        session.add(saved_dataset)
        await session.flush()
        await session.refresh(saved_dataset)
        print(f"DEBUG: Created new SavedDataset ID: {saved_dataset.id} for obs_id: {saved_dataset.obs_id}")
    else:
        # Update dataset_json if it already exists?
        print(f"DEBUG: Found existing SavedDataset ID: {saved_dataset.id} for obs_id: {saved_dataset.obs_id}")
        pass

    stmt_group = select(BasketGroup).options(
        selectinload(BasketGroup.saved_datasets)
        ).where(
        BasketGroup.id == basket_data.basket_group_id,
        BasketGroup.user_id == user.id
    )
    result_group = await session.execute(stmt_group)
    basket_group = result_group.scalars().first()

    if not basket_group:
        raise HTTPException(
            status_code=404,
            detail=f"Basket group with id={basket_data.basket_group_id} not found or not owned by user."
        )

    if saved_dataset in basket_group.saved_datasets:
         raise HTTPException(
             status_code=409,
             detail=f"Dataset obs_id={basket_data.obs_id} is already in basket group '{basket_group.name}' (id={basket_group.id})"
         )

    basket_group.saved_datasets.append(saved_dataset)
    session.add(basket_group)

    await session.commit()
    await session.refresh(saved_dataset)

    return BasketItemRead(
        id=saved_dataset.id,
        obs_id=saved_dataset.obs_id,
        dataset_json=json.loads(saved_dataset.dataset_json),
        created_at=saved_dataset.created_at,
    )

@basket_router.delete("/groups/{group_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item_from_basket_group(
    group_id: int,
    item_id: int,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Removes the link between a specific dataset and a specific basket group."""

    stmt_group = select(BasketGroup).options(selectinload(BasketGroup.saved_datasets)).where(
        BasketGroup.id == group_id,
        BasketGroup.user_id == user.id
    )
    result_group = await session.execute(stmt_group)
    basket_group = result_group.scalars().first()

    if not basket_group:
        raise HTTPException(
            status_code=404,
            detail=f"Basket group id={group_id} not found or not owned by user."
        )

    stmt_item = select(SavedDataset).where(
        SavedDataset.id == item_id,
        SavedDataset.user_id == user.id
    )
    result_item = await session.execute(stmt_item)
    saved_dataset = result_item.scalars().first()

    if not saved_dataset:
         raise HTTPException(
             status_code=404,
             detail=f"Saved dataset id={item_id} not found or not owned by user."
         )

    if saved_dataset not in basket_group.saved_datasets:
          raise HTTPException(
              status_code=404,
              detail=f"Dataset id={item_id} (obs_id={saved_dataset.obs_id}) not found within basket group id={group_id}."
          )

    try:
        basket_group.saved_datasets.remove(saved_dataset)
        await session.commit()
    except Exception as e:
        await session.rollback()
        print(f"Error removing dataset from group: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove dataset from group.")

    return None


@basket_router.get("/items", response_model=List[BasketItemRead])
async def get_all_saved_datasets_for_user(
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Gets all unique SavedDataset items associated with any of the user's baskets."""
    stmt = (
        select(SavedDataset)
        .join(basket_items_association)
        .join(BasketGroup)
        .where(BasketGroup.user_id == user.id)
        .distinct()
        .order_by(SavedDataset.created_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    response_items = []
    for row in rows:
         try:
             dataset_json = json.loads(row.dataset_json)
         except json.JSONDecodeError:
             dataset_json = {"error": "invalid json"}
         except TypeError:
             dataset_json = {"error": "missing json"}

         response_items.append(
             BasketItemRead(
                 id=row.id,
                 obs_id=row.obs_id,
                 dataset_json=dataset_json,
                 created_at=row.created_at,
             )
         )
    return response_items


@basket_router.get("/items/{item_id}", response_model=BasketItemRead)
async def get_saved_dataset_item(
    item_id: int,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Retrieve a single saved dataset by ID, checking user ownership."""

    stmt = select(SavedDataset).where(SavedDataset.id == item_id, SavedDataset.user_id == user.id)
    result = await session.execute(stmt)
    saved_item = result.scalars().first()

    if not saved_item:
        raise HTTPException(status_code=404, detail="Saved dataset not found")

    try:
        dataset_json = json.loads(saved_item.dataset_json)
    except Exception:
        dataset_json = {"error": "invalid or missing json"}

    return BasketItemRead(
        id=saved_item.id,
        obs_id=saved_item.obs_id,
        dataset_json=dataset_json,
        created_at=saved_item.created_at,
    )


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
        saved_datasets=[]
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
        .options(selectinload(BasketGroup.saved_datasets))
        .where(BasketGroup.id == group_id, BasketGroup.user_id == user.id)
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Basket group not found")
    group.name = group_data.name
    await session.commit()
    await session.refresh(group)
    # Refresh the loaded datasets relation manually
    # await session.refresh(group, attribute_names=['saved_datasets'])

    for item in group.saved_datasets:
        if isinstance(item.dataset_json, str):
            try:
                item.dataset_json = json.loads(item.dataset_json)
            except Exception: item.dataset_json = {}

    return group


@basket_router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_basket_group(
    group_id: int,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    # Deleting a group might leave SavedDataset records orphaned
    # if they are not in any other group. Cleanup needed?
    result = await session.execute(
        select(BasketGroup).where(BasketGroup.id == group_id, BasketGroup.user_id == user.id)
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Basket group not found")
    await session.delete(group)
    await session.commit()
    return None


@basket_router.get("/groups/{group_id}", response_model=BasketGroupRead)
async def get_basket_group_by_id(
    group_id: int,
    user: UserTable = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Retrieves a specific basket group by its ID, including its items (datasets).
    Ensures the requesting user owns the basket group.
    """

    stmt = (
        select(BasketGroup)
        .options(selectinload(BasketGroup.saved_datasets))
        .where(BasketGroup.id == group_id, BasketGroup.user_id == user.id)
    )

    result = await session.execute(stmt)
    group = result.unique().scalars().first()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Basket group with id={group_id} not found or not accessible."
        )

    # Create a list to hold the processed BasketItemRead models
    processed_datasets: List[BasketItemRead] = []
    for item in group.saved_datasets:
        parsed_json = {}
        if isinstance(item.dataset_json, str):
            try:
                parsed_json = json.loads(item.dataset_json)
            except json.JSONDecodeError:
                print(f"Warning: Invalid JSON found in SavedDataset ID {item.id}")
                parsed_json = {"error": "invalid JSON in database"}
        elif item.dataset_json is None:
             parsed_json = {"error": "missing JSON in database"}
        else:
             parsed_json = item.dataset_json

        processed_datasets.append(
            BasketItemRead(
                id=item.id,
                obs_id=item.obs_id,
                dataset_json=parsed_json,
                created_at=item.created_at,
            )
        )

    response_data = BasketGroupRead(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        saved_datasets=processed_datasets
    )

    return response_data
