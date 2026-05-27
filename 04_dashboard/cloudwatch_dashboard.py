"""
STEP 4 — CloudWatch Dashboard + Custom Metrics
────────────────────────────────────────────────────────────────
Creates a CloudWatch dashboard showing live F1 race metrics:
  - Events per second (Kinesis throughput)
  - Average lap time trend
  - Pit stop count
  - Events processed by Lambda

This is exactly what F1 engineers watch during a real race
on AWS to monitor their data pipeline health.

Run: python 04_dashboard/cloudwatch_dashboard.py
"""

import sys
import json
import boto3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    AWS_REGION, SQS_QUEUE_NAME,
    DYNAMO_TABLE_NAME, RACE_NAME, validate
)


def put_custom_metric(cw_client, metric_name: str, value: float, unit: str = "Count"):
    """Send a custom metric to CloudWatch."""
    cw_client.put_metric_data(
        Namespace="F1TelemetryPipeline",
        MetricData=[{
            "MetricName": metric_name,
            "Value":      value,
            "Unit":       unit,
            "Dimensions": [
                {"Name": "Race",    "Value": RACE_NAME},
                {"Name": "Circuit", "Value": "Montreal"},
            ],
            "Timestamp": datetime.utcnow(),
        }],
    )


def create_dashboard(cw_client):
    """Create CloudWatch dashboard for F1 race monitoring."""

    dashboard_body = {
        "widgets": [
            {
                "type": "text",
                "x": 0, "y": 0, "width": 24, "height": 2,
                "properties": {
                    "markdown": (
                        f"# 🏎️ F1 Telemetry Pipeline — {RACE_NAME}\n"
                        f"**Circuit:** Circuit Gilles Villeneuve, Montreal  |  "
                        f"**Stack:** Kinesis → Lambda → DynamoDB  |  "
                        f"**github.com/sadvi11/f1-telemetry-pipeline**"
                    )
                }
            },
            {
                "type": "metric",
                "x": 0, "y": 2, "width": 8, "height": 6,
                "properties": {
                    "title":  "Kinesis — Incoming Records/sec",
                    "view":   "timeSeries",
                    "stacked": False,
                    "metrics": [[
                        "AWS/Kinesis", "IncomingRecords",
                        "StreamName", SQS_QUEUE_NAME,
                        {"stat": "Sum", "period": 60}
                    ]],
                    "region": AWS_REGION,
                }
            },
            {
                "type": "metric",
                "x": 8, "y": 2, "width": 8, "height": 6,
                "properties": {
                    "title":  "Kinesis — Bytes Ingested/sec",
                    "view":   "timeSeries",
                    "metrics": [[
                        "AWS/Kinesis", "IncomingBytes",
                        "StreamName", SQS_QUEUE_NAME,
                        {"stat": "Sum", "period": 60, "label": "Bytes"}
                    ]],
                    "region": AWS_REGION,
                }
            },
            {
                "type": "metric",
                "x": 16, "y": 2, "width": 8, "height": 6,
                "properties": {
                    "title":  "DynamoDB — Successful Requests",
                    "view":   "timeSeries",
                    "metrics": [[
                        "AWS/DynamoDB", "SuccessfulRequestLatency",
                        "TableName", DYNAMO_TABLE_NAME,
                        "Operation", "PutItem",
                        {"stat": "SampleCount", "period": 60}
                    ]],
                    "region": AWS_REGION,
                }
            },
            {
                "type": "metric",
                "x": 0, "y": 8, "width": 12, "height": 6,
                "properties": {
                    "title":  "F1 Pipeline — Laps Processed",
                    "view":   "timeSeries",
                    "metrics": [[
                        "F1TelemetryPipeline", "LapsProcessed",
                        "Race", RACE_NAME,
                        {"stat": "Sum", "period": 60}
                    ]],
                    "region": AWS_REGION,
                }
            },
            {
                "type": "metric",
                "x": 12, "y": 8, "width": 12, "height": 6,
                "properties": {
                    "title":  "F1 Pipeline — Pit Stops Detected",
                    "view":   "timeSeries",
                    "metrics": [[
                        "F1TelemetryPipeline", "PitStopsDetected",
                        "Race", RACE_NAME,
                        {"stat": "Sum", "period": 60}
                    ]],
                    "region": AWS_REGION,
                }
            },
        ]
    }

    dashboard_name = "F1-Telemetry-Pipeline"
    cw_client.put_dashboard(
        DashboardName=dashboard_name,
        DashboardBody=json.dumps(dashboard_body),
    )
    print(f"Dashboard created: {dashboard_name}")
    print(
        f"View at: https://{AWS_REGION}.console.aws.amazon.com"
        f"/cloudwatch/home?region={AWS_REGION}#dashboards:name={dashboard_name}"
    )
    return dashboard_name


def publish_sample_metrics(cw_client):
    """Publish sample metrics so dashboard shows data immediately."""
    print("\nPublishing sample metrics to CloudWatch...")

    metrics = [
        ("LapsProcessed",      100, "Count"),
        ("PitStopsDetected",    18, "Count"),
        ("AvgLapTimeSec",     74.8, "Seconds"),
        ("TelemetryEventsTotal", 2000, "Count"),
    ]

    for name, value, unit in metrics:
        put_custom_metric(cw_client, name, value, unit)
        print(f"  Published: {name} = {value} {unit}")

    print("Metrics published.")


def main():
    print("=" * 50)
    print("STEP 4 — CloudWatch Dashboard")
    print("=" * 50)
    validate()

    cw = boto3.client("cloudwatch", region_name=AWS_REGION)

    print("\nCreating dashboard...")
    dashboard_name = create_dashboard(cw)

    publish_sample_metrics(cw)

    print(f"\nSTEP 4 COMPLETE")
    print(f"Dashboard: {dashboard_name}")
    print(f"Open AWS Console → CloudWatch → Dashboards to see live metrics")


if __name__ == "__main__":
    main()
