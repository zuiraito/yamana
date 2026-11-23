#!/usr/bin/env bash
# Removes all aprs_telemetry 
docker compose exec -T timescaledb psql -U postgres -d yamana -c "TRUNCATE aprs_telemetry;"
