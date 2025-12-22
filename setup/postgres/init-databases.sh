#!/bin/sh
# Create databases and users for all services
# This script is executed by postgres on container startup

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create dagster user and database for orchestration storage
    CREATE USER dagster WITH PASSWORD '$DAGSTER_DB_PASSWORD';
    CREATE DATABASE dagster OWNER dagster;
    GRANT ALL PRIVILEGES ON DATABASE dagster TO dagster;

    -- Create app user and database for the main application
    CREATE USER app WITH PASSWORD '$APP_DB_PASSWORD';
    CREATE DATABASE personal_ai_automation OWNER app;
    GRANT ALL PRIVILEGES ON DATABASE personal_ai_automation TO app;

    -- Create glitchtip user and database for error tracking
    CREATE USER glitchtip WITH PASSWORD '$GLITCHTIP_DB_PASSWORD';
    CREATE DATABASE glitchtip OWNER glitchtip;
    GRANT ALL PRIVILEGES ON DATABASE glitchtip TO glitchtip;
EOSQL

echo "Databases created: dagster, personal_ai_automation, glitchtip"
