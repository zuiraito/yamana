#!/usr/bin/env python3
"""RTL-SDR spectrum collector: writes one FFT sweep per interval into TimescaleDB
(table sdr_spectrum) for the Grafana waterfall dashboard.

Each sweep is stored as one byte per FFT bin (bytea): 0 = DB_MIN dBFS, 255 = DB_MAX dBFS.

Secrets and the host come from the project's .env file (COLLECTOR_PASSWORD, TAILSCALE_IP),
same as simulate_aprs.py.

Install:  pip install "psycopg[binary]" pyrtlsdr numpy
Run:      python3 examples/sdr_waterfall.py --freq 145.0e6 --rate 2.4e6
Test without hardware:  python3 examples/sdr_waterfall.py --simulate
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

INSERT_SQL = """
INSERT INTO sdr_spectrum (time, center_freq_hz, sample_rate_hz, db_min, db_max, bins)
VALUES (%s, %s, %s, %s, %s, %s)
"""


def load_env(path):
    """Minimal .env loader. Variables already set in the environment win."""
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


def connect(args):
    return psycopg.connect(
        host=args.host, port=args.port, dbname=args.dbname,
        user=args.user, password=args.password, autocommit=True,
    )


class RtlSource:
    def __init__(self, args):
        from rtlsdr import RtlSdr  # imported lazily so --simulate works without it
        self.sdr = RtlSdr()
        self.sdr.sample_rate = args.rate
        self.sdr.center_freq = args.freq
        self.sdr.gain = "auto" if args.gain is None else args.gain
        if args.ppm:
            self.sdr.freq_correction = args.ppm
        self.nfft = args.bins
        self.n_avg = args.avg

    def read(self):
        # n_avg * nfft complex samples (read_samples wants a multiple of 256)
        samples = self.sdr.read_samples(self.n_avg * self.nfft)
        return samples.reshape(self.n_avg, self.nfft)

    def close(self):
        self.sdr.close()


class SimSource:
    """Noise plus a few drifting carriers, for testing the dashboard without hardware."""

    def __init__(self, args):
        self.nfft, self.n_avg, self.t = args.bins, args.avg, 0.0

    def read(self):
        n = self.nfft
        t = np.arange(self.n_avg * n) / 2.4e6
        x = (np.random.randn(t.size) + 1j * np.random.randn(t.size)) * 0.01
        for f, a in ((-0.6e6, 0.05), (0.1e6, 0.02), (0.5e6 + 50e3 * np.sin(self.t), 0.08)):
            x += a * np.exp(2j * np.pi * f * t)
        self.t += 0.3
        return x.reshape(self.n_avg, n)

    def close(self):
        pass


def spectrum_db(frames):
    """Averaged power spectrum in dBFS (complex float samples in [-1, 1]), DC centred."""
    n = frames.shape[1]
    win = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(frames * win, axis=1), axes=1)
    power = (np.abs(spec) ** 2).mean(axis=0) / (win.sum() ** 2 / 2.0)
    return 10.0 * np.log10(power + 1e-20)


def main():
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="path to the .env file")
    known, _ = pre.parse_known_args()
    if not load_env(known.env_file):
        print(f"warning: {known.env_file} not found, using the environment only", file=sys.stderr)

    p = argparse.ArgumentParser(description=__doc__, parents=[pre],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--freq", type=float, default=145.0e6, help="centre frequency in Hz")
    p.add_argument("--rate", type=float, default=2.4e6, help="sample rate in Hz")
    p.add_argument("--bins", type=int, default=1024, help="FFT bins per sweep (multiple of 256)")
    p.add_argument("--avg", type=int, default=100, help="FFT frames averaged per sweep")
    p.add_argument("--gain", type=float, default=None, help="tuner gain in dB (default: auto)")
    p.add_argument("--ppm", type=int, default=0, help="frequency correction in ppm")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between sweeps")
    p.add_argument("--db-min", type=float, default=-110.0, help="dBFS mapped to colour 0")
    p.add_argument("--db-max", type=float, default=-20.0, help="dBFS mapped to colour 255")
    p.add_argument("--simulate", action="store_true", help="synthetic data, no RTL-SDR needed")
    p.add_argument("--host", default=os.getenv("DB_HOST") or os.getenv("TAILSCALE_IP", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "5432")))
    p.add_argument("--dbname", default=os.getenv("DB_NAME", "yamana"))
    p.add_argument("--user", default=os.getenv("DB_USER", "collector"))
    p.add_argument("--password", default=os.getenv("COLLECTOR_PASSWORD"))
    args = p.parse_args()

    if not args.password:
        sys.exit("COLLECTOR_PASSWORD not found in .env or the environment.")
    if args.bins % 256:
        sys.exit("--bins must be a multiple of 256")

    src = SimSource(args) if args.simulate else RtlSource(args)
    conn = connect(args)
    print(f"{args.freq/1e6:.3f} MHz, {args.rate/1e6:.2f} MS/s, {args.bins} bins, "
          f"one sweep every {args.interval:g}s -> {args.host}:{args.port}/{args.dbname}")

    scale = 255.0 / (args.db_max - args.db_min)
    next_tick = time.monotonic()
    try:
        while True:
            db = spectrum_db(src.read())
            q = np.clip((db - args.db_min) * scale, 0, 255).astype(np.uint8)
            ts = datetime.now(timezone.utc)
            try:
                conn.execute(INSERT_SQL, (ts, int(args.freq), int(args.rate),
                                          args.db_min, args.db_max, q.tobytes()))
                print(f"{ts:%H:%M:%S} peak {db.max():6.1f} dBFS")
            except psycopg.OperationalError as e:
                print(f"DB error: {e}; reconnecting", file=sys.stderr)
                try:
                    conn = connect(args)
                except psycopg.OperationalError as e2:
                    print(f"reconnect failed: {e2}", file=sys.stderr)
            next_tick += args.interval
            time.sleep(max(0.0, next_tick - time.monotonic()))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        src.close()
        conn.close()


if __name__ == "__main__":
    main()
