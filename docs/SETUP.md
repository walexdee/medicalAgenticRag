# Medical Agentic RAG – Setup & Deployment Guide

## Quick Setup (5 minutes)

### Step 1: Clone & Navigate
```bash
git clone <your-repo-url>
cd Medical_RAG
```

### Step 2: Install All Dependencies
```bash
npm install
```

This single command installs all Node packages **and** automatically creates a Python virtual environment (`.venv`) and installs all Python packages via the `postinstall` script in `package.json`.

```bash
# Configure environment
cp .env.example .env
# Edit .env with your keys:
#   OPENAI_API_KEY=sk-...
#   DATABASE_URL=postgresql://postgres:password@localhost/medical_rag
```

Create the PostgreSQL database (first time only):
```bash
psql -U postgres -c "CREATE DATABASE medical_rag;"
# Tables and pgvector extension are created automatically on first backend start
```

### Step 3: Start Backend
```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Backend will be available at: **http://localhost:8000**
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health

### Step 4: Frontend Setup (New Terminal)
```bash
# Start development server (dependencies already installed in Step 2)
npm start
```

Frontend will open at: **http://localhost:3000**

## Verify Setup

### Test Backend
```bash
# Health check
curl http://localhost:8000/api/health | jq

# Sample streaming query
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What are symptoms of diabetes?", "conversation_id": "test-123"}'

# Non-streaming query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are symptoms of diabetes?"}'
```

### Test Frontend
1. Open http://localhost:3000
2. Click a sample question or type your own
3. Watch the response stream token-by-token with source, confidence, and routing info

## Production Deployment

### Option 1: Docker (Recommended)

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build separately
docker build -t medical-rag .
docker run -p 8000:8000 --env-file .env medical-rag
```

### Option 2: AWS (Terraform)

All AWS infrastructure is defined in `terraform/`. It provisions ECS Fargate (backend), RDS PostgreSQL (vector store + history), S3 + CloudFront (frontend), ALB, ECR, and Secrets Manager.

```bash
cd terraform

# Pass secrets via env vars — never hard-code them in .tf files
export TF_VAR_openai_api_key="sk-..."
export TF_VAR_db_password="your-db-password"
export TF_VAR_app_api_key="your-secret-key"   # optional, leave empty to disable auth

# Initialise, preview, then apply
terraform init
terraform plan
# terraform apply   # uncomment when ready to deploy
```

After `apply`, push your Docker image to ECR and sync the React build to S3:
```bash
# Build and push backend image
ECR_URL=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URL
docker build -t $ECR_URL:latest .
docker push $ECR_URL:latest

# Build and deploy frontend
npm run build
S3_BUCKET=$(terraform output -raw s3_frontend_bucket)
aws s3 sync build/ s3://$S3_BUCKET --delete
```

**Google Cloud (Cloud Run):**
```bash
gcloud run deploy medical-rag \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=${OPENAI_API_KEY}
```

### Option 3: Manual VPS Deployment

```bash
# SSH into server
ssh user@your-server.com

# Install Python 3.11
sudo apt update && sudo apt install python3.11 python3.11-venv

# Clone repo
git clone https://github.com/yourusername/medical-rag.git
cd medical-rag

# Install all dependencies (Python + Node) and configure env
npm install
cp .env.example .env
# Edit .env with your keys

# Install & configure Nginx
sudo apt install nginx
# Configure reverse proxy to localhost:8000

# Run with systemd
sudo nano /etc/systemd/system/medical-rag.service
# [Service]
# ExecStart=/root/medical-rag/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
# WorkingDirectory=/root/medical-rag
# Restart=always
# Environment="PYTHONUNBUFFERED=1"

sudo systemctl start medical-rag
sudo systemctl enable medical-rag
```

## Security Checklist

- [x] Store secrets in `.env` (never commit)
- [x] Use environment variables for API keys
- [ ] Enable HTTPS/TLS for production
- [x] API key authentication via `X-API-Key` header (`API_KEY` env var)
- [x] Rate limiting — 20 req/min per IP via `slowapi`
- [x] CORS restricted to allowed origins (`ALLOWED_ORIGINS` env var)
- [x] Input validation — `sample_size` range-checked, CSV path removed from user input
- [x] PostgreSQL + pgvector for vector store and conversation history
- [ ] Monitor logs and errors
- [ ] Enable RDS automated backups (set `backup_retention_period` > 0 in `terraform/rds.tf`)
- [ ] Regular security updates

## Scaling Considerations

### Database
- **Current**: PostgreSQL + pgvector (`medical_qna`, `medical_device`, `conversation_turns` tables)
- **Schema** is created automatically by `init_schema()` + `init_history_schema()` on startup
- **AWS**: Managed via RDS PostgreSQL 16 (`terraform/rds.tf`), `db.t3.micro` by default — change `db_instance_class` in `terraform/variables.tf` for production

### Caching
Add Redis for query caching:
```python
import redis
cache = redis.Redis(host='localhost', port=6379)
```

### Load Balancing
```bash
# Use Gunicorn + multiple workers
gunicorn backend.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

## Development Workflow

### Add a New Feature

1. Create feature branch:
   ```bash
   git checkout -b feature/your-feature
   ```

2. Make changes in the relevant module:
   ```bash
   # Backend logic → backend/pipeline/nodes.py or backend/pipeline/graph.py
   # API endpoints → backend/routes/
   # Config → backend/config.py
   # Frontend → src/App.jsx or src/components/
   ```

3. Test locally:
   ```bash
   # Restart backend
   uvicorn backend.main:app --host 0.0.0.0 --port 8000

   # Test frontend
   npm start
   ```

4. Commit and push:
   ```bash
   git add .
   git commit -m "feat: add your feature"
   git push origin feature/your-feature
   ```

5. Create pull request (PR)

### Testing

```bash
# Backend tests
pytest tests/

# Frontend tests
npm test

# End-to-end tests
pytest tests/e2e/
```

## Troubleshooting

| Problem | Debug Steps | Solution |
|---------|-----------|----------|
| Backend won't start | Check Python version, pip list | `npm install` (re-runs postinstall), check Python 3.10+ |
| API key errors | Check `.env` exists & has keys | `cp .env.example .env` then add your keys |
| PostgreSQL connection error | Check `DATABASE_URL` in `.env` | Verify DB running: `pg_isready`; check credentials |
| pgvector extension missing | Connect to DB | Run `CREATE EXTENSION vector;` as superuser |
| Frontend can't connect | Check `http://localhost:8000/api/health` | Verify backend runs, check network tab |
| CORS errors | Check FastAPI CORS middleware | Ensure CORS is enabled for your domain |
| Port already in use | Find process holding port | `lsof -ti :8000 \| xargs kill -9` then restart |

## Configuration

All constants are in `backend/config.py`:

```python
LLM_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
DATABASE_URL = "postgresql://localhost/medical_rag"   # override via .env
N_RESULTS = 5               # Docs retrieved per query
MAX_ITERATIONS = 3          # Max relevance-check loops
MAX_HISTORY_TURNS = 10      # Conversation turns kept per session

# Set in .env to override:
ALLOWED_ORIGINS = "http://localhost:3000"  # Comma-separated CORS origins
API_KEY = ""                               # Enables X-API-Key auth when non-empty
```

## Support

- **Docs**: http://localhost:8000/docs
- **Logs**: JSON structured logs in terminal from `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- **Issues**: Check application logs and API response

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langgraph.com/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [React Documentation](https://react.dev/)

---

**Your Medical Agentic RAG is ready for production!**
