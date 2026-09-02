output "cloudfront_url" {
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
}

