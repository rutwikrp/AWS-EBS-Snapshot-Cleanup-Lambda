import boto3
import os
from datetime import datetime, timezone, timedelta

ec2 = boto3.client("ec2")

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
ALLOW_DELETE_TAG = os.getenv("ALLOW_DELETE_TAG", "AutoCleanup")
ALLOW_DELETE_VALUE = os.getenv("ALLOW_DELETE_VALUE", "true")

cutoff_date = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)


def get_ami_snapshot_ids():
    """Collect snapshot IDs used by AMIs"""
    snapshot_ids = set()
    paginator = ec2.get_paginator("describe_images")

    for page in paginator.paginate(Owners=["self"]):
        for image in page["Images"]:
            for mapping in image.get("BlockDeviceMappings", []):
                ebs = mapping.get("Ebs")
                if ebs and "SnapshotId" in ebs:
                    snapshot_ids.add(ebs["SnapshotId"])

    return snapshot_ids


def has_required_tag(tags):
    if not tags:
        return False
    for tag in tags:
        if tag["Key"] == ALLOW_DELETE_TAG and tag["Value"].lower() == ALLOW_DELETE_VALUE.lower():
            return True
    return False


def lambda_handler(event, context):
    stats = {
        "scanned": 0,
        "skipped_ami": 0,
        "skipped_tag": 0,
        "skipped_age": 0,
        "deleted": 0
    }

    ami_snapshot_ids = get_ami_snapshot_ids()

    paginator = ec2.get_paginator("describe_snapshots")

    for page in paginator.paginate(OwnerIds=["self"]):
        for snapshot in page["Snapshots"]:
            stats["scanned"] += 1
            snapshot_id = snapshot["SnapshotId"]
            start_time = snapshot["StartTime"]
            tags = snapshot.get("Tags", [])

            # Protect AMI snapshots
            if snapshot_id in ami_snapshot_ids:
                stats["skipped_ami"] += 1
                continue

            # Enforce retention
            if start_time > cutoff_date:
                stats["skipped_age"] += 1
                continue

            # Enforce explicit opt-in tag
            if not has_required_tag(tags):
                stats["skipped_tag"] += 1
                continue

            if DRY_RUN:
                print(f"[DRY-RUN] Would delete snapshot {snapshot_id}")
            else:
                ec2.delete_snapshot(SnapshotId=snapshot_id)
                print(f"Deleted snapshot {snapshot_id}")
                stats["deleted"] += 1

    print("Execution summary:", stats)
    return stats
