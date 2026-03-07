# ──────────────────────────────────────────────────────────
# S3 Bucket — React static build artefacts
# ──────────────────────────────────────────────────────────

# Generates a stable 8-character random suffix so the bucket name is globally
# unique without exposing the AWS account ID. The suffix is stored in state and
# stays the same across subsequent applies.
resource "random_id" "bucket_suffix" {
  byte_length = 4 # produces 8 hex characters
}

resource "aws_s3_bucket" "frontend" {
  bucket = "${var.app_name}-frontend-${random_id.bucket_suffix.hex}"
  tags   = { Name = "${var.app_name}-frontend" }
}

# Block all public access — CloudFront fetches via OAC, not public URLs
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  versioning_configuration { status = "Enabled" }
}

# ──────────────────────────────────────────────────────────
# CloudFront Origin Access Control (OAC)
# Allows CloudFront to read from the private S3 bucket
# ──────────────────────────────────────────────────────────
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.app_name}-oac"
  description                       = "OAC for Medical RAG frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# S3 bucket policy — only CloudFront (via OAC) can read objects
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowCloudFrontServicePrincipal"
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
    }]
  })
}

# ──────────────────────────────────────────────────────────
# CloudFront Distribution
# ──────────────────────────────────────────────────────────
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # US, Canada, Europe only (cheapest)
  comment             = "${var.app_name} frontend"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    # Cache static assets for 1 day; React's content-hashed filenames bust this automatically
    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }

  # Return index.html for any unknown path so React Router (client-side routing) works
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    # To use a custom domain + ACM cert, replace the line above with:
    # acm_certificate_arn      = aws_acm_certificate.frontend.arn
    # ssl_support_method       = "sni-only"
    # minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = { Name = "${var.app_name}-cloudfront" }
}
