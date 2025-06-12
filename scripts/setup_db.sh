#!/bin/bash

# Get the absolute path of the project root
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Load .env variables
set -a
source "$PROJECT_ROOT/.env"
set +a

# Parse DATABASE_URL
# Example: postgresql://user:password@localhost:5432/dbname
regex='postgresql:\/\/([^:]+):([^@]+)@[^:]+:\d+\/([^/]+)'
if [[ $DATABASE_URL =~ $regex ]]; then
  DB_USER="${BASH_REMATCH[1]}"
  DB_PASS="${BASH_REMATCH[2]}"
  DB_NAME="${BASH_REMATCH[3]}"
else
  echo "Could not parse DATABASE_URL from .env"
  exit 1
fi

# Create database and user
sudo -u postgres psql << EOF
DO
$do$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = '$DB_USER') THEN
      CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
   END IF;
END
$do$;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
EOF

echo "Database and user created successfully!"
