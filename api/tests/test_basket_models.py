import uuid

import pytest
from sqlalchemy.orm import attributes

from api.models import BasketGroup, SavedDataset, UserTable


@pytest.mark.anyio
async def test_basket_group_adds_items(db_session):
    u = UserTable(iam_subject_id=f"sub-{uuid.uuid4().hex[:6]}", hashed_password="")
    db_session.add(u)
    await db_session.flush()

    g = BasketGroup(user_id=u.id, name="My Basket")
    d1 = SavedDataset(user_id=u.id, obs_id="obs-001", dataset_json='{"a":1}')
    d2 = SavedDataset(user_id=u.id, obs_id="obs-002", dataset_json='{"a":2}')
    db_session.add_all([g, d1, d2])
    await db_session.flush()

    # Prevent async lazy-load: mark collection as initialized (empty)
    attributes.set_committed_value(g, "saved_datasets", [])
    g.saved_datasets.extend([d1, d2])
    await db_session.flush()

    # Verify via association table
    from sqlalchemy import select

    from api.models import basket_items_association

    rows = (
        await db_session.execute(
            select(basket_items_association).where(
                basket_items_association.c.basket_group_id == g.id
            )
        )
    ).fetchall()
    assert len(rows) == 2
