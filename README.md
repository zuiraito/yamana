# Mission control and overview framework using Yamcs and Grafana
<img width="2324" height="1433" alt="image" src="https://github.com/user-attachments/assets/ed68d71d-72ae-4447-b170-39c6b1f70af8" />

# Project overview
## File structure
```
├── docker-compose.yml              | docker compse file
├── examples
│   ├── exampledata                 | example data set
│   └── simulate_aprs.py            | data source simulation
├── grafana
│   ├── dashboards
│   │   └── realtime.json           | HAB mission dashbord
│   └── provisioning
│       ├── dashboards
│       │   └── dashboards.yml      
│       └── datasources
│           └── timescale.yml       | data source configuration
├── initdb                          | timescaleDB
│   └── 001_init.sh
├── README.md
└── scr                             | scripts
    ├── drop_aprs_database.sh
    └── setpasswprds.sh
```
## Ports
| Port | Service     |
| ---- | ----------- |
| 3002 | grafana     |
| 5432 | timescaleDB |
| 8090 | yamcs       |

```
┌────────────────┐ TMTC ┌───────┐
│ Ground Station │ <--> │ Yamcs │
└────────────────┘      └───────┘
    \/ dump
┌─────────────┐
│ timescaleDB │
└─────────────┘
    \/ visualize
┌─────────┐
│ Grafana │
└─────────┘
```

# Getting started
1. Copy the and saturate the env file: `cp .example-env .env && nano .env`
2. Start the docker container `docker compose up`
3. Open grafana `yourip:3002`, login with `admin` and the password you set in the `.env` file and go onto the `Yamana – Live Telemetry` Dashboard
4. To test if everything is working run `python3 examples/simulate_aprs.py examples/exampledata/data.aprs`

## View a live waterfall
Go onto the Yamana - SDR Waterfall view and run 
```
python3 examples/sdr_waterfall.py --freq 145e6
```

# Todo
- [ ] Implement a waterfall panel using <canvas>
- [ ] Timeline view
- [ ] Documentation for multiple ground stations / data sources
Clearing the aprs_telemetry after a test
```
docker compose exec -T timescaledb psql -U postgres -d yamana -c "TRUNCATE aprs_telemetry;"
```

10 directories, 10 files
