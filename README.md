# Mission control and overview framework using Yamcs and Grafana
<img width="2324" height="1433" alt="image" src="https://github.com/user-attachments/assets/ed68d71d-72ae-4447-b170-39c6b1f70af8" />

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
