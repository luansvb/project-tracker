variable "aws_region" {
  description = "Região AWS onde a infraestrutura será provisionada."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nome base do projeto."
  type        = string
  default     = "tracker-simulator"
}

variable "environment" {
  description = "Ambiente de deploy."
  type        = string
  default     = "dev"
}

variable "lambda_runtime" {
  description = "Runtime da Lambda."
  type        = string
  default     = "python3.12"
}

variable "lambda_memory_size" {
  description = "Memória da Lambda em MB."
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Timeout da Lambda em segundos."
  type        = number
  default     = 10
}

variable "log_retention_days" {
  description = "Retenção dos logs no CloudWatch."
  type        = number
  default     = 14
}

variable "log_level" {
  description = "Nível de log da Lambda."
  type        = string
  default     = "INFO"
}
