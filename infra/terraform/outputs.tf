output "api_base_url" {
  description = "URL base da API HTTP."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "tracker_table_name" {
  description = "Nome da tabela DynamoDB de trackers."
  value       = aws_dynamodb_table.trackers.name
}

output "tracker_history_table_name" {
  description = "Nome da tabela DynamoDB de histórico dos trackers."
  value       = aws_dynamodb_table.tracker_history.name
}

output "command_lambda_name" {
  description = "Nome da Lambda que processa comandos."
  value       = aws_lambda_function.command_handler.function_name
}
