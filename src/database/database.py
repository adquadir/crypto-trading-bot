import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy import create_engine, inspect, text, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session, relationship
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from dotenv import load_dotenv
from src.database.base import Base
from src.models.strategy import Strategy
from src.utils.config import load_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database configuration from environment variables
DB_USER = os.getenv("POSTGRES_USER", "trader")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "current_password")
DB_NAME = os.getenv("POSTGRES_DB", "crypto_trading")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# Construct database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    echo=os.getenv("DB_ECHO", "false").lower() == "true"
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create scoped session
db_session = scoped_session(SessionLocal)

# Database class for managing connections
class Database:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
        self.Base = Base

    def get_engine(self):
        return self.engine

    def get_session(self):
        return self.SessionLocal()

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def init_db(self):
        """Initialize database tables."""
        try:
            self.Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise e

    def check_connection(self):
        """Check database connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            return False

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
    update_db_schema()
    add_initial_strategies()


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
                    is_active=True,
                    type="technical",
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
                    is_active=True,
                    type="technical",
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
