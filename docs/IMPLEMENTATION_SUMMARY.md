# Medical Agentic RAG – Implementation Summary

## What Was Built

A **production-grade Agentic RAG system** for medical knowledge retrieval, with LangGraph-based dynamic routing, streaming responses, and full AWS deployment via Terraform.

---

## File Reference

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `config.py` | Constants, env vars, JSON log formatter |
| `models.py` | Pydantic request/response schemas + `GraphState` TypedDict |
| `auth.py` | `require_api_key` FastAPI dependency — checks `X-API-Key` header |
| `limiter.py` | Shared `slowapi` rate-limiter (20 req/min per IP) |
| `db.py` | psycopg2 `ThreadedConnectionPool`; `get_conn()` (plain) and `get_vector_conn()` (pgvector adapter registered) |
| `history.py` | PostgreSQL conversation store (`conversation_turns` table) |
| `vector_store.py` | pgvector tables with HNSW indexes; `init_schema()`, `query_qna()`, `query_device()`, `ingest_data()` |
| `pipeline/state.py` | `compute_confidence()` heuristic — no extra LLM call |
| `pipeline/nodes.py` | All LangGraph node functions: `router_node`, `retrieve_clinical`, `retrieve_device`, `web_search`, `check_relevance`, `augment`, `generate` |
| `pipeline/graph.py` | `build_agentic_rag()` graph builder; `query_rag()` executor; `stream_rag_response()` SSE generator |
| `routes/query.py` | `POST /api/query` and `POST /api/query/stream` (auth + rate limited) |
| `routes/health.py` | `GET /api/health`, `POST /api/ingest`, `GET /` |
| `main.py` | FastAPI app init, CORS middleware, rate limiter mount, request-ID middleware |

### Frontend (`src/`)

| File | Purpose |
|------|---------|
| `agentic_rag_app.jsx` | Full chat UI: SSE stream consumption, message state, routing badges, confidence scores, streaming cursor |

### Data (`data/`)

| File | Purpose |
|------|---------|
| `generate_data.py` | Generates synthetic datasets using all `CONDITIONS × QNA_TEMPLATES` combinations for unique rows |
| `medical_q_n_a.csv` | 1000-row Q&A dataset (~298 unique pairs after deduplication) |
| `medical_device_manuals_dataset.csv` | 1000-row device manual dataset |

### Infrastructure

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `package.json` | Node.js deps + `postinstall` script (creates `.venv` + pip install) |
| `.env.example` | Secrets template |
| `.env.production` | Frontend build env — sets `REACT_APP_API_URL` to the ALB URL before `npm run build` |
| `Dockerfile` | Backend container image (uvicorn entrypoint, `linux/amd64`) |
| `docker-compose.yml` | Local full-stack orchestration |

### Terraform (`terraform/`)

| File | Purpose |
|------|---------|
| `main.tf` | AWS provider, Terraform version constraint, optional S3 remote state |
| `variables.tf` | All inputs: region, CPU/memory, secrets, DB class, frontend domain |
| `outputs.tf` | `backend_url`, `frontend_url`, `ecr_repository_url`, `s3_frontend_bucket`, `rds_endpoint` |
| `vpc.tf` | VPC, public/private subnets across 2 AZs, IGW, NAT Gateway, security groups |
| `iam.tf` | ECS execution role (ECR + CloudWatch + Secrets Manager) + task role |
| `secrets.tf` | Secrets Manager secrets: `OPENAI_API_KEY`, `API_KEY`, `DATABASE_URL` |
| `ecr.tf` | ECR repository + image lifecycle policy |
| `rds.tf` | RDS PostgreSQL 16 in private subnets; custom parameter group; pgvector-compatible |
| `alb.tf` | Application Load Balancer, target group, HTTP listener, CloudWatch log group |
| `ecs.tf` | Fargate cluster + task definition (secrets injected from Secrets Manager) + rolling-update service |
| `s3_cloudfront.tf` | Private S3 bucket + CloudFront distribution with OAC (no public bucket access) |

---

## Agentic Pipeline

The pipeline is a LangGraph directed graph with conditional edges:

```
START → Router → [retrieve_clinical | retrieve_device | web_search]
                           ↓
              check_relevance
                ├── relevant   → augment → generate → END
                └── irrelevant → web_search → check_relevance (max 3 loops)
```

- **router** and **check_relevance** both use `temperature=0` for deterministic decisions
- **web_search** uses DuckDuckGo — no API key required
- The loop cap (`MAX_ITERATIONS=3`) prevents runaway retries

---

## Key Design Decisions

**pgvector connection split**
`get_conn()` returns a plain connection for schema DDL. `get_vector_conn()` calls `register_vector(conn)` for vector operations. This ensures the pgvector adapter is registered only after `CREATE EXTENSION vector` has run.

**Stable upsert IDs**
Vector store IDs are MD5 hashes of the source text (`hashlib.md5(question.encode()).hexdigest()`). Re-ingesting the same data is safe — rows are updated in place via `ON CONFLICT (id) DO UPDATE`.

**Data generation uniqueness**
`generate_data.py` uses nested loops over all `CONDITIONS × QNA_TEMPLATES` combinations, producing ~298 unique Q&A pairs. Ingest also calls `drop_duplicates()` as a safety net.

**Frontend API URL baked at build time**
`REACT_APP_API_URL` must be set in `.env.production` before running `npm run build`. React's `process.env` substitution happens at compile time, not runtime. After updating S3, invalidate the CloudFront cache to push the new bundle to edge nodes.

**Docker platform**
Always build the backend image with `--platform linux/amd64`. ECS Fargate runs x86_64 regardless of the build machine architecture.

---

## Configuration

All constants in `backend/config.py` — override with environment variables:

```python
LLM_MODEL         = "gpt-4o-mini"
EMBED_MODEL       = "text-embedding-3-small"
DATABASE_URL      = "postgresql://localhost/medical_rag"
N_RESULTS         = 5
MAX_ITERATIONS    = 3
MAX_HISTORY_TURNS = 10
ALLOWED_ORIGINS   = "http://localhost:3000"
API_KEY           = ""
```

---

## Common Customizations

| Goal | Where to change |
|------|----------------|
| Switch LLM model | `LLM_MODEL` in `backend/config.py` |
| Retrieve more documents | `N_RESULTS` in `backend/config.py` |
| Change routing logic | `router_node()` in `backend/pipeline/nodes.py` |
| Change answer prompt | `augment()` in `backend/pipeline/nodes.py` |
| Add a new SSE event type | `stream_rag_response()` in `backend/pipeline/graph.py` |
| Add a new UI component | `src/components/` |
| Add a new data source | New table in `vector_store.py` + new node in `nodes.py` + new edge in `graph.py` |

---

## Documentation Index

| File | Contents |
|------|---------|
| [QUICKSTART.md](QUICKSTART.md) | 5-minute local setup |
| [SETUP.md](SETUP.md) | Full setup + AWS deployment |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, LangGraph workflow |
| http://localhost:8000/docs | Interactive API documentation (Swagger UI) |
