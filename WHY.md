# WHY.md — The Decisions Behind This Project

> Most automation portfolios show scripts that wrap AWS CLI commands. This document explains why each module was built the way it was — the engineering thinking behind production-grade boto3 automation.

---

## Why I Built This Project

Cloud engineers who only use the AWS Console are not cloud engineers. They are manual operators.

Every task a human performs in the AWS Console — creating an EC2 instance, uploading to S3, scheduling a Lambda, setting a CloudWatch alarm, writing a DynamoDB item — should be automatable. This project is the proof that I think in code, not clicks.

The practical reason: every Cloud Engineer and DevOps job posting in Canada asks for Python + boto3. Saying "I know boto3" in a CV is a claim. Six working modules covering EC2, S3, Lambda, CloudWatch, DynamoDB, and API Gateway is evidence.

---

## Why Six Separate Modules Instead of One Script

A single monolithic automation script is easy to build and impossible to maintain. When the DynamoDB logic breaks, you should not have to read 800 lines of EC2 code to find the problem.

Each module has one responsibility:

| Module | Responsibility |
|---|---|
| ec2_controller.py | EC2 lifecycle — start, stop, list, tag |
| s3_uploader.py | S3 operations — upload, download, list, delete |
| lambda_scheduler.py | Lambda invocation and EventBridge scheduling |
| cloudwatch_alerts.py | CloudWatch metrics, alarms, and SNS notifications |
| dynamodb_table.py | DynamoDB table lifecycle and item operations |
| api_gateway.py | REST API creation with Lambda proxy integration |

This is the single responsibility principle applied to infrastructure automation. Each module can be imported, tested, and deployed independently.

---

## Why DynamoDB Instead of RDS

The Frame FinTech JD specifically mentions DynamoDB. But beyond that, the choice between DynamoDB and RDS is a real architectural decision with real consequences.

DynamoDB is the right choice when:
- Access patterns are known upfront (by user_id, by event_type)
- Read/write throughput needs to scale automatically
- You want zero database administration (no patches, no backups, no connection pooling)
- You can design a schema around partition + sort key access patterns

RDS is the right choice when:
- You need complex joins across multiple tables
- Your access patterns are unpredictable (ad-hoc SQL queries)
- You have existing SQL expertise and tooling

For the SmartMoney Canada financial events use case — storing user document uploads and sentiment queries — DynamoDB's key-value + GSI model fits perfectly. The access patterns are fixed: query by user, or query by event type.

---

## Why a Global Secondary Index (GSI)

DynamoDB's partition key gives you fast lookups by user. But what if you want to find all sentiment queries across all users? A full table scan would be expensive and slow.

A GSI on `event_type` solves this at no query cost. The GSI maintains a separate index sorted by event_type — any query against it runs in milliseconds regardless of table size.

This is the same pattern that Nokia's subscriber management systems used: primary index by subscriber ID for individual lookups, secondary index by service type for aggregated reporting. The data structure is different; the indexing principle is identical.

---

## Why PAY_PER_REQUEST Billing

DynamoDB offers two billing modes: provisioned capacity and on-demand (PAY_PER_REQUEST).

Provisioned capacity is cheaper at scale if you can accurately predict your read/write throughput. On-demand costs more per request but charges zero when traffic is zero.

For a portfolio project and for new workloads where traffic patterns are unknown, on-demand is the correct choice. You never pay for idle capacity. For SmartMoney Canada at current scale, a month of DynamoDB usage costs less than $1.

In production at high scale, you would switch to provisioned capacity once traffic patterns stabilize — typically after 2-3 months of on-demand data.

---

## Why API Gateway with Lambda Proxy Integration

There are two ways to integrate API Gateway with Lambda:

**Custom integration:** API Gateway transforms the request before sending to Lambda. You define mapping templates in Velocity Template Language. Powerful but complex.

**Lambda proxy integration:** API Gateway sends the full HTTP request to Lambda as-is. Lambda receives method, path, headers, body, and query parameters. Lambda returns a full HTTP response including status code and headers.

Lambda proxy was chosen because:
1. No mapping templates to maintain — less configuration drift
2. Lambda owns the full request/response lifecycle — easier to test locally
3. Standard pattern used by the majority of production API Gateway deployments in Canada

---

## Why ca-central-1 as Default Region

Every module defaults to `ca-central-1` — Canada (Central).

Canadian data residency is not optional for financial services, healthcare, and government workloads. PIPEDA (Personal Information Protection and Electronic Documents Act) and provincial privacy laws require that certain categories of Canadian data stay in Canada.

ca-central-1 is the primary Canadian AWS region. Defaulting to it in every module demonstrates awareness of Canadian compliance requirements — a genuine differentiator when applying to Canadian fintech, insurance, and healthcare companies.

---

## Why Tagged Resources

Every AWS resource created by this project includes three tags:

```
Project:     SmartMoneyCanada
Environment: dev
ManagedBy:   aws-python-automation
```

Tags are not decorative. They are the foundation of:
- **Cost allocation:** Which project is generating this AWS bill?
- **Access control:** IAM policies can restrict actions to tagged resources
- **Operational visibility:** CloudWatch dashboards filtered by tag
- **Compliance:** Auditors need to trace resources to business owners

An engineer who creates untagged resources in a production AWS account creates operational debt. Tagging every resource by default is the discipline that separates junior engineers from mid-level ones.

---

## Why Error Handling with ClientError

Every AWS API call can fail. Network timeouts. Throttling. Resource conflicts. Permission errors.

Each module catches `botocore.exceptions.ClientError` and handles specific error codes — `ResourceInUseException` for tables that already exist, `ConflictException` for API resources that are already created, `ResourceConflictException` for Lambda permissions already granted.

The alternative — letting exceptions propagate — produces scripts that fail on the second run because the resource already exists from the first run. Idempotent automation is automation that can run safely multiple times without breaking.

---

## The Nokia Bridge — Why My Background Is Relevant

Automating Nokia CBAM VNF deployments required the same thinking as boto3 automation: translate an operational procedure into repeatable, idempotent code. The difference is the API surface — Nokia's CBAM REST API vs AWS boto3.

The discipline is identical: understand the resource lifecycle, handle errors, make operations idempotent, tag everything for traceability, and document the WHY not just the WHAT.

---

*Code without context is archaeology. This document ensures the reasoning is never lost.*

**Sadhvi Sharma** | Calgary, AB | github.com/sadvi11
