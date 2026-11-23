#!/bin/bash
# Runs once, on first start of an empty database volume.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v collector_pw="$COLLECTOR_PASSWORD" \
  -v grafana_pw="$GRAFANA_RO_PASSWORD" <<'SQL'

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE telemetry (
  ts                  timestamptz NOT NULL,
  device              text        NOT NULL,
  -- battery (NULL on machines without one)
  battery_pct         real,
  battery_status      text,        -- Charging / Discharging / Full / Not charging
  battery_health_pct  real,        -- full-charge capacity / design capacity * 100
  battery_cycles      integer,
  -- storage (root filesystem)
  disk_total_bytes    bigint,
  disk_used_bytes     bigint,
  -- misc
  mem_used_pct        real,
  load1               real,
  network_name        text,        -- Wi-Fi SSID, else connection name, else interface
  -- (device, ts) also makes retries idempotent: re-sent samples are ignored
  PRIMARY KEY (device, ts)
);

SELECT create_hypertable('telemetry', by_range('ts', INTERVAL '7 days'));

ALTER TABLE telemetry SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'device',
  timescaledb.compress_orderby   = 'ts DESC'
);
SELECT add_compression_policy('telemetry', INTERVAL '14 days');

-- Least privilege: collectors can only insert, Grafana can only read.
CREATE ROLE collector LOGIN PASSWORD :'collector_pw';
CREATE ROLE grafana_ro LOGIN PASSWORD :'grafana_pw';
GRANT CONNECT ON DATABASE telemetry TO collector, grafana_ro;
GRANT USAGE ON SCHEMA public TO collector, grafana_ro;
GRANT INSERT ON telemetry TO collector;
GRANT SELECT ON telemetry TO grafana_ro;
SQL

