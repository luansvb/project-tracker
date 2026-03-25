resource "aws_cloudwatch_event_rule" "simulator_schedule" {
  name                = local.simulator_rule_name
  description         = "Dispara a Lambda de simulação periodicamente"
  schedule_expression = "rate(1 minute)"

  tags = merge(local.common_tags, {
    Name = local.simulator_rule_name
  })
}

resource "aws_cloudwatch_event_target" "simulator_lambda_target" {
  rule      = aws_cloudwatch_event_rule.simulator_schedule.name
  target_id = "simulator-lambda"
  arn       = aws_lambda_function.simulator.arn
}

resource "aws_lambda_permission" "allow_eventbridge_invoke_simulator" {
  statement_id  = "AllowExecutionFromEventBridgeSimulator"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.simulator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.simulator_schedule.arn
}
