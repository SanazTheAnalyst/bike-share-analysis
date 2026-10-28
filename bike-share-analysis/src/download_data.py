"""Download monthly Divvy trip data into the data/ folder.

Usage:
    python src/download_data.py            (downloads Dec 2024 to Nov 2025)
"""

import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://divvy-tripdata.s3.amazonaws.com/{month}-divvy-tripdata.zip"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def download(month: str) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    target = DATA_DIR / f"{month}-divvy-tripdata.zip"
    if target.exists():
        print(f"{target.name} already downloaded")
        return target
    print(f"Downloading {target.name} ...")
    urllib.request.urlretrieve(BASE_URL.format(month=month), target)
    return target


if __name__ == "__main__":
    months = sys.argv[1:] or ["202412"] + [f"2025{m:02d}" for m in range(1, 12)]
    for m in months:
        download(m)
