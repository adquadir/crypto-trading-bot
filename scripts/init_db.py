# scripts/init_db.py

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

try:
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Sample table creation (edit as needed)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_logs (
            id SERIAL PRIMARY KEY,
            signal TEXT,
            symbol TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confidence TEXT,
            entry_price FLOAT,
            exit_price FLOAT,
            outcome TEXT,
            pnl FLOAT
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Database initialized successfully.")

except Exception as e:
    print(f"❌ Error initializing database: {e}")