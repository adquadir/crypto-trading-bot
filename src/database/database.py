import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError

from .base import Base
from src.models.strategy import Strategy

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


class Database:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.engine = engine
            self.SessionLocal = SessionLocal
            self._setup_database()
            self._initialized = True

    def _setup_database(self):
        """Set up database connection and create tables."""
        try:
            # Create tables using the imported Base
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    def get_session(self):
        """Get a new database session."""
        return self.SessionLocal()

    def close(self):
        """Close the database connection."""
        try:
            self.engine.dispose()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            raise

    def get_strategy(self, strategy_id: int):
        """Get a strategy by ID."""
        with self.get_session() as db:
            return db.query(Strategy).filter(Strategy.id == strategy_id).first()

    def get_all_strategies(self):
        """Get all strategies."""
        with self.get_session() as db:
            return db.query(Strategy).all()

    def add_initial_strategies(self):
        """Add initial strategies to the database if they don't exist."""
        try:
            session = self.get_session()
            
            # Check if strategies already exist
            if session.query(Strategy).count() > 0:
                logger.info("Strategies already exist in database")
                return
            
            # Add default strategies
            strategies = [
                Strategy(
                    name="MACD",
                    description="Moving Average Convergence Divergence Strategy",
                    type="technical",
                    parameters={
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9
                    }
                ),
                Strategy(
                    name="RSI",
                    description="Relative Strength Index Strategy",
                    type="technical",
                    parameters={
                        "period": 14,
                        "overbought": 70,
                        "oversold": 30
                    }
                ),
                Strategy(
                    name="Bollinger Bands",
                    description="Bollinger Bands Strategy",
                    type="technical",
                    parameters={
                        "period": 20,
                        "std_dev": 2
                    }
                )
            ]
            
            session.add_all(strategies)
            session.commit()
            logger.info("Added initial strategies to database")
            
        except SQLAlchemyError as e:
            logger.error(f"Error adding initial strategies: {e}")
            session.rollback()
            raise
        finally:
            session.close()


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


def create_db_tables():
    """Create database tables."""
    update_db_schema()


def add_initial_strategies():
    """Add initial strategies if none exist."""
    db = SessionLocal()
    try:
        # Check if strategies already exist
        if db.query(Strategy).count() == 0:
            logger.info("Adding initial strategies...")
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
            logger.info("Initial strategies added.")
        else:
            logger.info("Strategies already exist, skipping initial data population.")
    except Exception as e:
        logger.error(f"Error adding initial strategies: {e}")
        db.rollback()
    finally:
        db.close()


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Call these functions when the module is imported
create_db_tables()
add_initial_strategies()

__all__ = ['Database', 'SessionLocal', 'init_db', 'db'] 