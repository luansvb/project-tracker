data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "command_handler_role" {
  name               = "${local.prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = merge(local.common_tags, {
    Name = "${local.prefix}-lambda-role"
  })
}

resource "aws_iam_role" "simulator_role" {
  name               = "${local.prefix}-simulator-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = merge(local.common_tags, {
    Name = "${local.prefix}-simulator-role"
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.command_handler_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "simulator_basic_execution" {
  role       = aws_iam_role.simulator_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "dynamodb_access" {
  name = "${local.prefix}-dynamodb-policy"
  role = aws_iam_role.command_handler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TrackersTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DescribeTable"
        ]
        Resource = aws_dynamodb_table.trackers.arn
      },
      {
        Sid    = "TrackerHistoryTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:DescribeTable"
        ]
        Resource = aws_dynamodb_table.tracker_history.arn
      },
      {
        Sid    = "TrackerTelemetryTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:DescribeTable"
        ]
        Resource = aws_dynamodb_table.tracker_telemetry.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "simulator_dynamodb_access" {
  name = "${local.prefix}-simulator-dynamodb-policy"
  role = aws_iam_role.simulator_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TrackersTableReadWriteAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:PutItem",
          "dynamodb:DescribeTable"
        ]
        Resource = aws_dynamodb_table.trackers.arn
      },
      {
        Sid    = "TrackerHistoryWriteAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:DescribeTable"
        ]
        Resource = aws_dynamodb_table.tracker_history.arn
      },
      {
        Sid    = "TrackerTelemetryWriteAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:DescribeTable"
        ]
        Resource = aws_dynamodb_table.tracker_telemetry.arn
      }
    ]
  })
}
