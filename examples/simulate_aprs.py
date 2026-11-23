#!/usr/bin/env python3
"""Test data generator: replays APRS packets from a file into TimescaleDB.

The timestamps in the file are ignored. One packet is inserted every
INTERVAL seconds with the current time as its timestamp.

Secrets and the host come from the project's .env file (one directory above
this script): COLLECTOR_PASSWORD and TAILSCALE_IP. The database port is only
bound to the Tailscale IP, so "localhost" would not work on the server.

Install:  pip install "psycopg[binary]"
Run:      python3 examples/simulate_aprs.py ~/move-up-x-wesp/postflight/data.aprs --loop
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env(path):
    """Minimal .env loader (KEY=VALUE, '#' comments, optional quotes).
    Variables already set in the environment win."""
    path = Path(path)
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)
    return True

# A record starts with e.g. "2026-11-04 12:11:07 CET: "
RECORD_START = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \S+:\s")

PACKET = re.compile(
    r"(?P<src>[^>\s]+)>(?P<path>[^:\s]+):"
    r"[/@](?P<hms>\d{6})h"
    r"(?P<lat>\d{4}\.\d{2})(?P<ns>[NS])."          # '.' = symbol table
    r"(?P<lon>\d{5}\.\d{2})(?P<ew>[EW])."          # '.' = symbol code
    r"(?:(?P<course>\d{3})/(?P<speed>\d{3}))?"
    r"(?:/A=(?P<alt>-?\d{6}))?"
    r"\s*(?P<cnt>\d+)TxC\s+(?P<temp>-?\d+\.\d+)C"
    r"\s+(?P<press>\d+\.\d+)hPa\s+(?P<volt>\d+\.\d+)V"
    r"\s+(?P<sats>\d+)S\s*(?P<comment>.*)"
)

INSERT_SQL = """
INSERT INTO aprs_telemetry
  (time, callsign, latitude, longitude, altitude_m, speed_kmh, course_deg,
   frame_counter, temperature_c, pressure_hpa, voltage_v, satellites, comment)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def read_records(path):
    """Return the packet text of each record. Lines that do not start with a
    timestamp are continuations (the file contains hard-wrapped lines)."""
    records, current = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if RECORD_START.match(line):
                if current is not None:
                    records.append(current)
                current = RECORD_START.sub("", line, count=1)
            elif current is not None:
                current += line
    if current is not None:
        records.append(current)
    return records


def parse(text):
    m = PACKET.search(text)
    if not m:
        return None
    lat = int(m["lat"][:2]) + float(m["lat"][2:]) / 60
    lon = int(m["lon"][:3]) + float(m["lon"][3:]) / 60
    if m["ns"] == "S":
        lat = -lat
    if m["ew"] == "W":
        lon = -lon
    return {
        "callsign": m["src"],
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "altitude_m": round(int(m["alt"]) * 0.3048, 1) if m["alt"] else None,
        "speed_kmh": round(int(m["speed"]) * 1.852, 1) if m["speed"] else None,
        "course_deg": int(m["course"]) if m["course"] else None,
        "frame_counter": int(m["cnt"]),
        "temperature_c": float(m["temp"]),
        "pressure_hpa": float(m["press"]),
        "voltage_v": float(m["volt"]),
        "satellites": int(m["sats"]),
        "comment": m["comment"].strip(),
    }


def connect(args):
    return psycopg.connect(
        host=args.host, port=args.port, dbname=args.dbname,
        user=args.user, password=args.password, autocommit=True,
    )


def main():
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file", default=str(DEFAULT_ENV_FILE),
                     help="path to the .env file (default: ../.env)")
    known, _ = pre.parse_known_args()
    if not load_env(known.env_file):
        print(f"warning: {known.env_file} not found, using the environment only",
              file=sys.stderr)

    p = argparse.ArgumentParser(description=__doc__, parents=[pre],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", help="APRS log file")
    p.add_argument("--interval", type=float, default=5.0, help="seconds between inserts")
    p.add_argument("--loop", action="store_true", help="start over when the file ends")
    p.add_argument("--host", default=os.getenv("DB_HOST") or os.getenv("TAILSCALE_IP", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "5432")))
    p.add_argument("--dbname", default=os.getenv("DB_NAME", "yamana"))
    p.add_argument("--user", default=os.getenv("DB_USER", "collector"))
    p.add_argument("--password", default=os.getenv("COLLECTOR_PASSWORD"))
    args = p.parse_args()

    if not args.password:
        sys.exit("COLLECTOR_PASSWORD not found in .env or the environment.")

    rows = []
    for rec in read_records(args.file):
        d = parse(rec)
        if d is None:
            print(f"skipping unparsable record: {rec[:70]!r}", file=sys.stderr)
        else:
            rows.append(d)
    if not rows:
        sys.exit("No valid packets found in file.")
    print(f"Loaded {len(rows)} packets, inserting every {args.interval:g}s "
          f"into {args.host}:{args.port}/{args.dbname}")

    conn = connect(args)
    next_tick = time.monotonic()
    try:
        while True:
            for d in rows:
                ts = datetime.now(timezone.utc)
                values = (ts, d["callsign"], d["latitude"], d["longitude"],
                          d["altitude_m"], d["speed_kmh"], d["course_deg"],
                          d["frame_counter"], d["temperature_c"], d["pressure_hpa"],
                          d["voltage_v"], d["satellites"], d["comment"])
                try:
                    conn.execute(INSERT_SQL, values)
                    print(f"{ts:%H:%M:%S} inserted frame {d['frame_counter']} "
                          f"alt={d['altitude_m']} m T={d['temperature_c']} C")
                except psycopg.OperationalError as e:
                    print(f"DB error: {e}; reconnecting", file=sys.stderr)
                    try:
                        conn = connect(args)
                    except psycopg.OperationalError as e2:
                        print(f"reconnect failed: {e2}", file=sys.stderr)

                next_tick += args.interval
                time.sleep(max(0.0, next_tick - time.monotonic()))
            if not args.loop:
                break
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
