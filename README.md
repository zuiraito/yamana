
<img width="2841" height="1376" alt="image" src="https://github.com/user-attachments/assets/bc99b4dd-90c6-46a6-a1e6-c71492de0405" />

# Getting started
1. Copy the and saturate the env file: `cp .example-env .env && nano .env`
2. Start the docker container `docker compose up`
3. Open grafana `yourip:3002`, login with `admin` and the password you set in the `.env` file and go onto the `Yamana – Live Telemetry` Dashboard
4. To test if everything is working run `python3 examples/simulate_aprs.py examples/exampledata/data.aprs`

# Todo
- [ ] Implement a waterfall panel using <canvas>
- [ ] Timeline view
- [ ] Documentation for multiple ground stations / data sources
Clearing the aprs_telemetry after a test
```
docker compose exec -T timescaledb psql -U postgres -d yamana -c "TRUNCATE aprs_telemetry;"
```
