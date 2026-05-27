"""
config.py — Shared configuration for F1 Telemetry Pipeline
All scripts import from here. Edit values in .env file only.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── AWS ───────────────────────────────────────────────────────────────────────
AWS_REGION          = os.getenv("AWS_REGION", "ca-central-1")
AWS_ACCOUNT_ID      = os.getenv("AWS_ACCOUNT_ID", "")

# ── Kinesis ───────────────────────────────────────────────────────────────────
SQS_QUEUE_NAME = os.getenv("SQS_QUEUE_NAME", "f1-telemetry-queue")

# ── DynamoDB ──────────────────────────────────────────────────────────────────
DYNAMO_TABLE_NAME   = os.getenv("DYNAMO_TABLE_NAME", "f1-race-telemetry")

# ── Lambda ────────────────────────────────────────────────────────────────────
LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "f1-telemetry-processor")

# ── Race simulation ───────────────────────────────────────────────────────────
RACE_NAME           = "Canadian Grand Prix 2026"
CIRCUIT             = "Circuit Gilles Villeneuve, Montreal"
TOTAL_LAPS          = 70
CARS_ON_TRACK       = 20

# ── Project paths ─────────────────────────────────────────────────────────────
ROOT_DIR            = Path(__file__).parent
ARTIFACTS_DIR       = ROOT_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


def validate():
    """Verify all required environment variables are set."""
    required = {
        "AWS_REGION":     AWS_REGION,
        "AWS_ACCOUNT_ID": AWS_ACCOUNT_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing: {', '.join(missing)} — fill in .env file"
        )
    print(f"Config OK")
    print(f"  Region  : {AWS_REGION}")
    print(f"  Queue   : {SQS_QUEUE_NAME}")
    print(f"  Table   : {DYNAMO_TABLE_NAME}")
    print(f"  Race    : {RACE_NAME}")


if __name__ == "__main__":
    validate()
