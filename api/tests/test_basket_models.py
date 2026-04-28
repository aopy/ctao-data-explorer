import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import attributes

from api.models import BasketGroup, SavedDataset, basket_items_association


@pytest.mark.anyio
async def test_basket_group_adds_items(db_session):
    sub = f"sub-{uuid.uuid4().hex[:6]}"

    g = BasketGroup(user_sub=sub, name="My Basket")
    db_session.add(g)
    await db_session.flush()

    d1 = SavedDataset(user_sub=sub, obs_id="obs1", dataset_json="{}")
    d2 = SavedDataset(user_sub=sub, obs_id="obs2", dataset_json="{}")
    db_session.add_all([d1, d2])
    await db_session.flush()

    # Prevent async lazy-load of relationship collection
    attributes.set_committed_value(g, "saved_datasets", [])
    g.saved_datasets.extend([d1, d2])

    await db_session.commit()

    rows = (
        await db_session.execute(
            select(basket_items_association).where(
                basket_items_association.c.basket_group_id == g.id
            )
        )
    ).fetchall()

    assert len(rows) == 2
