"""
STEP 1 — F1 Race Telemetry Producer
────────────────────────────────────────────────────────────────
Simulates real F1 car telemetry from the Canadian Grand Prix
and streams it to Amazon Kinesis in real time.

Each event represents one car completing one lap:
  - Lap time, sector splits, speed trap
  - Tyre compound + degradation
  - Position, gap to leader
  - Pit stop detection

This is EXACTLY the pattern AWS uses for real F1 races —
300+ sensors per car → Kinesis → Lambda → DynamoDB → TV graphics

Run: python 01_producer/race_producer.py
"""

import sys
import json
import random
import time
import boto3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    AWS_REGION, SQS_QUEUE_NAME,
    RACE_NAME, CIRCUIT, TOTAL_LAPS, CARS_ON_TRACK,
    validate
)

# ── 2026 F1 Grid ──────────────────────────────────────────────────────────────
DRIVERS = [
    {"car": 1,  "driver": "Max Verstappen",      "team": "Red Bull Racing"},
    {"car": 4,  "driver": "Lando Norris",         "team": "McLaren"},
    {"car": 16, "driver": "Charles Leclerc",      "team": "Ferrari"},
    {"car": 63, "driver": "George Russell",       "team": "Mercedes"},
    {"car": 44, "driver": "Lewis Hamilton",       "team": "Ferrari"},
    {"car": 81, "driver": "Oscar Piastri",        "team": "McLaren"},
    {"car": 55, "driver": "Carlos Sainz",         "team": "Williams"},
    {"car": 14, "driver": "Fernando Alonso",      "team": "Aston Martin"},
    {"car": 23, "driver": "Alexander Albon",      "team": "Williams"},
    {"car": 22, "driver": "Yuki Tsunoda",         "team": "Red Bull Racing"},
    {"car": 10, "driver": "Pierre Gasly",         "team": "Alpine"},
    {"car": 31, "driver": "Esteban Ocon",         "team": "Haas"},
    {"car": 77, "driver": "Valtteri Bottas",      "team": "Kick Sauber"},
    {"car": 24, "driver": "Zhou Guanyu",          "team": "Kick Sauber"},
    {"car": 18, "driver": "Lance Stroll",         "team": "Aston Martin"},
    {"car": 27, "driver": "Nico Hulkenberg",      "team": "Haas"},
    {"car": 3,  "driver": "Daniel Ricciardo",     "team": "Alpine"},
    {"car": 20, "driver": "Kevin Magnussen",      "team": "Haas"},
    {"car": 2,  "driver": "Logan Sargeant",       "team": "Williams"},
    {"car": 11, "driver": "Sergio Perez",         "team": "Red Bull Racing"},
]

TYRE_COMPOUNDS = ["soft", "medium", "hard"]

# Montreal Circuit Gilles Villeneuve lap time range (seconds)
# Real times: ~1:13-1:16 range
BASE_LAP_TIME = 74.5   # ~1:14.5 base lap time

# ── Telemetry generator ───────────────────────────────────────────────────────

class RaceState:
    """Tracks current race state for all 20 cars."""

    def __init__(self):
        self.cars = {}
        for i, d in enumerate(DRIVERS):
            self.cars[d["car"]] = {
                "driver":          d["driver"],
                "team":            d["team"],
                "car_number":      d["car"],
                "position":        i + 1,
                "current_lap":     0,
                "tyre_compound":   random.choice(["soft", "medium"]),
                "tyre_age_laps":   0,
                "total_time":      0.0,
                "pit_stops":       0,
                "is_retired":      False,
            }

    def generate_lap_event(self, car_number: int, lap: int) -> dict:
        """Generate realistic telemetry for one car completing one lap."""
        car = self.cars[car_number]
        if car["is_retired"]:
            return None

        # Tyre degradation effect
        tyre_deg = car["tyre_age_laps"] * 0.08   # 0.08 sec per lap of age
        compound_offset = {"soft": 0.0, "medium": 0.5, "hard": 1.2}[car["tyre_compound"]]

        # Base lap time with variation + degradation
        lap_time = (
            BASE_LAP_TIME
            + compound_offset
            + tyre_deg
            + random.uniform(-0.5, 0.8)     # natural variation
            + (0.3 if car["position"] > 10 else 0)  # traffic effect
        )

        # Sector splits (Montreal: S1 heavy braking, S2 twisty, S3 hairpin)
        s1 = lap_time * 0.28 + random.uniform(-0.1, 0.1)
        s2 = lap_time * 0.42 + random.uniform(-0.1, 0.1)
        s3 = lap_time - s1 - s2

        # Speed trap (main straight km/h — Montreal is a power circuit)
        speed_trap = random.uniform(315, 345) - (car["tyre_age_laps"] * 0.3)

        # Pit stop logic
        is_pit_lap = False
        if (car["tyre_age_laps"] >= 25 and car["pit_stops"] == 0 and lap > 15):
            if random.random() > 0.6:
                is_pit_lap = True
                lap_time += random.uniform(20, 24)   # pit stop time loss

        # Update car state
        car["tyre_age_laps"] += 1
        car["current_lap"] = lap
        car["total_time"] += lap_time

        if is_pit_lap:
            car["tyre_compound"] = random.choice(["medium", "hard"])
            car["tyre_age_laps"] = 0
            car["pit_stops"] += 1

        # Leader gap
        leader_time = min(
            c["total_time"] for c in self.cars.values()
            if not c["is_retired"] and c["current_lap"] == lap
        ) if any(
            c["current_lap"] == lap and not c["is_retired"]
            for c in self.cars.values()
        ) else car["total_time"]

        gap_to_leader = max(0.0, car["total_time"] - leader_time)

        return {
            # Race context
            "race_name":        RACE_NAME,
            "circuit":          CIRCUIT,
            "timestamp":        datetime.utcnow().isoformat(),
            "lap_number":       lap,

            # Car identity
            "car_number":       car_number,
            "driver":           car["driver"],
            "team":             car["team"],
            "position":         car["position"],

            # Lap performance
            "lap_time_sec":     round(lap_time, 3),
            "lap_time_str":     f"1:{int(lap_time-60):02d}.{int((lap_time%1)*1000):03d}",
            "sector_1_sec":     round(s1, 3),
            "sector_2_sec":     round(s2, 3),
            "sector_3_sec":     round(s3, 3),
            "speed_trap_kmh":   round(speed_trap, 1),

            # Tyre data
            "tyre_compound":    car["tyre_compound"],
            "tyre_age_laps":    car["tyre_age_laps"],
            "is_pit_lap":       is_pit_lap,
            "pit_stops_total":  car["pit_stops"],

            # Race position
            "gap_to_leader_sec": round(gap_to_leader, 3),
            "total_race_time":   round(car["total_time"], 3),

            # Powered by
            "powered_by":       "AWS Kinesis + Lambda + DynamoDB",
        }


# ── Producer ──────────────────────────────────────────────────────────────────

def create_sqs_queue():
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    try:
        r = sqs.create_queue(QueueName=SQS_QUEUE_NAME)
        print(f"Queue ready: {SQS_QUEUE_NAME}")
        return r["QueueUrl"]
    except Exception:
        r = sqs.get_queue_url(QueueName=SQS_QUEUE_NAME)
        print(f"Queue exists: {SQS_QUEUE_NAME}")
        return r["QueueUrl"]


def send_to_kinesis(client, event: dict) -> None:
    """Send one telemetry event to Kinesis."""
    client.put_record(
        StreamName=KINESIS_STREAM_NAME,
        Data=json.dumps(event).encode("utf-8"),
        PartitionKey=str(event["car_number"]),
    )


def run_race(laps: int = 10, delay: float = 0.1):
    """
    Simulate race telemetry for specified number of laps.
    delay: seconds between each car event (controls speed)
    """
    print("=" * 60)
    print(f"F1 TELEMETRY PRODUCER")
    print(f"Race   : {RACE_NAME}")
    print(f"Circuit: {CIRCUIT}")
    print(f"Laps   : {laps}")
    print(f"Cars   : {CARS_ON_TRACK}")
    print("=" * 60)

    queue_url = create_sqs_queue()

    sqs = boto3.client("sqs", region_name=AWS_REGION)
    state = RaceState()
    total_events = 0

    print("Streaming to SQS: " + SQS_QUEUE_NAME)
    print(f"{'Lap':>4} {'Car':>4} {'Driver':<22} {'Lap Time':>10} {'Tyre':<8} {'Pos':>4}")
    print("-" * 60)

    for lap in range(1, laps + 1):
        for driver in DRIVERS:
            event = state.generate_lap_event(driver["car"], lap)
            if event:
                sqs.send_message(QueueUrl=queue_url, MessageBody=__import__("json").dumps(event))
                total_events += 1
                print(
                    f"{lap:>4} "
                    f"{driver['car']:>4} "
                    f"{event['driver']:<22} "
                    f"{event['lap_time_str']:>10} "
                    f"{event['tyre_compound']:<8} "
                    f"{event['position']:>4}"
                )
                time.sleep(delay)

        print(f"  — Lap {lap} complete — {CARS_ON_TRACK} events sent —")

    print(f"\nRace simulation complete!")
    print(chr(10) + chr(82) + chr(97) + chr(99) + chr(101) + chr(32) + chr(115) + chr(105) + chr(109) + chr(117) + chr(108) + chr(97) + chr(116) + chr(105) + chr(111) + chr(110) + chr(32) + chr(99) + chr(111) + chr(109) + chr(112) + chr(108) + chr(101) + chr(116) + chr(101))
    print(str(total_events) + chr(32) + chr(101) + chr(118) + chr(101) + chr(110) + chr(116) + chr(115) + chr(32) + chr(115) + chr(101) + chr(110) + chr(116))
    print(SQS_QUEUE_NAME)


if __name__ == "__main__":
    validate()
    # Run 5 laps by default (change to TOTAL_LAPS for full race)
    run_race(laps=5, delay=0.05)
