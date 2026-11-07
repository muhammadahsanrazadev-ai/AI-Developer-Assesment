"""add search_keyword to discovered queries

Revision ID: a7c3e91b4d20
Revises: 20599215a9b8
Create Date: 2026-11-07 13:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a7c3e91b4d20"
down_revision = "20599215a9b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "discovered_queries",
        sa.Column("search_keyword", sa.String(length=80), nullable=True),
    )


def downgrade():
    op.drop_column("discovered_queries", "search_keyword")
