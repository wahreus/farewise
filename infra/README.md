# Terraform configuration overview

This document combines the Terraform configuration for FareWise into a single infrastructure overview. Each Terraform file has its own top-level section, with the configuration grouped into collapsible sections so the infrastructure can be scanned quickly while keeping the full code easily accessible.

# `main.tf`

<details>
<summary>Provider</summary>

<pre><code class="language-hcl">provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "Terraform"
      Application = "FareWise"
    }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "Terraform"
      Application = "FareWise"
    }
  }
}</code></pre>

</details>

<details>
<summary>Local Values</summary>

<pre><code class="language-hcl">locals {
  bucket_name = var.bucket_name != "" ? var.bucket_name : "${var.project_name}-frontend-${random_id.bucket_suffix.hex}"
}</code></pre>

</details>

<details>
<summary>ACM Certificate for CloudFront</summary>

<pre><code class="language-hcl">resource "aws_acm_certificate" "frontend" {
  provider = aws.us_east_1

  domain_name = var.domain_name

  subject_alternative_names = [
    "www.${var.domain_name}"
  ]

  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "frontend" {
  provider = aws.us_east_1

  certificate_arn = aws_acm_certificate.frontend.arn
}</code></pre>

</details>

<details>
<summary>S3 Frontend Bucket</summary>

<pre><code class="language-hcl">resource "aws_s3_bucket" "frontend" {
  bucket        = local.bucket_name
  force_destroy = true
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}</code></pre>

</details>

<details>
<summary>S3 Ownership Controls</summary>

<pre><code class="language-hcl">resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}</code></pre>

</details>

<details>
<summary>S3 Public Access Block</summary>

<pre><code class="language-hcl">resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}</code></pre>

</details>

<details>
<summary>S3 Server-Side Encryption</summary>

<pre><code class="language-hcl">resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}</code></pre>

</details>

<details>
<summary>Lambda IAM Role and Permissions</summary>

<pre><code class="language-hcl">data "aws_iam_policy_document" "api_lambda_assume_role" {
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
}</code></pre>

</details>

<details>
<summary>API Lambda Function</summary>

<pre><code class="language-hcl">resource "aws_lambda_function" "api" {
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
}</code></pre>

</details>

<details>
<summary>HTTP API Gateway</summary>

<pre><code class="language-hcl">resource "aws_apigatewayv2_api" "api" {
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
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }
}

resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id = "AllowExecutionFromAPIGateway"
  action       = "lambda:InvokeFunction"

  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}</code></pre>

</details>

<details>
<summary>CloudFront Origin Access Control</summary>

<pre><code class="language-hcl">resource "aws_cloudfront_origin_access_control" "frontend" {
  name        = "${var.project_name}-oac"
  description = "Allow CloudFront to read the private S3 frontend bucket"

  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}</code></pre>

</details>

<details>
<summary>CloudFront Distribution</summary>

<pre><code class="language-hcl">resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} frontend and API"
  default_root_object = "index.html"
  price_class         = var.price_class

  aliases = [
    var.domain_name,
    "www.${var.domain_name}"
  ]

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

    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  ordered_cache_behavior {
    path_pattern     = "/analyses*"
    target_origin_id = "api-${aws_apigatewayv2_api.api.id}"

    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods  = ["GET", "HEAD"]

    compress = true

    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"

    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.frontend.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}</code></pre>

</details>

<details>
<summary>S3 Bucket Policy for CloudFront Access</summary>

<pre><code class="language-hcl">resource "aws_s3_bucket_policy" "allow_cloudfront" {
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
}</code></pre>

</details>

<details>
<summary>GitHub OIDC</summary>

<pre><code class="language-hcl">resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]
}</code></pre>

</details>

<details>
<summary>GitHub Actions CD Role</summary>

<pre><code class="language-hcl">data "aws_caller_identity" "current" {}

locals {
  github_oidc_provider_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"

  github_cd_subject = "repo:wahreus@284278793/farewise@1253475090:environment:production"
}

data "aws_iam_policy_document" "github_cd_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_cd_subject]
    }
  }
}

resource "aws_iam_role" "github_cd" {
  name               = "${var.project_name}-github-cd"
  assume_role_policy = data.aws_iam_policy_document.github_cd_assume_role.json
}

data "aws_iam_policy_document" "github_cd" {
  statement {
    sid = "UpdateLambdaCode"

    effect = "Allow"

    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration"
    ]

    resources = [
      aws_lambda_function.api.arn
    ]
  }

  statement {
    sid = "ListFrontendBucket"

    effect = "Allow"

    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation"
    ]

    resources = [
      aws_s3_bucket.frontend.arn
    ]
  }

  statement {
    sid = "DeployFrontendObjects"

    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.frontend.arn}/*"
    ]
  }

  statement {
    sid = "InvalidateCloudFront"

    effect = "Allow"

    actions = [
      "cloudfront:CreateInvalidation"
    ]

    resources = [
      aws_cloudfront_distribution.frontend.arn
    ]
  }
}

resource "aws_iam_role_policy" "github_cd" {
  name   = "${var.project_name}-github-cd-policy"
  role   = aws_iam_role.github_cd.id
  policy = data.aws_iam_policy_document.github_cd.json
}</code></pre>

</details>
</br>

# `outputs.tf`

<details>
<summary>Outputs</summary>

<pre><code class="language-hcl">output "cloudfront_url" {
  description = "Public HTTPS URL for FareWise"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "api_url" {
  description = "Public API Gateway URL"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "frontend_bucket_name" {
  description = "S3 bucket that stores the frontend files"
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID used for cache invalidations"
  value       = aws_cloudfront_distribution.frontend.id
}

output "github_cd_role_arn" {
  description = "IAM role assumed by the FareWise GitHub Actions CD workflow"
  value       = aws_iam_role.github_cd.arn
}

output "site_url" {
  description = "Canonical public HTTPS URL for FareWise"
  value       = "https://${var.domain_name}"
}

output "www_site_url" {
  description = "WWW HTTPS URL for FareWise"
  value       = "https://www.${var.domain_name}"
}

output "cloudfront_domain_name" {
  description = "CloudFront hostname used as the Squarespace ALIAS/CNAME destination"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "squarespace_acm_validation_records" {
  description = "DNS CNAME records to add in Squarespace to validate the CloudFront ACM certificate"

  value = {
    for dvo in aws_acm_certificate.frontend.domain_validation_options :
    dvo.domain_name => {
      type  = dvo.resource_record_type
      name  = trimsuffix(trimsuffix(dvo.resource_record_name, "."), ".${var.domain_name}")
      value = trimsuffix(dvo.resource_record_value, ".")
    }
  }
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN for the FareWise CloudFront custom domain"
  value       = aws_acm_certificate.frontend.arn
}</code></pre>

</details>
</br>

# `variables.tf`

<details>
<summary>Variables</summary>

<pre><code class="language-hcl">variable "aws_region" {
  type    = string
  default = "eu-west-2"
}

variable "project_name" {
  type    = string
  default = "farewise"
}

variable "bucket_name" {
  type    = string
  default = ""
}

variable "price_class" {
  type    = string
  default = "PriceClass_100"
}

variable "domain_name" {
  type    = string
  default = "farewise.uk"
}</code></pre>

</details>
</br>

# `versions.tf`

<details>
<summary>Terraform and Provider Versions</summary>

<pre><code class="language-hcl">terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}</code></pre>

</details>
