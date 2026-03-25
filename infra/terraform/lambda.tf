data "archive_file" "command_handler_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/lambdas/command_handler"
  output_path = "${path.module}/command_handler.zip"
}

data "archive_file" "simulator_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/lambdas/simulator"
  output_path = "${path.module}/simulator.zip"
}

resource "aws_cloudwatch_log_group" "command_handler" {
  name              = "/aws/lambda/${local.command_lambda_name}"
  retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    Name = "/aws/lambda/${local.command_lambda_name}"
  })
}

resource "aws_cloudwatch_log_group" "simulator" {
  name              = "/aws/lambda/${local.simulator_lambda_name}"
  retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    Name = "/aws/lambda/${local.simulator_lambda_name}"
  })
}

resource "aws_lambda_function" "command_handler" {
  function_name    = local.command_lambda_name
  role             = aws_iam_role.command_handler_role.arn
  runtime          = var.lambda_runtime
  handler          = "app.lambda_handler"
  filename         = data.archive_file.command_handler_zip.output_path
  source_code_hash = data.archive_file.command_handler_zip.output_base64sha256
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  environment {
    variables = {
      TRACKER_TABLE_NAME = aws_dynamodb_table.trackers.name
      HISTORY_TABLE_NAME = aws_dynamodb_table.tracker_history.name
      LOG_LEVEL          = var.log_level
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy.dynamodb_access,
    aws_cloudwatch_log_group.command_handler,
  ]

  tags = merge(local.common_tags, {
    Name = local.command_lambda_name
  })
}

resource "aws_lambda_function" "simulator" {
  function_name    = local.simulator_lambda_name
  role             = aws_iam_role.simulator_role.arn
  runtime          = var.lambda_runtime
  handler          = "app.lambda_handler"
  filename         = data.archive_file.simulator_zip.output_path
  source_code_hash = data.archive_file.simulator_zip.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      TRACKER_TABLE_NAME = aws_dynamodb_table.trackers.name
      HISTORY_TABLE_NAME = aws_dynamodb_table.tracker_history.name
      LOG_LEVEL          = var.log_level
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.simulator_basic_execution,
    aws_iam_role_policy.simulator_dynamodb_access,
    aws_cloudwatch_log_group.simulator,
  ]

  tags = merge(local.common_tags, {
    Name = local.simulator_lambda_name
  })
}
