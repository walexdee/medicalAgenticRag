output "backend_url" {
  description = "ALB DNS name — use this as your backend API base URL during testing"
  value       = "http://${aws_lb.backend.dns_name}"
}

output "frontend_url" {
  description = "CloudFront URL for the React frontend"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "ecr_repository_url" {
  description = "ECR URL to push the backend Docker image to"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name — use in deploy scripts"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name — use in deploy scripts"
  value       = aws_ecs_service.backend.name
}

output "s3_frontend_bucket" {
  description = "S3 bucket name — sync your React build output here"
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for ECS container logs"
  value       = aws_cloudwatch_log_group.backend.name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (host:port) — used in DATABASE_URL"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.postgres.db_name
}
