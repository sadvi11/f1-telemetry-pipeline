"""
STEP 3 — DynamoDB Setup + Race Analytics
────────────────────────────────────────────────────────────────
Creates the DynamoDB table and provides race analytics queries:
  - Fastest lap overall
  - Race standings (current positions)
  - Tyre strategy by driver
  - Sector time comparisons

Run: python 03_storage/dynamodb_setup.py
"""

import sys
import boto3
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import AWS_REGION, DYNAMO_TABLE_NAME, validate


def create_table():
    """Create DynamoDB table for F1 telemetry storage."""
    client = boto3.client("dynamodb", region_name=AWS_REGION)

    try:
        client.create_table(
            TableName=DYNAMO_TABLE_NAME,
            KeySchema=[
                {"AttributeName": "pk",  "KeyType": "HASH"},
                {"AttributeName": "sk",  "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk",         "AttributeType": "S"},
                {"AttributeName": "sk",         "AttributeType": "S"},
                {"AttributeName": "car_number", "AttributeType": "N"},
                {"AttributeName": "lap_number", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "car-lap-index",
                    "KeySchema": [
                        {"AttributeName": "car_number", "KeyType": "HASH"},
                        {"AttributeName": "lap_number",  "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
            Tags=[
                {"Key": "Project",     "Value": "F1TelemetryPipeline"},
                {"Key": "Race",        "Value": "CanadianGP2026"},
                {"Key": "ManagedBy",   "Value": "f1-telemetry-pipeline"},
            ],
        )
        print(f"Creating table: {DYNAMO_TABLE_NAME}")
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=DYNAMO_TABLE_NAME)
        print(f"Table ACTIVE: {DYNAMO_TABLE_NAME}")

    except client.exceptions.ResourceInUseException:
        print(f"Table already exists: {DYNAMO_TABLE_NAME}")


def get_race_standings(table) -> list:
    """Query current race standings — all drivers sorted by total time."""
    response = table.scan(
        FilterExpression="attribute_exists(total_race_time)",
        ProjectionExpression="driver, team, #pos, lap_number, total_race_time, tyre_compound, pit_stops_total",
        ExpressionAttributeNames={"#pos": "position"},
    )
    items = response.get("Items", [])

    # Get latest lap per driver
    latest = {}
    for item in items:
        driver = item["driver"]
        lap = int(item.get("lap_number", 0))
        if driver not in latest or lap > int(latest[driver].get("lap_number", 0)):
            latest[driver] = item

    return sorted(latest.values(), key=lambda x: float(x.get("total_race_time", 999999)))


def get_fastest_laps(table, limit: int = 5) -> list:
    """Get the fastest individual laps of the race."""
    response = table.scan(
        FilterExpression="attribute_exists(lap_time_sec)",
        ProjectionExpression="driver, team, lap_number, lap_time_str, lap_time_sec, tyre_compound",
    )
    items = response.get("Items", [])
    return sorted(items, key=lambda x: float(x.get("lap_time_sec", 999)))[:limit]


def get_tyre_strategy(table, driver_name: str) -> list:
    """Get full tyre strategy for one driver."""
    response = table.scan(
        FilterExpression="driver = :d",
        ExpressionAttributeValues={":d": driver_name},
        ProjectionExpression="lap_number, tyre_compound, tyre_age_laps, is_pit_lap, lap_time_str",
    )
    items = response.get("Items", [])
    return sorted(items, key=lambda x: int(x.get("lap_number", 0)))


def run_analytics():
    """Run race analytics and print results."""
    print("=" * 60)
    print("STEP 3 — F1 Race Analytics")
    print("=" * 60)

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMO_TABLE_NAME)

    # Race standings
    print("\n🏎️  RACE STANDINGS")
    print(f"{'Pos':>4} {'Driver':<22} {'Team':<20} {'Lap':>4} {'Tyre':<8} {'Stops':>5}")
    print("-" * 70)
    standings = get_race_standings(table)
    for i, car in enumerate(standings[:10], 1):
        print(
            f"{i:>4} "
            f"{car.get('driver', ''):<22} "
            f"{car.get('team', ''):<20} "
            f"{car.get('lap_number', 0):>4} "
            f"{car.get('tyre_compound', ''):<8} "
            f"{car.get('pit_stops_total', 0):>5}"
        )

    # Fastest laps
    print("\n⚡ TOP 5 FASTEST LAPS")
    print(f"{'Driver':<22} {'Team':<20} {'Lap':>4} {'Time':>10} {'Tyre':<8}")
    print("-" * 70)
    fastest = get_fastest_laps(table)
    for lap in fastest:
        print(
            f"{lap.get('driver', ''):<22} "
            f"{lap.get('team', ''):<20} "
            f"{lap.get('lap_number', 0):>4} "
            f"{lap.get('lap_time_str', ''):>10} "
            f"{lap.get('tyre_compound', ''):<8}"
        )

    print(f"\nNext: python 04_dashboard/cloudwatch_dashboard.py")


if __name__ == "__main__":
    validate()
    create_table()
    run_analytics()
