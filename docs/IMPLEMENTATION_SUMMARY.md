# Medical Agentic RAG – Implementation Summary

## What Was Built

A **production-grade Agentic RAG system** for medical knowledge with:

### Backend (FastAPI + LangGraph)

Structured as a Python package under `backend/`:

| File | Purpose |
|------|---------|
| `backend/config.py` | Constants, env vars, JSON log formatter |
| `backend/models.py` | Pydantic schemas + `GraphState` TypedDict |
| `backend/auth.py` | `require_api_key` dependency — checks `X-API-Key` header |
| `backend/limiter.py` | Shared `slowapi` rate-limiter (20 req/min per IP) |
| `backend/db.py` | Shared psycopg2 `ThreadedConnectionPool` (`get_conn()`/`put_conn()`) |
| `backend/history.py` | PostgreSQL conversation store (`conversation_turns` table) |
| `backend/vector_store.py` | pgvector tables, HNSW indexes, `init_schema()`, `query_qna()`, `query_device()`, `count_*()`, ingest |
| `backend/pipeline/state.py` | `compute_confidence()` heuristic |
| `backend/pipeline/nodes.py` | All LangGraph node functions + LLM helper |
| `backend/pipeline/graph.py` | `build_agentic_rag()`, `query_rag()`, `stream_rag_response()` |
| `backend/routes/query.py` | `POST /api/query`, `POST /api/query/stream` (auth + rate limited) |
| `backend/routes/health.py` | `GET /api/health`, `POST /api/ingest`, `GET /` |
| `backend/main.py` | FastAPI app, CORS, rate limiter, request ID middleware |

### Frontend (React)

Structured under `src/`:

| File | Purpose |
|------|---------|
| `src/index.js` | React entry point |
| `src/App.jsx` | Main shell (state, SSE stream consumption, layout) |
| `src/constants.js` | `SOURCE_COLORS`, `SAMPLE_QUESTIONS`, `API_BASE` |
| `src/components/Header.jsx` | Top bar with status badges |
| `src/components/MessageBubble.jsx` | Message rendering with streaming cursor + confidence badge |
| `src/components/TypingIndicator.jsx` | Animated loading dots |

### Data

| File | Purpose |
|------|---------|
| `data/generate_data.py` | Synthetic CSV generator |
| `data/medical_q_n_a.csv` | 1000-row Q&A dataset |
| `data/medical_device_manuals_dataset.csv` | 1000-row device dataset |

### Infrastructure

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `package.json` | Node.js dependencies + `postinstall` (creates `.venv` + pip install) |
| `.env.example` | Secrets template |
| `Dockerfile` | Container image (uvicorn entrypoint) |
| `docker-compose.yml` | Local full-stack orchestration |
| `terraform/main.tf` | AWS provider config, remote state backend |
| `terraform/variables.tf` | All configurable inputs (region, CPU, secrets, etc.) |
| `terraform/vpc.tf` | VPC, public/private subnets, IGW, NAT Gateway, security groups |
| `terraform/iam.tf` | ECS execution + task IAM roles |
| `terraform/secrets.tf` | Secrets Manager for `OPENAI_API_KEY`, `API_KEY`, and `DATABASE_URL` |
| `terraform/ecr.tf` | ECR repo + image lifecycle policy |
| `terraform/rds.tf` | RDS PostgreSQL 16 + DB subnet group + parameter group |
| `terraform/alb.tf` | ALB, target group, HTTP listener, CloudWatch log group |
| `terraform/ecs.tf` | Fargate cluster, task definition (secrets incl. `DATABASE_URL`), rolling service |
| `terraform/s3_cloudfront.tf` | Private S3 bucket + CloudFront OAC distribution |
| `terraform/outputs.tf` | ALB URL, CloudFront URL, ECR URL, cluster/service names |

## Architecture Overview

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

## How to Start

```bash
# Terminal 1: Backend
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
npm start
```

## Key Features

- **Streaming responses** — SSE via `POST /api/query/stream`
- **Persistent conversation history** — PostgreSQL-backed, survives restarts
- **Confidence scores** — heuristic badge (no extra LLM call)
- **Intelligent routing** — LLM routes each query to best source
- **Relevance checking** — fallback to web search if retrieved context is off-topic
- **DuckDuckGo fallback** — free web search, no API key required
- **API key auth** — optional `X-API-Key` header (set `API_KEY` env var to enable)
- **Rate limiting** — 20 req/min per IP via `slowapi`
- **JSON structured logs** — every log line is JSON with `request_id` for tracing

## Confidence Score Heuristic

Computed in `backend/pipeline/state.py`:

| Condition | Score |
|-----------|-------|
| Medical Q&A Collection | 90% |
| Medical Device Manual | 85% |
| Web Search (working) | 65% |
| Web Search (failed) | 40% |
| Context not relevant | −15% |
| Each extra iteration | −8% |

## Configuration

All constants in `backend/config.py`. Override with environment variables:

```python
LLM_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
DATABASE_URL = "postgresql://localhost/medical_rag"   # override via .env
N_RESULTS = 5
MAX_ITERATIONS = 3
MAX_HISTORY_TURNS = 10

# Production overrides (set in .env):
ALLOWED_ORIGINS = "http://localhost:3000"   # Comma-separated CORS origins
API_KEY = ""                                # Enables X-API-Key auth when set
```

Frontend API endpoint in `src/constants.js`:
```javascript
export const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
```

## Common Customizations

- **Change LLM**: edit `LLM_MODEL` in `backend/config.py`
- **More retrieval results**: increase `N_RESULTS`
- **Change routing logic**: edit `router_node` in `backend/pipeline/nodes.py`
- **Change augment prompt**: edit `augment_node` in `backend/pipeline/nodes.py`
- **Add new SSE event types**: edit `stream_rag_response` in `backend/pipeline/graph.py`
- **Add new UI components**: add to `src/components/`

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

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | `npm install` (re-runs postinstall to recreate `.venv`) |
| `OPENAI_API_KEY not found` | `cp .env.example .env` + add your key |
| `DATABASE_URL not set` | Add `DATABASE_URL=postgresql://...` to `.env` |
| PostgreSQL connection error | Check DB is running: `pg_isready`; verify credentials |
| pgvector extension missing | Run `CREATE EXTENSION vector;` as superuser |
| Port already in use | `lsof -ti :8000 \| xargs kill -9` |
| Frontend can't connect | Verify backend: `curl http://localhost:8000/api/health` |

## Documentation

- **QUICKSTART.md** — 5-minute setup
- **SETUP.md** — Full deployment guide
- **ARCHITECTURE.md** — System design, data flow, LangGraph workflow
- **API Docs** — http://localhost:8000/docs
