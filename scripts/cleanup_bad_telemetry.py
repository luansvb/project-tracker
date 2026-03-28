import boto3
from boto3.dynamodb.conditions import Key

REGION = "us-east-1"
TABLE_NAME = "tracker-simulator-dev-tracker-telemetry"
TRACKER_ID = "tracker-lt32-001"

# ajuste se quiser mudar o corte
CUTOFF_ISO = "2026-03-28T15:21:48+00:00"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def main():
    response = table.query(
        KeyConditionExpression=Key("tracker_id").eq(TRACKER_ID) & Key("recorded_at").lt(CUTOFF_ISO)
    )

    items = response.get("Items", [])
    deleted = 0

    for item in items:
        table.delete_item(
            Key={
                "tracker_id": item["tracker_id"],
                "recorded_at": item["recorded_at"],
            }
        )
        deleted += 1

    print(f"Tracker: {TRACKER_ID}")
    print(f"Cutoff: {CUTOFF_ISO}")
    print(f"Deleted: {deleted}")


if __name__ == "__main__":
    main()
