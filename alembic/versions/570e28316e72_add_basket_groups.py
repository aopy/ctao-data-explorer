"""add basket_groups fix

Revision ID: 570e28316e72
Revises: 4f07440fb4c8
Create Date: 2025-02-18 12:34:56.789012

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "570e28316e72"
down_revision = "4f07440fb4c8"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Drop the foreign key constraint from saved_datasets that depends on saved_baskets.
    op.drop_constraint("saved_datasets_basket_id_fkey", "saved_datasets", type_="foreignkey")

    # 2. Drop the old saved_baskets table.
    op.drop_table("saved_baskets")

    # 3. Create the new basket_groups table.
    op.create_table(
        "basket_groups",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, server_default="My Basket"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    # 4. Add the new basket_group_id column to saved_datasets.
    op.add_column("saved_datasets", sa.Column("basket_group_id", sa.Integer(), nullable=True))

    # 5. Create a new foreign key constraint on saved_datasets.basket_group_id referencing basket_groups.id.
    op.create_foreign_key(
        "saved_datasets_basket_group_id_fkey",  # new constraint name
        "saved_datasets",  # source table
        "basket_groups",  # referent table
        ["basket_group_id"],  # local column(s)
        ["id"],  # remote column(s)
    )


def downgrade():
    # Reverse the upgrade steps:
    op.drop_constraint("saved_datasets_basket_group_id_fkey", "saved_datasets", type_="foreignkey")
    op.drop_column("saved_datasets", "basket_group_id")
    op.drop_table("basket_groups")
    op.create_table(
        "saved_baskets",
        sa.Column("id", sa.Integer(), primary_key=True),
        # ... (include other columns as originally defined) ...
    )
    op.create_foreign_key(
        "saved_datasets_basket_id_fkey",
        "saved_datasets",
        "saved_baskets",
        ["basket_group_id"],  # This assumes the original column name was reused
        ["id"],
    )
