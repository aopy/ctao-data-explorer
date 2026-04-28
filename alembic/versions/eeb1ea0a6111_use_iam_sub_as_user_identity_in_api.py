"""Use iam_sub as user identity in API

Revision ID: eeb1ea0a6111
Revises: ccf858918774
Create Date: 2026-04-16 16:16:37.476034
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "eeb1ea0a6111"
down_revision: Union[str, None] = "ccf858918774"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_sub columns as NULLABLE first (so existing rows don't break migration)
    op.add_column("basket_groups", sa.Column("user_sub", sa.String(length=128), nullable=True))
    op.add_column("saved_datasets", sa.Column("user_sub", sa.String(length=128), nullable=True))
    op.add_column("query_history", sa.Column("user_sub", sa.String(length=128), nullable=True))

    # Backfill user_sub from legacy users table using user_id
    op.execute(
        """
        UPDATE basket_groups bg
        SET user_sub = u.iam_subject_id
        FROM users u
        WHERE bg.user_id = u.id
          AND bg.user_sub IS NULL;
        """
    )
    op.execute(
        """
        UPDATE saved_datasets sd
        SET user_sub = u.iam_subject_id
        FROM users u
        WHERE sd.user_id = u.id
          AND sd.user_sub IS NULL;
        """
    )
    op.execute(
        """
        UPDATE query_history qh
        SET user_sub = u.iam_subject_id
        FROM users u
        WHERE qh.user_id = u.id
          AND qh.user_sub IS NULL;
        """
    )

    # Fail fast if any rows couldn't be mapped
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM basket_groups WHERE user_sub IS NULL) THEN
            RAISE EXCEPTION 'basket_groups has rows with NULL user_sub after backfill';
          END IF;
          IF EXISTS (SELECT 1 FROM saved_datasets WHERE user_sub IS NULL) THEN
            RAISE EXCEPTION 'saved_datasets has rows with NULL user_sub after backfill';
          END IF;
          IF EXISTS (SELECT 1 FROM query_history WHERE user_sub IS NULL) THEN
            RAISE EXCEPTION 'query_history has rows with NULL user_sub after backfill';
          END IF;
        END $$;
        """
    )

    # Enforce NOT NULL once populated
    op.alter_column(
        "basket_groups",
        "user_sub",
        existing_type=sa.String(length=128),
        nullable=False,
    )
    op.alter_column(
        "saved_datasets",
        "user_sub",
        existing_type=sa.String(length=128),
        nullable=False,
    )
    op.alter_column(
        "query_history",
        "user_sub",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.alter_column(
        "basket_groups",
        "name",
        existing_type=sa.VARCHAR(),
        server_default=None,
        existing_nullable=False,
    )

    # Create indexes on user_sub
    op.create_index(op.f("ix_basket_groups_user_sub"), "basket_groups", ["user_sub"], unique=False)
    op.create_index(
        op.f("ix_saved_datasets_user_sub"), "saved_datasets", ["user_sub"], unique=False
    )
    op.create_index(op.f("ix_query_history_user_sub"), "query_history", ["user_sub"], unique=False)

    # Drop old FKs + user_id columns
    op.drop_constraint("basket_groups_user_id_fkey", "basket_groups", type_="foreignkey")
    op.drop_column("basket_groups", "user_id")

    op.drop_constraint("saved_datasets_user_id_fkey", "saved_datasets", type_="foreignkey")
    op.drop_column("saved_datasets", "user_id")

    op.drop_constraint("query_history_user_id_fkey", "query_history", type_="foreignkey")
    op.drop_column("query_history", "user_id")


def downgrade() -> None:

    op.add_column("basket_groups", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("saved_datasets", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("query_history", sa.Column("user_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE basket_groups bg
        SET user_id = u.id
        FROM users u
        WHERE bg.user_sub = u.iam_subject_id
          AND bg.user_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE saved_datasets sd
        SET user_id = u.id
        FROM users u
        WHERE sd.user_sub = u.iam_subject_id
          AND sd.user_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE query_history qh
        SET user_id = u.id
        FROM users u
        WHERE qh.user_sub = u.iam_subject_id
          AND qh.user_id IS NULL;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM basket_groups WHERE user_id IS NULL) THEN
            RAISE EXCEPTION 'basket_groups has rows with NULL user_id after downgrade backfill';
          END IF;
          IF EXISTS (SELECT 1 FROM saved_datasets WHERE user_id IS NULL) THEN
            RAISE EXCEPTION 'saved_datasets has rows with NULL user_id after downgrade backfill';
          END IF;
          IF EXISTS (SELECT 1 FROM query_history WHERE user_id IS NULL) THEN
            RAISE EXCEPTION 'query_history has rows with NULL user_id after downgrade backfill';
          END IF;
        END $$;
        """
    )

    op.alter_column("basket_groups", "user_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("saved_datasets", "user_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("query_history", "user_id", existing_type=sa.Integer(), nullable=False)

    op.create_foreign_key(
        "basket_groups_user_id_fkey", "basket_groups", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "saved_datasets_user_id_fkey", "saved_datasets", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "query_history_user_id_fkey", "query_history", "users", ["user_id"], ["id"]
    )

    op.drop_index(op.f("ix_basket_groups_user_sub"), table_name="basket_groups")
    op.drop_index(op.f("ix_saved_datasets_user_sub"), table_name="saved_datasets")
    op.drop_index(op.f("ix_query_history_user_sub"), table_name="query_history")

    # Restore original name default if you had one
    op.alter_column(
        "basket_groups",
        "name",
        existing_type=sa.VARCHAR(),
        server_default=sa.text("'My Basket'::character varying"),
        existing_nullable=False,
    )

    op.drop_column("basket_groups", "user_sub")
    op.drop_column("saved_datasets", "user_sub")
    op.drop_column("query_history", "user_sub")
