from sqlalchemy import create_engine, inspect, text, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session
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

# Create scoped session
db_session = scoped_session(SessionLocal)

# Create metadata
metadata = MetaData()

class Database:
    """Database management class for the trading bot."""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
        self.metadata = metadata
    
    def get_session(self):
        return self.SessionLocal()
    
    def init_db(self) -> None:
        """Initialize the database and create tables."""
        try:
            # Create tables
            Base.metadata.create_all(bind=self.engine)
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

    def close(self):
        """Close the database connection."""
        try:
            self.engine.dispose()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            raise

# Initialize database
db = Database()

async def init_db() -> None:
    """Initialize the database."""
    await db.init_db()

def update_db_schema():
    """Update the database schema by creating any missing tables."""
    try:
        # Create any missing tables using the imported Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema updated successfully")
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