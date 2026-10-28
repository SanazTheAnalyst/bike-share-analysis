import pandas as pd
import pytest

from src.bikeshare import add_features, clean_trips, haversine_km


def make_rides(rows):
    base = {
        "rideable_type": "classic_bike", "start_station_name": "A", "start_station_id": "1",
        "end_station_name": "B", "end_station_id": "2", "start_lat": 41.88, "start_lng": -87.63,
        "end_lat": 41.89, "end_lng": -87.62, "member_casual": "member",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_removes_duplicate_ride_ids():
    df = make_rides([
        {"ride_id": "x", "started_at": "2026-07-01 10:00:00", "ended_at": "2026-07-01 10:10:00"},
        {"ride_id": "x", "started_at": "2026-07-01 10:00:00", "ended_at": "2026-07-01 10:10:00"},
    ])
    clean, log = clean_trips(df)
    assert len(clean) == 1
    assert log["duplicates_removed"] == 1


@pytest.mark.parametrize("end, kept", [
    ("2026-07-01 10:00:30", False),   # under 1 minute
    ("2026-07-01 09:50:00", False),   # ends before it starts
    ("2026-07-02 11:00:00", False),   # over 24 hours
    ("2026-07-01 10:05:00", True),    # normal 5-minute ride
])
def test_filters_unrealistic_durations(end, kept):
    df = make_rides([{"ride_id": "r", "started_at": "2026-07-01 10:00:00", "ended_at": end}])
    clean, _ = clean_trips(df)
    assert (len(clean) == 1) is kept


def test_drops_unknown_rider_type():
    df = make_rides([{"ride_id": "r", "started_at": "2026-07-01 10:00:00",
                      "ended_at": "2026-07-01 10:05:00", "member_casual": "unknown"}])
    clean, _ = clean_trips(df)
    assert clean.empty


def test_haversine_known_distance():
    # Chicago Union Station to Navy Pier is about 3.1 km in a straight line
    assert haversine_km(41.8789, -87.6403, 41.8917, -87.6086) == pytest.approx(3.0, abs=0.2)


def test_features_weekend_and_round_trip():
    df = make_rides([{"ride_id": "r", "started_at": "2026-07-04 14:00:00",  # a Saturday
                      "ended_at": "2026-07-04 14:20:00", "end_station_name": "A"}])
    clean, _ = clean_trips(df)
    feat = add_features(clean)
    assert bool(feat.loc[0, "is_weekend"]) is True
    assert bool(feat.loc[0, "round_trip"]) is True
    assert feat.loc[0, "season"] == "Summer"
    assert feat.loc[0, "hour"] == 14


def test_keeps_only_rides_in_period():
    df = make_rides([
        {"ride_id": "a", "started_at": "2024-11-30 23:58:00", "ended_at": "2024-12-01 00:10:00"},
        {"ride_id": "b", "started_at": "2024-12-01 08:00:00", "ended_at": "2024-12-01 08:10:00"},
    ])
    clean, log = clean_trips(df, start="2024-12-01", end="2025-12-01")
    assert clean["ride_id"].tolist() == ["b"]
    assert log["outside_period_removed"] == 1
