"""remove_email_from_users_table

Revision ID: cc0837c676f3
Revises: 669b3735c944
Create Date: 2025-06-10 15:19:48.298388

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cc0837c676f3"
down_revision: Union[str, None] = "669b3735c944"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "email")
    # op.drop_column('users', 'first_name')
    # op.drop_column('users', 'last_name')
    # op.drop_column('users', 'first_login_at')


def downgrade() -> None:
    pass
