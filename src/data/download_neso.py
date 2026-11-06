"""
Download NESO historic half-hourly demand data (one CSV per year).

Usage (from the project root):
    python -m src.data.download_neso                 # 2019 to latest
    python -m src.data.download_neso --start 2015    # from 2015
    python -m src.data.download_neso --force         # re-download existing files

The script asks the NESO CKAN API which yearly files exist, so it keeps
working when NESO adds a new year.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import requests

from src.config import NESO_API, NESO_HISTORIC_DEMAND_PACKAGE, RAW_DIR

OUT_DIR = RAW_DIR / "neso"
HEADERS = {"User-Agent": "uk-energy-intelligence/0.1 (portfolio project)"}
EXPECTED_COLUMNS = {"SETTLEMENT_DATE", "SETTLEMENT_PERIOD", "ND", "TSD"}


def list_yearly_resources() -> dict[int, str]:
    """Return {year: csv_url} for every yearly demand file on the portal."""
    resp = requests.get(
        f"{NESO_API}/package_show",
        params={"id": NESO_HISTORIC_DEMAND_PACKAGE},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    resources = resp.json()["result"]["resources"]

    years: dict[int, str] = {}
    for res in resources:
        if str(res.get("format", "")).upper() != "CSV":
            continue
        match = re.search(r"(19|20)\d{2}", f"{res.get('name', '')} {res.get('url', '')}")
        if match:
            years[int(match.group(0))] = res["url"]
    return dict(sorted(years.items()))


def download(url: str, dest: Path) -> None:
    with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(dest)


def quick_check(path: Path) -> None:
    df = pd.read_csv(path, nrows=5)
    cols = {c.upper() for c in df.columns}
    missing = EXPECTED_COLUMNS - cols
    status = "OK" if not missing else f"MISSING {sorted(missing)}"
    n_rows = sum(1 for _ in open(path, encoding="utf-8", errors="ignore")) - 1
    print(f"   {path.name}: {n_rows:,} rows, {len(df.columns)} columns, key columns {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=int, default=2019, help="first year to download")
    parser.add_argument("--end", type=int, default=None, help="last year (default: latest available)")
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Querying NESO Data Portal for available years...")
    available = list_yearly_resources()
    if not available:
        print("No yearly CSV files found - the portal layout may have changed.")
        return 1
    print(f"Available: {min(available)}-{max(available)}")

    end = args.end or max(available)
    for year, url in available.items():
        if not (args.start <= year <= end):
            continue
        dest = OUT_DIR / f"demanddata_{year}.csv"
        if dest.exists() and not args.force:
            print(f"-> {year}: already downloaded, skipping")
        else:
            print(f"-> {year}: downloading")
            download(url, dest)
        quick_check(dest)

    print(f"\nDone. Files saved in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
