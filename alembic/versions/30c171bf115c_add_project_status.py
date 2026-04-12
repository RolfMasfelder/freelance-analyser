"""add project status

Revision ID: 30c171bf115c
Revises: da1ca0c388e1
Create Date: 2026-04-12 15:24:34.825760

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "30c171bf115c"
down_revision: Union[str, Sequence[str], None] = "da1ca0c388e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    projectstatus = sa.Enum(
        "neu", "gesehen", "beworben", "abgelehnt", name="projectstatus"
    )
    projectstatus.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "projects",
        sa.Column("status", projectstatus, nullable=False, server_default="neu"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "status")
    sa.Enum(name="projectstatus").drop(op.get_bind(), checkfirst=True)
