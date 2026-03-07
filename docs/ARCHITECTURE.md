# Project Structure

```
Medical_RAG/
│
├── backend/                        # Python backend (FastAPI)
│   ├── config.py                   # Constants, env vars, JSON log formatter
│   ├── models.py                   # Pydantic schemas + GraphState TypedDict
│   ├── auth.py                     # API key dependency (X-API-Key header)
│   ├── limiter.py                  # Shared slowapi rate-limiter instance
│   ├── db.py                       # Shared psycopg2 ThreadedConnectionPool (get_conn/put_conn)
│   ├── history.py                  # PostgreSQL conversation store (conversation_turns table)
│   ├── vector_store.py             # pgvector tables, HNSW indexes, query_qna/query_device, ingest
│   ├── pipeline/
│   │   ├── state.py                # compute_confidence() heuristic
│   │   ├── nodes.py                # All LangGraph node functions + LLM helper
│   │   └── graph.py                # build_agentic_rag(), query_rag(), stream_rag_response()
│   ├── routes/
│   │   ├── query.py                # POST /api/query, POST /api/query/stream (auth + rate limited)
│   │   └── health.py               # GET /api/health, POST /api/ingest, GET /
│   └── main.py                     # FastAPI app, CORS, rate limiter, request ID middleware
│
├── src/                            # React frontend
│   ├── index.js                    # React entry point
│   ├── App.jsx                     # Main shell (state, sendMessage, layout)
│   ├── constants.js                # SOURCE_COLORS, SAMPLE_QUESTIONS, API_BASE
│   └── components/
│       ├── Header.jsx              # Top bar with status badges
│       ├── MessageBubble.jsx       # Message rendering (all states)
│       └── TypingIndicator.jsx     # Animated loading dots
│
├── data/                           # Datasets and generation scripts
│   ├── generate_data.py            # Synthetic CSV generator
│   ├── medical_q_n_a.csv           # 1000-row Q&A dataset
│   └── medical_device_manuals_dataset.csv  # 1000-row device dataset
│
├── terraform/                      # AWS infrastructure (Terraform)
│   ├── main.tf                     # Provider config + remote state backend
│   ├── variables.tf                # All configurable inputs
│   ├── outputs.tf                  # ALB URL, CloudFront URL, ECR URL, etc.
│   ├── vpc.tf                      # VPC, subnets, IGW, NAT Gateway, security groups
│   ├── iam.tf                      # ECS execution role + task role
│   ├── secrets.tf                  # Secrets Manager (OPENAI_API_KEY, API_KEY)
│   ├── ecr.tf                      # ECR repo + lifecycle policy
│   ├── rds.tf                      # RDS PostgreSQL 16 + DB subnet group + parameter group
│   ├── alb.tf                      # ALB, target group, HTTP listener, CloudWatch logs
│   ├── ecs.tf                      # Fargate cluster, task definition, rolling-update service
│   └── s3_cloudfront.tf            # S3 bucket + CloudFront distribution for React frontend
│
├── public/
│   └── index.html
│   (PostgreSQL tables created automatically on startup — no local files needed)
├── requirements.txt
├── package.json                    # postinstall: creates .venv + pip install
├── Dockerfile                      # Backend image (uvicorn entrypoint)
├── docker-compose.yml              # Local full-stack orchestration
└── .env
```

## Data Flow

```
User Input
    ↓
src/App.jsx  (sendMessage)
    ├─ POST /api/query/stream  (SSE)
    └─ Reads token-by-token stream
    ↓
backend/routes/query.py  (api_query_stream)
    ├─ get_history(conversation_id)
    └─ stream_rag_response(query, history)
    ↓
backend/pipeline/graph.py  (stream_rag_response)
    ├─ [thread pool] query_rag() → full LangGraph pipeline
    │       ↓
    │   Router → Retrieve_QnA / Retrieve_Device / Web_Search
    │       ↓
    │   Relevance_Checker (up to MAX_ITERATIONS=3)
    │       ↓
    │   Augment → Generate
    ├─ Emit: SSE meta event (source, routing, relevance)
    ├─ Emit: SSE token events (streamed from OpenAI)
    └─ Emit: SSE done event (answer, confidence, timestamp)
    ↓
src/components/MessageBubble.jsx
    ├─ Shows source badge + routing reason
    ├─ Shows confidence score (color-coded)
    ├─ Streams tokens with blinking cursor
    └─ Shows timestamp + iteration count when done
```

## LangGraph Workflow

```
START
  ↓
Router (LLM decides: QnA / Device / Web)
  ↓
┌─────────────────────────────────────┐
│  Retrieve_QnA   Retrieve_Device   Web_Search
└─────────────────────────────────────┘
  ↓
Relevance_Checker
  ├─ Yes → Augment → Generate → END
  └─ No  → Web_Search (loop, max 3 iterations)
```

## Confidence Score

Heuristic based on pipeline outcome (no extra LLM call):

| Condition | Base Score |
|-----------|-----------|
| Medical Q&A Collection | 90% |
| Medical Device Manual | 85% |
| Web Search (working) | 65% |
| Web Search (failed) | 40% |
| Context not relevant | −15% |
| Each extra iteration | −8% |

## Key Configuration

All constants in `backend/config.py`. Override any with environment variables:

```python
LLM_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
DATABASE_URL = "postgresql://localhost/medical_rag"   # override via .env
N_RESULTS = 5               # Docs retrieved per query
MAX_ITERATIONS = 3          # Max relevance-check loops
MAX_HISTORY_TURNS = 10      # Conversation turns kept per session

# Set these in .env for production:
ALLOWED_ORIGINS = "http://localhost:3000"   # Comma-separated allowed CORS origins
API_KEY = ""                                # If set, require X-API-Key header on all queries
```

## Features

- **Streaming responses** — SSE via `POST /api/query/stream`
- **Persistent conversation history** — PostgreSQL-backed, survives restarts, per `conversation_id`
- **Confidence scores** — heuristic badge on every response
- **Intelligent routing** — LLM routes each query to the best source
- **Relevance checking** — fallback to web search if retrieved context is off-topic
- **DuckDuckGo fallback** — free web search, no API key required
- **API key auth** — optional `X-API-Key` header check (set `API_KEY` env var to enable)
- **Rate limiting** — 20 requests/min per IP on query endpoints
- **CORS control** — configurable allowed origins via `ALLOWED_ORIGINS` env var
- **JSON structured logs** — every log line is a JSON object; includes `request_id` for tracing
- **Request ID tracing** — every request gets a UUID, returned in `X-Request-ID` response header

## Deployment

### Docker
```bash
docker build -t medical-rag .
docker run -p 8000:8000 --env-file .env medical-rag
```

### Docker Compose
```bash
docker-compose up
```

### AWS (Terraform)
See [terraform/](terraform/) for the full infrastructure config. Resources provisioned:
- **ECS Fargate** — runs the backend container
- **ECR** — stores the Docker image
- **ALB** — public load balancer in front of ECS
- **RDS PostgreSQL 16** — vector store (pgvector) + conversation history (replaces EFS + ChromaDB + SQLite)
- **S3 + CloudFront** — hosts the React frontend
- **Secrets Manager** — stores `OPENAI_API_KEY`, `DATABASE_URL`, and `API_KEY`

```bash
cd terraform
export TF_VAR_openai_api_key="sk-..."
export TF_VAR_db_password="your-db-password"
export TF_VAR_app_api_key="your-secret-key"
terraform init
terraform plan
# terraform apply  # when ready to deploy
```

### Manual
```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000    # Backend on :8000
npm start                                               # Frontend on :3000
```
