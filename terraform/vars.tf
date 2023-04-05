variable "function_name" {
  type    = string
  default = "octopus-energy"
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "environment_vars" {
  type      = map(string)
  sensitive = true
  default   = {
    "API_KEY"     = "unset"
    "METER_ID"    = "unset"
    "MPAN"        = "unset"
    "WEBHOOK_URL" = "unset"
  }
}