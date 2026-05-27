"""Tests for F1 Telemetry Pipeline"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_defaults():
    import config
    assert config.KINESIS_STREAM_NAME == "f1-telemetry-stream"
    assert config.DYNAMO_TABLE_NAME == "f1-race-telemetry"
    assert config.CARS_ON_TRACK == 20
    assert config.TOTAL_LAPS == 70


def test_race_produces_20_drivers():
    from config import DRIVERS
    assert len(DRIVERS) == 20


def test_lap_event_has_required_fields():
    sys.path.insert(0, str(Path(__file__).parent.parent / "01_producer"))
    from race_producer import RaceState
    state = RaceState()
    event = state.generate_lap_event(1, 1)
    assert event is not None
    required = [
        "driver", "car_number", "lap_number", "lap_time_sec",
        "lap_time_str", "tyre_compound", "position",
        "sector_1_sec", "sector_2_sec", "sector_3_sec",
        "speed_trap_kmh", "gap_to_leader_sec", "powered_by"
    ]
    for field in required:
        assert field in event, f"Missing field: {field}"


def test_lap_time_is_realistic():
    sys.path.insert(0, str(Path(__file__).parent.parent / "01_producer"))
    from race_producer import RaceState
    state = RaceState()
    event = state.generate_lap_event(1, 1)
    assert 65 < event["lap_time_sec"] < 90, "Lap time out of realistic range"


def test_tyre_compound_is_valid():
    sys.path.insert(0, str(Path(__file__).parent.parent / "01_producer"))
    from race_producer import RaceState, TYRE_COMPOUNDS
    state = RaceState()
    event = state.generate_lap_event(1, 1)
    assert event["tyre_compound"] in TYRE_COMPOUNDS


def test_speed_trap_is_realistic():
    sys.path.insert(0, str(Path(__file__).parent.parent / "01_producer"))
    from race_producer import RaceState
    state = RaceState()
    event = state.generate_lap_event(1, 1)
    assert 280 < event["speed_trap_kmh"] < 360, "Speed trap out of range"


def test_powered_by_aws():
    sys.path.insert(0, str(Path(__file__).parent.parent / "01_producer"))
    from race_producer import RaceState
    state = RaceState()
    event = state.generate_lap_event(1, 1)
    assert "AWS" in event["powered_by"]
