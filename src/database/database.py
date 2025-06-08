from sqlalchemy import create_engine, inspect, text, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv
from .models import Base, Strategy # Import Base and Strategy
import logging
from contextlib import contextmanager
from typing import Generator, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database URL from environment variable or use default SQLite
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./trading_bot.db"
)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base and MetaData
Base = declarative_base()
metadata = MetaData()

class Database:
    """Database management class for the trading bot."""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
        self.Base = Base
        self.metadata = metadata
    
    async def init_db(self) -> None:
        """Initialize the database and create tables."""
        try:
            # Create tables
            self.Base.metadata.create_all(bind=self.engine)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise
    
    @contextmanager
    def get_db(self) -> Generator[Session, None, None]:
        """Get a database session.
        
        Yields:
            Session: Database session
        """
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    async def check_connection(self) -> bool:
        """Check database connection.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            with self.get_db() as db:
                db.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            return False

# Initialize database
db = Database()

async def init_db() -> None:
    """Initialize the database."""
    await db.init_db()

def update_db_schema():
    """Update database schema to match models while preserving data."""
    try:
        inspector = inspect(engine)
        
        # Get existing tables
        existing_tables = inspector.get_table_names()
        logger.info(f"Existing tables: {existing_tables}")
        
        # Create any missing tables
        Base.metadata.create_all(bind=engine)
        
        # Check for missing columns in trading_signals
        if 'trading_signals' in existing_tables:
            existing_columns = [col['name'] for col in inspector.get_columns('trading_signals')]
            logger.info(f"Existing columns in trading_signals: {existing_columns}")
            
            missing_columns = []
            
            # Check for missing columns
            if 'action' not in existing_columns:
                missing_columns.append('action')
            
            # Add missing columns if any
            if missing_columns:
                with engine.connect() as conn:
                    for column in missing_columns:
                        try:
                            # PostgreSQL specific ALTER TABLE
                            conn.execute(text(f"ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS {column} VARCHAR"))
                            logger.info(f"Added missing column: {column}")
                        except Exception as e:
                            logger.error(f"Error adding column {column}: {e}")
                            # Try alternative approach for PostgreSQL
                            try:
                                conn.execute(text(f"""
                                    DO $$ 
                                    BEGIN
                                        IF NOT EXISTS (
                                            SELECT 1 
                                            FROM information_schema.columns 
                                            WHERE table_name = 'trading_signals' 
                                            AND column_name = '{column}'
                                        ) THEN
                                            ALTER TABLE trading_signals ADD COLUMN {column} VARCHAR;
                                        END IF;
                                    END $$;
                                """))
                                logger.info(f"Added missing column using alternative approach: {column}")
                            except Exception as e2:
                                logger.error(f"Alternative approach also failed for column {column}: {e2}")
                    conn.commit()
        
        logger.info("Database schema update completed successfully")
    except Exception as e:
        logger.error(f"Error updating database schema: {e}")
        raise

# Function to create database tables
def create_db_tables():
    update_db_schema()  # Use the new update function instead of create_all

# Function to add initial strategies if none exist
def add_initial_strategies():
    db = SessionLocal()
    try:
        # Check if strategies already exist
        if db.query(Strategy).count() == 0:
            print("Adding initial strategies...")
            default_strategies = [
                Strategy(
                    name="MACD Crossover", 
                    active=True, 
                    parameters={
                        "macd_fast_period": 12,
                        "macd_slow_period": 26,
                        "macd_signal_period": 9,
                        "rsi_period": 14,
                        "rsi_overbought": 70,
                        "rsi_oversold": 30,
                        "max_position_size": 0.1,
                        "max_leverage": 3,
                        "risk_per_trade": 0.02,
                        "confidence_threshold": 0.7,
                        "volatility_factor": 0.5
                    }
                ),
                Strategy(
                    name="RSI Divergence", 
                    active=True, 
                    parameters={
                        "rsi_period": 14,
                        "rsi_overbought": 70,
                        "rsi_oversold": 30,
                        "max_position_size": 0.05,
                        "max_leverage": 5,
                        "risk_per_trade": 0.01,
                        "confidence_threshold": 0.6,
                        "volatility_factor": 0.6
                    }
                )
            ]
            db.add_all(default_strategies)
            db.commit()
            print("Initial strategies added.")
        else:
            print("Strategies already exist, skipping initial data population.")
    except Exception as e:
        print(f"Error adding initial strategies: {e}")
        db.rollback()
    finally:
        db.close()

# Call these functions when the module is imported
create_db_tables()
add_initial_strategies()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

__all__ = ['Database', 'SessionLocal', 'init_db', 'db'] 