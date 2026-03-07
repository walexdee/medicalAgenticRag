# Medical Agentic RAG – Production System

A production-grade **Agentic Retrieval-Augmented Generation (RAG)** system for medical knowledge, powered by **FastAPI**, **LangGraph**, and **PostgreSQL + pgvector**.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ React Frontend (src/App.jsx)                            │
│ - Streaming chat UI (token-by-token via SSE)            │
│ - Source badge, confidence score, routing info          │
│ - Conversation history per session                      │
└──────────────────┬──────────────────────────────────────┘
                   │ SSE + REST API
┌──────────────────▼──────────────────────────────────────┐
│ FastAPI Backend (backend/)                              │
│ ┌─────────────────────────────────────────────┐        │
│ │ LangGraph Agentic Workflow                  │        │
│ │  START → Router → [QnA|Device|Web] →       │        │
│ │          Relevance Check → Augment →       │        │
│ │          Generate → END                     │        │
│ └─────────────────────────────────────────────┘        │
│ - OpenAI GPT-4o-mini (routing, generation)             │
│ - OpenAI Embeddings (similarity search)                │
│ - DuckDuckGo Search (web search, free)                 │
│ - Streaming SSE responses                              │
│ - PostgreSQL-backed conversation history + vectors     │
│ - Heuristic confidence scoring                         │
└──────────────────┬──────────────────────────────────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
┌────▼──────┐ ┌───▼──────┐ ┌───▼───────┐
│PostgreSQL │ │OpenAI    │ │DuckDuckGo │
│+ pgvector │ │API       │ │(free)     │
│(QnA+Dev.) │ │(LLM)     │ │           │
└───────────┘ └──────────┘ └───────────┘
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 16+ with pgvector extension
- OpenAI API key

### 1. Install All Dependencies

```bash
cd Medical_RAG

# Installs Node packages AND creates .venv + installs Python packages automatically
npm install

# Configure environment
cp .env.example .env
# Edit .env and add:
# OPENAI_API_KEY=sk-...
# DATABASE_URL=postgresql://postgres:password@localhost/medical_rag
```

### 2. Start Backend

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Expected output (JSON structured logs):
```
INFO:     Uvicorn running on http://0.0.0.0:8000
{"time": "...", "level": "INFO", "logger": "backend.main", "message": "Starting Medical Agentic RAG Backend"}
{"time": "...", "level": "INFO", "logger": "backend.main", "message": "PostgreSQL schema ready"}
```

### 3. Start Frontend

In a new terminal:

```bash
npm start
```

The frontend opens at `http://localhost:3000`

## API Endpoints

### `POST /api/query/stream`
Streaming RAG query endpoint (SSE).

**Request:**
```json
{
  "query": "What are contraindications for a pacemaker?",
  "conversation_id": "session-uuid"
}
```

**SSE Events:**
```
data: {"type": "meta", "source": "Medical Q&A Collection", "routing": "Retrieve_QnA", ...}

data: {"type": "token", "token": "Contra"}
data: {"type": "token", "token": "indications"}
...

data: {"type": "done", "answer": "...", "confidence": 0.9, "timestamp": "..."}
```

### `POST /api/query`
Non-streaming RAG query endpoint.

**Response:**
```json
{
  "query": "What are contraindications for a pacemaker?",
  "answer": "Contraindications include active infections...",
  "source": "Medical Q&A Collection",
  "confidence": 0.9,
  "source_info": { "routing": "Retrieve_QnA", "reason": "..." },
  "relevance": { "is_relevant": true, "reason": "..." },
  "iteration_count": 1,
  "timestamp": "2025-03-06T10:30:45.123456"
}
```

### `GET /api/health`
Backend health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models": { "llm": "gpt-4o-mini", "embeddings": "text-embedding-3-small" },
  "databases": { "database_url": "localhost/medical_rag", "qa_collection_count": 500, "device_collection_count": 500 }
}
```

### `POST /api/ingest`
Ingest medical data into PostgreSQL (pgvector).

**Query parameters:**
- `sample_size` (int, 1–5000, default 500) — how many rows to ingest from each CSV

## Workflow

1. **Router** reads the query and decides retrieval source (QnA / Device / Web)
2. **Retriever** fetches relevant documents from ChromaDB or DuckDuckGo
3. **Relevance Checker** validates if context answers the question
   - If relevant → proceeds to augmentation
   - If not relevant → falls back to web search (max 3 iterations)
4. **Augment** builds a RAG prompt with context + conversation history
5. **Generate** streams the answer token-by-token via SSE

## Configuration

All constants in `backend/config.py`:

```python
LLM_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
DATABASE_URL = "postgresql://localhost/medical_rag"   # override via .env
N_RESULTS = 5               # Docs retrieved per query
MAX_ITERATIONS = 3          # Max relevance-check loops
MAX_HISTORY_TURNS = 10      # Conversation turns kept in memory
```

## Confidence Scores

Heuristic based on pipeline outcome (no extra LLM call):

| Condition | Score |
|-----------|-------|
| Medical Q&A Collection | 90% |
| Medical Device Manual | 85% |
| Web Search (working) | 65% |
| Web Search (failed) | 40% |
| Context not relevant | −15% |
| Each extra iteration | −8% |

## Data Ingestion

CSVs live in `data/`:

- `data/medical_q_n_a.csv` — 1000-row Q&A dataset
- `data/medical_device_manuals_dataset.csv` — 1000-row device dataset

Re-generate with:
```bash
python data/generate_data.py
```

Ingest via API:
```bash
curl -X POST "http://localhost:8000/api/ingest?sample_size=500"
```

> **Note**: The `/api/ingest` endpoint uses `ON CONFLICT ... DO UPDATE` so it is safe to call multiple times.

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

All AWS infrastructure is defined in [terraform/](terraform/). It provisions:
- **ECS Fargate** — backend container
- **ECR** — Docker image registry
- **ALB** — public load balancer
- **RDS PostgreSQL 16** — vector store + conversation history (replaces EFS + SQLite + ChromaDB)
- **S3 + CloudFront** — React frontend hosting
- **Secrets Manager** — `OPENAI_API_KEY`, `DATABASE_URL`, and `API_KEY`

```bash
cd terraform
export TF_VAR_openai_api_key="sk-..."
export TF_VAR_db_password="your-db-password"
export TF_VAR_app_api_key="your-secret-key"   # optional
terraform init
terraform plan
# terraform apply   # when ready to deploy
```

### Production Considerations

- Use Gunicorn + Uvicorn workers for multi-process serving
- **Rate limiting** — already implemented (20 req/min per IP via `slowapi`)
- **API key auth** — already implemented (`API_KEY` env var + `X-API-Key` header)
- **CORS** — already restricted via `ALLOWED_ORIGINS` env var
- **PostgreSQL + pgvector** — already implemented (replaces ChromaDB + SQLite)
- Add monitoring (Prometheus/Grafana)
- Cache frequent queries with Redis
- Use HTTPS/TLS

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `OPENAI_API_KEY not set` | Copy `.env.example` → `.env`, fill in your key |
| Backend won't start | `npm install` (re-runs postinstall), check Python 3.10+ |
| `DATABASE_URL not set` | Add `DATABASE_URL=postgresql://...` to `.env` |
| PostgreSQL connection error | Check DB is running: `pg_isready`; verify DATABASE_URL |
| pgvector extension missing | Run `CREATE EXTENSION vector;` in your database |
| Port already in use | `lsof -ti :8000 \| xargs kill -9` |
| Frontend can't reach API | Ensure backend runs on 8000, CORS enabled |
| Web search failing | Check internet; DuckDuckGo requires no API key |

## Documentation

- **Quick Start**: [QUICKSTART.md](docs/QUICKSTART.md)
- **Full Setup & Deployment**: [SETUP.md](docs/SETUP.md)
- **Architecture & Data Flow**: [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **API Docs**: http://localhost:8000/docs

## License

MIT
