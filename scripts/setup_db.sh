#!/bin/bash
source .env
DB_USER=${POSTGRES_USER:-trader}
DB_PASS=${POSTGRES_PASSWORD:-current_password}
DB_NAME=${POSTGRES_DB:-crypto_trading}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}
PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME << EOF
ALTER TABLE trades ADD COLUMN IF NOT EXISTS leverage FLOAT DEFAULT 1.0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS pnl_pct FLOAT;
EOF
echo "Database schema updated successfully"
