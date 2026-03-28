resource "aws_dynamodb_table" "trackers" {
  name         = local.tracker_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tracker_id"

  attribute {
    name = "tracker_id"
    type = "S"
  }

  tags = merge(local.common_tags, {
    Name = local.tracker_table_name
  })
}

resource "aws_dynamodb_table" "tracker_history" {
  name         = local.tracker_history_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  tags = merge(local.common_tags, {
    Name = local.tracker_history_table_name
  })
}

resource "aws_dynamodb_table" "tracker_telemetry" {
  name         = "${local.prefix}-tracker-telemetry"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tracker_id"
  range_key    = "recorded_at"

  attribute {
    name = "tracker_id"
    type = "S"
  }

  attribute {
    name = "recorded_at"
    type = "S"
  }

  tags = merge(local.common_tags, {
    Name = "${local.prefix}-tracker-telemetry"
  })
}
