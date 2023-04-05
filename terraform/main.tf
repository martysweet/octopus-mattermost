resource "aws_lambda_function" "lambda_function" {
  function_name    = var.function_name
  handler          = "main.lambda_handler"
  runtime          = "python3.8"
  memory_size      = "256"
  timeout          = "10"
  filename         = data.archive_file.lambda_function.output_path
  source_code_hash = data.archive_file.lambda_function.output_base64sha256
  role             = aws_iam_role.lambda_function.arn
  environment {
    variables = var.environment_vars
  }
}

resource "aws_iam_role" "lambda_function" {
  name = "lambda_function_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_function" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_function.name
}

# Lambda resource policy to allow events.amazonaws.com
resource "aws_lambda_permission" "lambda_function" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_function.arn
}

# Run the function at 15:00 UTC every day
resource "aws_cloudwatch_event_rule" "lambda_function" {
  name                = "lambda_function_daily_invoke"
  description         = "Run the lambda function every day at 15:00 UTC"
  schedule_expression = "cron(0 15 * * ? *)"
}

resource "aws_cloudwatch_event_target" "lambda_function" {
  target_id = "lambda_function_daily_invoke"
  rule      = aws_cloudwatch_event_rule.lambda_function.name
  arn       = aws_lambda_function.lambda_function.arn
}

output "arn" {
  value = aws_lambda_function.lambda_function.arn
}

