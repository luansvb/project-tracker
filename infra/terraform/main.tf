locals {
  prefix                     = "${var.project_name}-${var.environment}"
  tracker_table_name         = "${local.prefix}-trackers"
  tracker_history_table_name = "${local.prefix}-tracker-history"
  command_lambda_name        = "${local.prefix}-command-handler"
  simulator_lambda_name      = "${local.prefix}-simulator"
  simulator_rule_name        = "${local.prefix}-simulator-schedule"
  http_api_name              = "${local.prefix}-api"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Layer       = "foundation-v0.3"
  }
}
