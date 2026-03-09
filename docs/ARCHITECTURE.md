# Architecture

## Project Structure

```
medicalAgenticRag/
│
├── backend/                        # Python backend (FastAPI)
│   ├── config.py                   # Constants, env vars, JSON log formatter
│   ├── models.py                   # Pydantic schemas + GraphState TypedDict
│   ├── auth.py                     # API key dependency (X-API-Key header)
│   ├── limiter.py                  # Shared slowapi rate-limiter instance
│   ├── db.py                       # psycopg2 ThreadedConnectionPool (get_conn / get_vector_conn)
│   ├── history.py                  # PostgreSQL conversation store (conversation_turns table)
│   ├── vector_store.py             # pgvector tables, HNSW indexes, query/ingest functions
│   ├── pipeline/
│   │   ├── state.py                # compute_confidence() heuristic
│   │   ├── nodes.py                # All LangGraph node functions + LLM helper
│   │   └── graph.py                # build_agentic_rag(), query_rag(), stream_rag_response()
│   ├── routes/
│   │   ├── query.py                # POST /api/query, POST /api/query/stream
│   │   └── health.py               # GET /api/health, POST /api/ingest, GET /
│   └── main.py                     # FastAPI app, CORS, rate limiter, request ID middleware
│
├── src/                            # React frontend
│   └── agentic_rag_app.jsx         # Full chat UI (state, SSE streaming, message rendering)
│
├── data/                           # Datasets and generation scripts
│   ├── generate_data.py            # Synthetic CSV generator
│   ├── medical_q_n_a.csv           # 1000-row Q&A dataset (~298 unique pairs)
│   └── medical_device_manuals_dataset.csv  # 1000-row device dataset
│
├── terraform/                      # AWS infrastructure (Terraform)
│   ├── main.tf                     # Provider config, remote state backend
│   ├── variables.tf                # All configurable inputs
│   ├── outputs.tf                  # ALB URL, CloudFront URL, ECR URL, etc.
│   ├── vpc.tf                      # VPC, subnets, IGW, NAT Gateway, security groups
│   ├── iam.tf                      # ECS execution + task IAM roles
│   ├── secrets.tf                  # Secrets Manager (OPENAI_API_KEY, API_KEY, DATABASE_URL)
│   ├── ecr.tf                      # ECR repo + lifecycle policy
│   ├── rds.tf                      # RDS PostgreSQL 16 + parameter group (pgvector-ready)
│   ├── alb.tf                      # ALB, target group, HTTP listener
│   ├── ecs.tf                      # Fargate cluster, task definition, rolling-update service
│   ├── s3_cloudfront.tf            # Private S3 bucket + CloudFront OAC distribution
│   └── outputs.tf                  # All resource URLs and names
│
├── docs/                           # Documentation
├── public/index.html               # React HTML shell
├── requirements.txt                # Python dependencies
├── package.json                    # Node.js dependencies + postinstall hook
├── Dockerfile                      # Backend container (uvicorn entrypoint)
├── docker-compose.yml              # Local full-stack orchestration
└── .env                            # Secrets (not committed)
```

## What Makes This Agentic

Standard RAG always retrieves from the same source and generates. This system is agentic because:

1. **Dynamic routing** — an LLM decides at runtime which source to query (Q&A database, device manual database, or live web search) based on the nature of the question.

2. **Relevance checking loop** — after retrieval, a second LLM call evaluates whether the retrieved context actually answers the question. If not, it re-routes to web search and tries again.

3. **Conditional branching** — the LangGraph graph has real conditional edges that change execution path based on LLM decisions, not fixed rules.

4. **Fallback tool use** — DuckDuckGo search is used as a tool when local knowledge is insufficient, giving the system access to current information without a pre-indexed corpus.

## LangGraph Workflow

```
START
  ↓
router  (LLM at temperature=0 — deterministic)
  ├── "medical_knowledge" → retrieve_clinical
  ├── "device_manual"     → retrieve_device
  └── "web_search"        → web_search
          ↓
check_relevance  (LLM at temperature=0)
  ├── relevant     → augment → generate → END
  └── not relevant → web_search → check_relevance (loop, max 3 iterations)
```

Key design decisions:
- Router and relevance checker both run at `temperature=0` for deterministic, consistent routing
- The relevance loop has a hard cap of `MAX_ITERATIONS=3` to prevent infinite loops
- Web search is both a primary route and a fallback, keeping the graph simple

## Data Flow

```
User types query
    ↓
src/agentic_rag_app.jsx  (sendMessage)
    └── POST /api/query/stream  (SSE connection)
    ↓
backend/routes/query.py
    ├── Load conversation history from PostgreSQL
    └── stream_rag_response(query, history)
    ↓
backend/pipeline/graph.py
    ├── Run full LangGraph pipeline in thread pool
    ├── Emit SSE "meta" event  (source, routing reason, relevance)
    ├── Emit SSE "token" events  (streamed from OpenAI)
    └── Emit SSE "done" event  (full answer, confidence, timestamp)
    ↓
Browser renders streaming tokens with blinking cursor
    └── Finalises with source badge, confidence score, iteration count
```

## Database Design

All persistence is in **PostgreSQL + pgvector**. Three tables:

| Table | Purpose | Key Columns |
|-------|---------|------------|
| `medical_qna` | Q&A vector store | `id TEXT`, `content TEXT`, `embedding vector(1536)`, `metadata JSONB` |
| `medical_device` | Device manual vector store | `id TEXT`, `content TEXT`, `embedding vector(1536)`, `metadata JSONB` |
| `conversation_turns` | Chat history | `conversation_id TEXT`, `role TEXT`, `content TEXT`, `created_at TIMESTAMPTZ` |

Both vector tables use **HNSW indexes** (`vector_cosine_ops`) for fast approximate nearest-neighbour search. IDs are MD5 hashes of the source text, enabling safe upserts.

The connection pool (`backend/db.py`) exposes two functions:
- `get_conn()` — plain connection, used for DDL (`init_schema`) and counts
- `get_vector_conn()` — registers the pgvector adapter, used for insert and query operations

This separation ensures the pgvector adapter is only registered after the extension exists.

## Confidence Score

Computed in `backend/pipeline/state.py` — no extra LLM call:

| Condition | Score |
|-----------|-------|
| Medical Q&A Collection | 90% |
| Medical Device Manual | 85% |
| Web Search (success) | 65% |
| Web Search (failed/empty) | 40% |
| Context marked not relevant | −15% |
| Each extra iteration | −8% |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirect to `/docs` |
| GET | `/api/health` | System health + record counts |
| POST | `/api/ingest` | Load CSVs from `data/` into pgvector |
| POST | `/api/query` | Non-streaming query |
| POST | `/api/query/stream` | Streaming query (SSE) |

Query endpoints accept optional `X-API-Key` header when `API_KEY` env var is set.
Rate limit: 20 requests/min per IP.

## AWS Infrastructure

```
Internet
    │
    ├── CloudFront (HTTPS) → S3 (React build, private bucket + OAC)
    │
    └── ALB (HTTP) → ECS Fargate (FastAPI)
                         │
                         ├── RDS PostgreSQL 16 (private subnet, pgvector)
                         └── Secrets Manager (OPENAI_API_KEY, DATABASE_URL, API_KEY)
```

All ECS tasks run in private subnets. RDS is not publicly accessible. Secrets are injected as environment variables at task startup via Secrets Manager — never stored in the image or task definition plaintext.

## Key Configuration

All constants in `backend/config.py`:

```python
LLM_MODEL         = "gpt-4o-mini"
EMBED_MODEL       = "text-embedding-3-small"
DATABASE_URL      = "postgresql://localhost/medical_rag"  # override via .env
N_RESULTS         = 5        # documents retrieved per query
MAX_ITERATIONS    = 3        # max relevance-check loop iterations
MAX_HISTORY_TURNS = 10       # conversation turns kept per session
ALLOWED_ORIGINS   = "http://localhost:3000"
API_KEY           = ""       # enables X-API-Key auth when non-empty
```

Frontend API URL (baked in at build time):
```javascript
const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
```

Set `REACT_APP_API_URL` in `.env.production` before running `npm run build` for any non-local deployment.
