"""Load, clean and analyse Divvy bike-share trip data.

Business question: how do annual members and casual riders use the bikes
differently, and how could that help turn casual riders into members?
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RAW_COLUMNS = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "end_station_name",
    "start_lat", "start_lng", "end_lat", "end_lng", "member_casual",
]
CATEGORY_COLUMNS = ["rideable_type", "start_station_name", "end_station_name", "member_casual"]

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SEASONS = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
           6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}

MIN_MINUTES = 1        # shorter rides are usually false starts or re-docking
MAX_MINUTES = 24 * 60  # longer rides are usually lost or stolen bikes


def load_trips(data_dir: str | Path) -> pd.DataFrame:
    """Read every monthly Divvy file (.zip or .csv) in data_dir into one table."""
    files = sorted(Path(data_dir).glob("*divvy-tripdata.*"))
    files = [f for f in files if f.suffix in {".zip", ".csv"}]
    if not files:
        raise FileNotFoundError(f"No Divvy files found in {data_dir}. Run src/download_data.py first.")
    frames = [_read_file(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    return df.astype({c: "category" for c in CATEGORY_COLUMNS})


def _read_file(path: Path) -> pd.DataFrame:
    """Read one monthly file. Zips made on a Mac also contain __MACOSX files, which are skipped."""
    if path.suffix == ".csv":
        return pd.read_csv(path, usecols=RAW_COLUMNS)
    with zipfile.ZipFile(path) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX"))
        with z.open(csv_name) as f:
            return pd.read_csv(f, usecols=RAW_COLUMNS)


def clean_trips(df: pd.DataFrame, start: str | None = None, end: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Remove duplicate, broken and unrealistic rides. Returns the clean table and a log of what was removed.

    start/end (e.g. "2024-12-01", "2025-12-01") keep only rides that started in that period,
    because each monthly file also holds a few rides from the edge of the previous month.
    """
    log = {"raw_rows": len(df)}

    df = df.drop_duplicates(subset="ride_id")
    log["duplicates_removed"] = log["raw_rows"] - len(df)

    df = df.assign(
        started_at=pd.to_datetime(df["started_at"], format="ISO8601"),
        ended_at=pd.to_datetime(df["ended_at"], format="ISO8601"),
    )
    df = df[df["member_casual"].isin(["member", "casual"])]

    before = len(df)
    if start:
        df = df[df["started_at"] >= pd.Timestamp(start)]
    if end:
        df = df[df["started_at"] < pd.Timestamp(end)]
    log["outside_period_removed"] = before - len(df)

    df = df.assign(ride_minutes=(df["ended_at"] - df["started_at"]).dt.total_seconds() / 60)
    before = len(df)
    df = df[df["ride_minutes"].between(MIN_MINUTES, MAX_MINUTES)]
    log["bad_duration_removed"] = before - len(df)

    log["clean_rows"] = len(df)
    log["share_kept"] = round(len(df) / log["raw_rows"], 4)
    return df.reset_index(drop=True), log


def haversine_km(lat1, lng1, lat2, lng2):
    """Straight-line distance in km between two points on Earth."""
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add the time and distance columns used in the analysis."""
    start = df["started_at"]
    start_name = df["start_station_name"].astype("string")
    same_station = (start_name == df["end_station_name"].astype("string")).fillna(False)
    return df.assign(
        day_of_week=pd.Categorical(start.dt.day_name(), categories=DAY_ORDER, ordered=True),
        is_weekend=start.dt.dayofweek >= 5,
        hour=start.dt.hour,
        month=start.dt.to_period("M").astype(str),
        season=start.dt.month.map(SEASONS),
        distance_km=haversine_km(df["start_lat"], df["start_lng"], df["end_lat"], df["end_lng"]),
        round_trip=same_station,
    )


def summarise(df: pd.DataFrame) -> dict:
    """Headline numbers comparing members and casual riders."""
    by = df.groupby("member_casual")
    weekend_share = by["is_weekend"].mean()
    out = {
        "rides": by.size().to_dict(),
        "ride_share": (by.size() / len(df)).round(4).to_dict(),
        "median_minutes": by["ride_minutes"].median().round(1).to_dict(),
        "mean_minutes": by["ride_minutes"].mean().round(1).to_dict(),
        "median_distance_km": by["distance_km"].median().round(2).to_dict(),
        "weekend_share": weekend_share.round(4).to_dict(),
        "round_trip_share": by["round_trip"].mean().round(4).to_dict(),
        "rides_over_30_min_share": by["ride_minutes"].apply(lambda s: (s > 30).mean()).round(4).to_dict(),
        "busiest_day": by["day_of_week"].agg(lambda s: s.value_counts().idxmax()).to_dict(),
        "busiest_hour": by["hour"].agg(lambda s: int(s.value_counts().idxmax())).to_dict(),
        "bike_type_share": (df.groupby(["member_casual", "rideable_type"]).size()
                            / by.size()).round(4).unstack().to_dict(orient="index"),
        "summer_share": by["season"].apply(lambda s: (s == "Summer").mean()).round(4).to_dict(),
        "median_speed_kmh": (df["distance_km"] / (df["ride_minutes"] / 60)).groupby(df["member_casual"],
                             observed=True).median().round(1).to_dict(),
        "rides_by_month": df.groupby(["month", "member_casual"], observed=True).size().unstack().to_dict(),
        "months": sorted(df["month"].unique().tolist()),
    }
    return out


def top_casual_stations(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Stations where casual riders start most often: the best places for member marketing."""
    casual = df[(df["member_casual"] == "casual") & df["start_station_name"].notna()]
    counts = casual["start_station_name"].value_counts().head(n)
    return counts.rename_axis("start_station").reset_index(name="casual_rides")
