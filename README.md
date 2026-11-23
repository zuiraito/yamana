# Getting started
1. Copy the `.example_env` to `.env` and saturate it.
2. Start the docker container `docker compose up`
3. Open grafana `yourip:3002`, login with `admin` and the password you set in the `.env` file and go onto the `Yamana – Live Telemetry` Dashboard
4. Run `python3 examples/simulate_aprs.py examples/exampledata/data.aprs`

Clearing the aprs_telemetry after a test
```
docker compose exec -T timescaledb psql -U postgres -d yamana -c "TRUNCATE aprs_telemetry;"
```
