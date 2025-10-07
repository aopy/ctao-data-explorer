"""drop external_tokens table

Revision ID: 4960fd93be7e
Revises: c296416b08f5
Create Date: 2025-10-07 15:36:15.994663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4960fd93be7e'
down_revision: Union[str, None] = 'c296416b08f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
