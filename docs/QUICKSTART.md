# Quick Start

## TL;DR

```bash
# Terminal 1: Backend
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
npm start

# Open http://localhost:3000
```

## Step-by-Step

### 1. Install Dependencies (First time only)

```bash
npm install
```

This installs all Node packages **and** automatically creates a Python virtual environment (`.venv`) and installs all Python packages via the `postinstall` script in `package.json`.

### 2. Configure API Keys & Database

```bash
cp .env.example .env
# Edit .env and add:
# OPENAI_API_KEY=sk-...
# DATABASE_URL=postgresql://postgres:password@localhost/medical_rag
```

Create the database (first time only):
```bash
psql -U postgres -c "CREATE DATABASE medical_rag;"
# Tables and pgvector extension are created automatically on first backend start
```

### 3. Run Backend (Terminal 1)

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

### 4. Run Frontend (Terminal 2)

```bash
npm start
```

Browser opens at http://localhost:3000

### 5. Test It

1. Click a sample question or type your own
2. Watch the response stream in token-by-token
3. Check the source badge, confidence score, and routing info in each response

## Verify Setup

### Backend Health
```bash
curl http://localhost:8000/api/health | jq
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models": { "llm": "gpt-4o-mini", "embeddings": "text-embedding-3-small" },
  "databases": { "database_url": "localhost/medical_rag", "qa_collection_count": 500, "device_collection_count": 500 }
}
```

### Test Streaming Query
```bash
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is diabetes?", "conversation_id": "test-123"}'
```

### Test Non-Streaming Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is diabetes?"}'
```

## What You Get

- **Backend API** on http://localhost:8000
- **Frontend UI** on http://localhost:3000
- **API Documentation** on http://localhost:8000/docs
- **Streaming responses** via SSE (token-by-token)
- **Conversation history** per session
- **Confidence scores** on every response
- **Vector Database** (PostgreSQL + pgvector) with 500 Q&A + 500 Device records

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | `npm install` (re-runs postinstall) |
| `OPENAI_API_KEY not found` | `cp .env.example .env` + add your key |
| `DATABASE_URL not set` | Add `DATABASE_URL=postgresql://...` to `.env` |
| PostgreSQL connection failed | Check DB is running: `pg_isready` |
| Backend won't start | Check Python 3.10+: `python3 --version` |
| Frontend can't connect | Verify backend runs: `curl http://localhost:8000/api/health` |
| Port already in use | `lsof -ti :8000 \| xargs kill -9` then restart |

## Documentation

- **Full Setup**: See [SETUP.md](SETUP.md)
- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **API Docs**: Visit http://localhost:8000/docs
