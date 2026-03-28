resource "aws_apigatewayv2_api" "tracker_api" {
  name          = local.http_api_name
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["content-type"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = ["*"]
    max_age       = 300
  }

  tags = merge(local.common_tags, {
    Name = local.http_api_name
  })
}

resource "aws_apigatewayv2_integration" "command_handler" {
  api_id                 = aws_apigatewayv2_api.tracker_api.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.command_handler.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 10000
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.tracker_api.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.command_handler.id}"
}

resource "aws_apigatewayv2_route" "command" {
  api_id    = aws_apigatewayv2_api.tracker_api.id
  route_key = "POST /command"
  target    = "integrations/${aws_apigatewayv2_integration.command_handler.id}"
}

resource "aws_apigatewayv2_route" "get_tracker" {
  api_id    = aws_apigatewayv2_api.tracker_api.id
  route_key = "GET /trackers/{tracker_id}"
  target    = "integrations/${aws_apigatewayv2_integration.command_handler.id}"
}

resource "aws_apigatewayv2_route" "get_tracker_history" {
  api_id    = aws_apigatewayv2_api.tracker_api.id
  route_key = "GET /trackers/{tracker_id}/history"
  target    = "integrations/${aws_apigatewayv2_integration.command_handler.id}"
}

resource "aws_apigatewayv2_route" "get_tracker_positions" {
  api_id    = aws_apigatewayv2_api.tracker_api.id
  route_key = "GET /trackers/{tracker_id}/positions"
  target    = "integrations/${aws_apigatewayv2_integration.command_handler.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.tracker_api.id
  name        = "$default"
  auto_deploy = true

  tags = merge(local.common_tags, {
    Name = "${local.http_api_name}-default-stage"
  })
}

resource "aws_lambda_permission" "allow_apigateway_invoke" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.command_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.tracker_api.execution_arn}/*/*"
}
