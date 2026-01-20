# AWS EBS Snapshot Cleanup Lambda (Safe by Design)

## Overview

This repository contains an AWS Lambda function that helps identify and clean up unused EBS snapshots to reduce storage costs, while prioritizing safety and operational correctness.

The solution is intentionally conservative and avoids destructive assumptions by using explicit opt-in tagging, retention rules, and dry-run execution.

---

## Architecture & Flow Diagram

Below is a high-level view of the Lambda execution flow and safety guardrails:

```
┌────────────────────┐
│ EventBridge (Cron) │   (Optional Schedule)
└─────────┬──────────┘
          │
          ▼
┌──────────────────────────┐
│ AWS Lambda Function      │
│ EBS Snapshot Cleanup     │
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────┐
│ DescribeSnapshots        │
│ (Account-owned)          │
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────┐
│ DescribeImages (AMIs)    │
│ Collect referenced snaps│
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────┐
│ Snapshot Evaluation Loop │
└─────────┬────────────────┘
          │
          ├─ Age < RETENTION_DAYS ──► SKIP
          │
          ├─ Missing AutoCleanup   ─► SKIP
          │
          ├─ Referenced by AMI     ─► SKIP
          │
          ▼
┌──────────────────────────┐
│ DRY_RUN == true ?        │
└─────────┬────────────────┘
          │
     Yes ─┴─► Log "[DRY-RUN]"
          │
      No  ▼
┌──────────────────────────┐
│ DeleteSnapshot API Call  │
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────┐
│ Execution Summary Logs   │
│ (scanned / skipped /     │
│  deleted counts)         │
└──────────────────────────┘
```

**Design intent:**  
Every decision point biases toward *skipping* unless all explicit safety conditions are satisfied.

---

## Features

- Dry-run mode enabled by default  
- Tag-based opt-in snapshot deletion  
- Configurable snapshot retention period  
- Protection for AMI-referenced snapshots  
- Pagination support for large AWS accounts  
- Clear execution summary for auditing and review  

---

## How It Works

The Lambda function performs the following steps:

1. Retrieves all EBS snapshots owned by the AWS account  
2. Collects snapshot IDs referenced by AMIs and excludes them  
3. Applies a configurable retention threshold  
4. Deletes snapshots only if explicitly tagged for cleanup  
5. Runs in dry-run mode unless deletion is explicitly enabled  
6. Logs a summary of scanned, skipped, and deleted snapshots  

---

## Configuration

The function is controlled entirely through environment variables.

| Variable | Description | Default |
|--------|------------|---------|
| DRY_RUN | Simulates deletion without removing snapshots | true |
| RETENTION_DAYS | Minimum age (in days) before deletion | 30 |
| ALLOW_DELETE_TAG | Tag key required for deletion | AutoCleanup |
| ALLOW_DELETE_VALUE | Tag value required for deletion | true |

---

## Deletion Logic

A snapshot is eligible for deletion **only when all of the following conditions are met**:

- Snapshot age exceeds `RETENTION_DAYS`  
- Snapshot is explicitly tagged with `AutoCleanup=true`  
- Snapshot is **not referenced by any AMI**  
- `DRY_RUN` is set to `false`  

This approach ensures cleanup is intentional, reviewable, and reversible.

---

## Example Output (Dry-Run)

```
[DRY-RUN] Would delete snapshot snap-0abc1234

Execution summary:
{
  "scanned": 125,
  "skipped_ami": 12,
  "skipped_tag": 97,
  "skipped_age": 14,
  "deleted": 0
}
```

---

## Testing

The function can be tested safely without real data deletion by:

- Creating test snapshots with the required cleanup tag  
- Setting `RETENTION_DAYS=0`  
- Running with `DRY_RUN=true` to validate logic  
- Reviewing logs and execution summary  

Deletion should only be enabled after dry-run results are verified.

---

## Deployment

1. Deploy as an AWS Lambda function  
2. Required IAM permissions:
   - `ec2:DescribeSnapshots`
   - `ec2:DescribeImages`
   - `ec2:DeleteSnapshot`
3. Optionally schedule execution using Amazon EventBridge  

---

## Notes

- Detached or unused volumes are **not assumed safe to delete**  
- AWS Backup and critical snapshots are protected by default unless explicitly tagged  
- Designed to favor safety over aggressive cleanup  

---

## Purpose

This project demonstrates a **guardrail-first approach** to AWS cost optimization, showing how automation can be applied responsibly without introducing operational risk.
