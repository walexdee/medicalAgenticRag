# Medical Agentic RAG – Setup & Deployment Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| PostgreSQL | 17 | with pgvector extension |
| Docker | 24+ | required for AWS deployment |
| Terraform | 1.6+ | required for AWS deployment |
| AWS CLI | 2.x | required for AWS deployment |

## Local Development

### 1. Install PostgreSQL 17

**macOS:**
```bash
brew install postgresql@17
brew services start postgresql@17
echo 'export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Ubuntu/Debian:**
```bash
sudo apt install -y postgresql-17 postgresql-17-pgvector
sudo systemctl start postgresql
```

### 2. Create the Database and Enable pgvector

```bash
createdb medical_rag
psql medical_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

> The pgvector extension must be created before starting the backend. Tables (`medical_qna`, `medical_device`, `conversation_turns`) are created automatically on first startup.

### 3. Clone and Install Dependencies

```bash
git clone https://github.com/yourusername/medicalAgenticRag.git
cd medicalAgenticRag
npm install
```

`npm install` triggers the `postinstall` script which:
1. Creates a Python virtual environment at `.venv`
2. Installs all Python packages from `requirements.txt`

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://<your-system-username>@localhost/medical_rag
API_HOST=0.0.0.0
API_PORT=8000
```

On macOS, `<your-system-username>` is the output of `whoami`. A local PostgreSQL install does not require a password.

### 5. Generate and Ingest Data

```bash
# Generate synthetic datasets
source .venv/bin/activate
python data/generate_data.py

# Start the backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# In a new terminal, trigger ingest
curl -X POST http://localhost:8000/api/ingest
```

### 6. Start the Frontend

```bash
npm start
```

Frontend opens at http://localhost:3000. The status indicator in the header turns green when the backend is reachable.

## Verify Setup

```bash
# Health check
curl http://localhost:8000/api/health | python3 -m json.tool

# Test a streaming query
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What are symptoms of diabetes?", "conversation_id": "test-1"}'
```

## Production Deployment — AWS (Terraform)

### Architecture

```
Browser → CloudFront → S3 (React build)
Browser → ALB → ECS Fargate (FastAPI backend)
ECS Fargate → RDS PostgreSQL 16 (pgvector + history)
ECS Fargate → Secrets Manager (OPENAI_API_KEY, DATABASE_URL)
```

### Step 1: Provision Infrastructure

```bash
cd terraform

export TF_VAR_openai_api_key="sk-..."
export TF_VAR_db_password="your-strong-db-password"
export TF_VAR_app_api_key=""   # leave empty to disable API key auth

terraform init
terraform plan
terraform apply
```

Note the outputs — you will need them in the steps below:
```bash
terraform output
# backend_url         = "http://<alb-dns>"
# frontend_url        = "https://<cloudfront-id>.cloudfront.net"
# ecr_repository_url  = "<account>.dkr.ecr.us-east-1.amazonaws.com/medical-rag"
# s3_frontend_bucket  = "medical-rag-frontend-<suffix>"
```

### Step 2: Build and Push the Backend Image

> If you are on an Apple Silicon Mac (M1/M2/M3), you must build for `linux/amd64` — ECS Fargate uses x86_64.

```bash
ECR_URL=$(terraform output -raw ecr_repository_url)

aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin $ECR_URL

docker build --platform linux/amd64 -t "${ECR_URL}:latest" .
docker push "${ECR_URL}:latest"
```

After pushing, force a new ECS deployment:
```bash
CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw ecs_service_name)
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment
```

### Step 3: Build and Deploy the Frontend

Before building the React app, set the backend URL so it is baked into the bundle:

```bash
cd ..   # back to project root
echo "REACT_APP_API_URL=$(cd terraform && terraform output -raw backend_url)" > .env.production
npm run build
```

Sync to S3 and invalidate the CloudFront cache:
```bash
S3_BUCKET=$(cd terraform && terraform output -raw s3_frontend_bucket)
aws s3 sync build/ s3://$S3_BUCKET --delete

DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='medical-rag frontend'].Id | [0]" \
  --output text)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

### Step 4: Ingest Data

Once the ECS task is healthy (check the ALB target group), trigger ingest:
```bash
BACKEND=$(cd terraform && terraform output -raw backend_url)
curl -X POST ${BACKEND}/api/ingest
```

### Step 5: Verify

```bash
BACKEND=$(cd terraform && terraform output -raw backend_url)
curl ${BACKEND}/api/health | python3 -m json.tool
```

The frontend is accessible at the `frontend_url` Terraform output.

## Updating a Deployed Stack

**Backend code change:**
```bash
ECR_URL=$(cd terraform && terraform output -raw ecr_repository_url)
docker build --platform linux/amd64 -t "${ECR_URL}:latest" .
docker push "${ECR_URL}:latest"
aws ecs update-service \
  --cluster $(cd terraform && terraform output -raw ecs_cluster_name) \
  --service $(cd terraform && terraform output -raw ecs_service_name) \
  --force-new-deployment
```

**Frontend change:**
```bash
npm run build
aws s3 sync build/ s3://$(cd terraform && terraform output -raw s3_frontend_bucket) --delete
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='medical-rag frontend'].Id | [0]" --output text)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

## Configuration Reference

All constants are in `backend/config.py`. Override any with environment variables:

```python
LLM_MODEL       = "gpt-4o-mini"
EMBED_MODEL     = "text-embedding-3-small"
DATABASE_URL    = "postgresql://localhost/medical_rag"  # override via .env
N_RESULTS       = 5          # documents retrieved per query
MAX_ITERATIONS  = 3          # max relevance-check loop iterations
MAX_HISTORY_TURNS = 10       # conversation turns kept per session
ALLOWED_ORIGINS = "http://localhost:3000"  # comma-separated CORS origins
API_KEY         = ""         # enables X-API-Key auth when non-empty
```

Frontend API URL (`src/agentic_rag_app.jsx`):
```javascript
const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
```

Set `REACT_APP_API_URL` in `.env.production` before running `npm run build` for any non-local deployment.

## Security Checklist

- Store all secrets in `.env` — never commit this file
- `OPENAI_API_KEY` and `DATABASE_URL` are stored in Secrets Manager on AWS
- Enable `API_KEY` to require `X-API-Key` header on all query endpoints
- Rate limiting: 20 requests/min per IP (via `slowapi`)
- CORS: restrict `ALLOWED_ORIGINS` to your frontend domain in production
- RDS: runs in private subnets, not publicly accessible
- Enable HTTPS on the ALB by adding an ACM certificate to `terraform/alb.tf`

## Development Workflow

```bash
# Create a feature branch
git checkout -b feature/your-feature

# Backend changes → backend/pipeline/nodes.py, backend/pipeline/graph.py, backend/routes/
# Frontend changes → src/agentic_rag_app.jsx, src/components/

# Test locally
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
npm start

# Commit
git add backend/ src/
git commit -m "feat: your feature description"
git push origin feature/your-feature
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langgraph.com/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
