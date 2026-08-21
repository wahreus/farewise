# ------------------------------------------------------------------------------------------------------------
# Provider
# ------------------------------------------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "Terraform"
      Application = "FareWise"
    }
  }
}

# ------------------------------------------------------------------------------------------------------------
# Local Values
# ------------------------------------------------------------------------------------------------------------

locals {
  bucket_name = var.bucket_name != "" ? var.bucket_name : "${var.project_name}-frontend-${random_id.bucket_suffix.hex}"
}

# ------------------------------------------------------------------------------------------------------------
# S3 Frontend Bucket
# ------------------------------------------------------------------------------------------------------------

resource "aws_s3_bucket" "frontend" {
  bucket        = local.bucket_name
  force_destroy = true
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# ------------------------------------------------------------------------------------------------------------
# S3 Ownership Controls
# ------------------------------------------------------------------------------------------------------------

resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# ------------------------------------------------------------------------------------------------------------
# S3 Public Access Block
# ------------------------------------------------------------------------------------------------------------

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ------------------------------------------------------------------------------------------------------------
# S3 Server-Side Encryption
# ------------------------------------------------------------------------------------------------------------

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ------------------------------------------------------------------------------------------------------------
# Lambda IAM Role and Permissions
# ------------------------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "api_lambda_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "api_lambda" {
  name = "${var.project_name}-api-lambda-role"

  assume_role_policy = data.aws_iam_policy_document.api_lambda_assume_role.json
}

data "aws_iam_policy_document" "api_lambda" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = ["${aws_cloudwatch_log_group.api_lambda.arn}:*"]
  }
}

resource "aws_iam_role_policy" "api_lambda" {
  name = "${var.project_name}-api-lambda-policy"
  role = aws_iam_role.api_lambda.id

  policy = data.aws_iam_policy_document.api_lambda.json
}

resource "aws_cloudwatch_log_group" "api_lambda" {
  name              = "/aws/lambda/${var.project_name}-api"
  retention_in_days = 14
}

# ------------------------------------------------------------------------------------------------------------
# API Lambda Function
# ------------------------------------------------------------------------------------------------------------

resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api"

  role    = aws_iam_role.api_lambda.arn
  handler = "src.api.main.handler"
  runtime = "python3.12"

  filename         = "${path.module}/../build/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../build/lambda.zip")

  architectures = ["x86_64"]
  memory_size   = 1024
  timeout       = 25

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash,
    ]
  }

  depends_on = [
    aws_iam_role_policy.api_lambda,
    aws_cloudwatch_log_group.api_lambda
  ]
}

# ------------------------------------------------------------------------------------------------------------
# HTTP API Gateway
# ------------------------------------------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id = aws_apigatewayv2_api.api.id

  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id = aws_apigatewayv2_api.api.id

  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.api.id

  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 2
    throttling_rate_limit  = 1
  }
}

resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id = "AllowExecutionFromAPIGateway"
  action       = "lambda:InvokeFunction"

  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# ------------------------------------------------------------------------------------------------------------
# CloudFront Origin Access Control
# ------------------------------------------------------------------------------------------------------------

resource "aws_cloudfront_origin_access_control" "frontend" {
  name        = "${var.project_name}-oac"
  description = "Allow CloudFront to read the private S3 frontend bucket"

  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ------------------------------------------------------------------------------------------------------------
# CloudFront Distribution
# ------------------------------------------------------------------------------------------------------------

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} frontend and API"
  default_root_object = "index.html"
  price_class         = var.price_class

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-${aws_s3_bucket.frontend.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  origin {
    domain_name = trimprefix(aws_apigatewayv2_api.api.api_endpoint, "https://")
    origin_id   = "api-${aws_apigatewayv2_api.api.id}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id = "s3-${aws_s3_bucket.frontend.id}"

    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    cached_methods  = ["GET", "HEAD"]

    compress = true

    # AWS managed cache policy: CachingOptimized
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  ordered_cache_behavior {
    path_pattern     = "/analyses*"
    target_origin_id = "api-${aws_apigatewayv2_api.api.id}"

    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods  = ["GET", "HEAD"]

    compress = true

    # AWS managed cache policy: CachingDisabled
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"

    # AWS managed origin request policy: AllViewerExceptHostHeader
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# ------------------------------------------------------------------------------------------------------------
# S3 Bucket Policy for CloudFront Access
# ------------------------------------------------------------------------------------------------------------

resource "aws_s3_bucket_policy" "allow_cloudfront" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipalReadOnly"
        Effect = "Allow"

        Principal = {
          Service = "cloudfront.amazonaws.com"
        }

        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"

        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })

  depends_on = [
    aws_s3_bucket_public_access_block.frontend
  ]
}

# ------------------------------------------------------------------------------------------------------------
# GitHub OIDC
# ------------------------------------------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]
}
