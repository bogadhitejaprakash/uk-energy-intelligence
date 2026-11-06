"""
Download NESO's historic day-ahead demand forecasts (the industry benchmark).

Usage:
    python -m src.data.download_neso_forecasts
    python -m src.data.download_neso_forecasts --force   # refresh (datasets update monthly)

Files saved to data/raw/neso_forecasts/<name>.csv
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd
import requests

from src.config import NESO_API, NESO_FORECAST_RESOURCES, RAW_DIR
from src.data.download_neso import HEADERS, download

OUT_DIR = RAW_DIR / "neso_forecasts"


def resource_url(resource_id: str) -> str:
    """Ask the CKAN API for the current download URL of a resource."""
    r = requests.get(f"{NESO_API}/resource_show", params={"id": resource_id},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()["result"]["url"]


def describe(path) -> None:
    df = pd.read_csv(path, low_memory=False)
    print(f"   {len(df):,} rows x {len(df.columns)} columns")
    print(f"   columns: {list(df.columns)}")
    print(df.head(3).to_string(index=False, max_colwidth=25))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, resource_id in NESO_FORECAST_RESOURCES.items():
        dest = OUT_DIR / f"{name}.csv"
        if dest.exists() and not args.force:
            print(f"-> {name}: already downloaded, skipping")
        else:
            print(f"-> {name}: downloading")
            download(resource_url(resource_id), dest)
        describe(dest)
        print()
    print(f"Done. Files saved in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
