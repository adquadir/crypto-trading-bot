from sqlalchemy import create_engine, text
from src.database.database import get_database_url

def upgrade():
    """Add description column to strategies table."""
    engine = create_engine(get_database_url())
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE strategies 
            ADD COLUMN description VARCHAR;
        """))
        conn.commit()

def downgrade():
    """Remove description column from strategies table."""
    engine = create_engine(get_database_url())
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE strategies 
            DROP COLUMN description;
        """))
        conn.commit()

if __name__ == "__main__":
    upgrade() 