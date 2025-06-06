from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from .models import Base, Strategy # Import Base and Strategy
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database URL from environment variable or use default SQLite
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./trading_bot.db"
)

# Create SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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