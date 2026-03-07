# ──────────────────────────────────────────────────────────
# Application Load Balancer
# Sits in the public subnets and forwards traffic to ECS tasks
# in the private subnets on port 8000.
#
# HTTPS note: to enable HTTPS, provision an ACM certificate
# for your domain and uncomment the https_listener block below.
# ──────────────────────────────────────────────────────────
resource "aws_lb" "backend" {
  name               = "${var.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  # Prevents accidental deletion of the load balancer
  enable_deletion_protection = false

  tags = { Name = "${var.app_name}-alb" }
}

# Target group — ECS tasks register here
resource "aws_lb_target_group" "backend" {
  name        = "${var.app_name}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # required for Fargate

  health_check {
    path                = "/api/health"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = { Name = "${var.app_name}-tg" }
}

# HTTP listener — forwards all traffic to ECS on port 8000
# Replace this with a redirect-to-HTTPS rule once you add a certificate
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.backend.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# ──────────────────────────────────────────────────────────
# HTTPS listener (uncomment once you have an ACM certificate)
# ──────────────────────────────────────────────────────────
# resource "aws_acm_certificate" "backend" {
#   domain_name       = "api.yourdomain.com"
#   validation_method = "DNS"
# }
#
# resource "aws_lb_listener" "https" {
#   load_balancer_arn = aws_lb.backend.arn
#   port              = 443
#   protocol          = "HTTPS"
#   ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
#   certificate_arn   = aws_acm_certificate.backend.arn
#
#   default_action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.backend.arn
#   }
# }
#
# # Redirect HTTP → HTTPS
# resource "aws_lb_listener_rule" "http_redirect" {
#   listener_arn = aws_lb_listener.http.arn
#   priority     = 1
#   action {
#     type = "redirect"
#     redirect { protocol = "HTTPS", port = "443", status_code = "HTTP_301" }
#   }
#   condition { path_pattern { values = ["/*"] } }
# }

# CloudWatch log group for ALB access logs (optional)
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = 30

  tags = { Name = "${var.app_name}-logs" }
}
