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
