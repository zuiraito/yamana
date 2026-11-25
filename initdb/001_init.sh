#!/bin/bash
# Runs once, on first start of an empty database volume.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v collector_pw="$COLLECTOR_PASSWORD" \
  -v grafana_pw="$GRAFANA_RO_PASSWORD" <<'SQL'

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE aprs_telemetry (
  time           timestamptz NOT NULL,
  callsign       text        NOT NULL,
  latitude       double precision,
  longitude      double precision,
  altitude_m     double precision,
  speed_kmh      double precision,
  course_deg     int,
  frame_counter  int,
  temperature_c  double precision,
  pressure_hpa   double precision,
  voltage_v      double precision,
  satellites     int,
  comment        text
);
SELECT create_hypertable('aprs_telemetry', 'time');
GRANT INSERT ON aprs_telemetry TO collector;
GRANT SELECT ON aprs_telemetry TO grafana_ro;

-- SDR waterfall: one row per sweep. bins = uint8 power values (bytea), one byte per FFT bin,
-- scaled linearly so 0 = db_min and 255 = db_max (dBFS).
CREATE TABLE sdr_spectrum (
  time           timestamptz NOT NULL,
  center_freq_hz bigint      NOT NULL,
  sample_rate_hz integer     NOT NULL,
  db_min         real        NOT NULL,
  db_max         real        NOT NULL,
  bins           bytea       NOT NULL
);
SELECT create_hypertable('sdr_spectrum', 'time');
SELECT add_retention_policy('sdr_spectrum', INTERVAL '7 days');
GRANT INSERT ON sdr_spectrum TO collector;
GRANT SELECT ON sdr_spectrum TO grafana_ro;
SQL
