"""
STEP 2 — Lambda Consumer (Kinesis → DynamoDB)
────────────────────────────────────────────────────────────────
This Lambda function is triggered by Kinesis stream events.
Processes each F1 telemetry event and stores in DynamoDB.

Deployed as AWS Lambda with Kinesis trigger.
Also runnable locally to test processing logic.

Run locally: python 02_consumer/lambda_consumer.py
"""

import sys
import json
import base64
import boto3
from pathlib import Path
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import AWS_REGION, DYNAMO_TABLE_NAME, SQS_QUEUE_NAME


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    AWS Lambda entry point — triggered by Kinesis stream.
    Processes each telemetry record and writes to DynamoDB.
    """
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMO_TABLE_NAME)

    processed = 0
    errors = 0

    for record in event["Records"]:
        try:
            # Decode base64 Kinesis data
            payload = base64.b64decode(record["kinesis"]["data"]).decode("utf-8")
            telemetry = json.loads(payload)

            # Write to DynamoDB
            store_telemetry(table, telemetry)
            processed += 1

        except Exception as e:
            print(f"Error processing record: {e}")
            errors += 1

    print(f"Processed: {processed} | Errors: {errors}")
    return {"processed": processed, "errors": errors}


def store_telemetry(table, event: dict) -> None:
    """Store one telemetry event in DynamoDB."""

    # Convert floats to Decimal for DynamoDB
    def to_decimal(v):
        if isinstance(v, float):
            return Decimal(str(round(v, 3)))
        return v

    item = {k: to_decimal(v) for k, v in event.items()}

    # Composite key: car_number + lap_number
    item["pk"] = f"CAR#{event['car_number']}#LAP#{event['lap_number']}"
    item["sk"] = event["timestamp"]

    table.put_item(Item=item)


# ── Local test mode ───────────────────────────────────────────────────────────

def test_locally():
    import json
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMO_TABLE_NAME)
    queue_url = sqs.get_queue_url(QueueName=SQS_QUEUE_NAME)["QueueUrl"]
    total = 0
    print("Reading SQS: " + SQS_QUEUE_NAME)
    print("Writing DynamoDB: " + DYNAMO_TABLE_NAME)
    while True:
        resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=1)
        msgs = resp.get("Messages", [])
        if not msgs:
            break
        for msg in msgs:
            event = json.loads(msg["Body"])
            store_telemetry(table, event)
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
            total += 1
            print("Stored: " + event["driver"] + " Lap" + str(event["lap_number"]) + " " + event["lap_time_str"])
    print("Total stored: " + str(total))
    print("Next: python 03_storage/dynamodb_setup.py")


if __name__ == '__main__':
    test_locally()
