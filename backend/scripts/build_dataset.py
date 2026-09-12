"""Build the point-in-time dataset and load it into the database.

    python -m scripts.build_dataset [--reset] [--live]

--reset  drop and recreate every table first
--live   attempt the PSX/SBP scrapers before falling back to the simulator
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from app.config import settings
from app.db import repository as repo
from app.db.models import init_db
from app.etl import ratios as ratio_etl
from app.ingest.simulator import PSXSimulator


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop existing tables")
    ap.add_argument("--live", action="store_true", help="try live PSX scrapers first")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    print(f"database   : {settings.database_url}")
    init_db(drop=args.reset)
    if args.reset:
        print("schema     : dropped and recreated")

    source = "simulated"
    if args.live:
        from app.ingest.psx_client import fetch_all
        live = fetch_all()
        if live is not None:
            source = "psx-live"
            data = live
        else:
            print("live fetch : unavailable, falling back to the simulator")
            data = None
    else:
        data = None

    if data is None:
        print(f"simulating : {settings.history_start} to {settings.history_end}")
        sim = PSXSimulator(seed=args.seed)
        data = sim.run()

    n = repo.save_companies(data.get("shares"))
    print(f"companies  : {n}")
    n = repo.save_macro(data["macro"])
    print(f"macro      : {n} monthly observations")
    n = repo.save_statements(data["statements"])
    print(f"statements : {n} quarterly filings ({source})")
    n = repo.save_prices(data["prices"])
    print(f"prices     : {n} daily bars")
    n = repo.save_index(data["index"])
    print(f"index      : {n} KSE-100 closes")

    print("ratios     : computing TTM ratios and sector z-scores ...")
    r = ratio_etl.run(data["statements"])
    n = repo.save_ratios(r)
    print(f"ratios     : {n} rows, {len([c for c in r.columns if c.startswith('z_')])} sector z-scores")

    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
