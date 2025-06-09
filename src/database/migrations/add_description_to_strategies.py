"""Add description column to strategies table."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = 'add_description_to_strategies'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Add description column to strategies table."""
    op.add_column('strategies', sa.Column('description', sa.String(255), nullable=True))

def downgrade():
    """Remove description column from strategies table."""
    op.drop_column('strategies', 'description') 