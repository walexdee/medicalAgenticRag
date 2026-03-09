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

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 17 with pgvector

Install PostgreSQL 17 (macOS):
```bash
brew install postgresql@17
brew services start postgresql@17
echo 'export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Install PostgreSQL 17 (Ubuntu/Debian):
```bash
sudo apt install -y postgresql-17 postgresql-17-pgvector
sudo systemctl start postgresql
```

### 2. Create the Database

```bash
createdb medical_rag
psql medical_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

> The `vector` extension must exist before the backend starts. Tables are created automatically on first startup.

### 3. Install Dependencies

```bash
git clone https://github.com/yourusername/medicalAgenticRag.git
cd medicalAgenticRag
npm install
```

This installs all Node packages **and** automatically creates `.venv` and installs all Python packages via the `postinstall` script in `package.json`.

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

> On macOS, `<your-system-username>` is the output of `whoami`. No password is needed for a local PostgreSQL install.

### 5. Generate Data

```bash
source .venv/bin/activate
python data/generate_data.py
```

This creates `data/medical_q_n_a.csv` (1000 rows, ~298 unique Q&A pairs) and `data/medical_device_manuals_dataset.csv` (1000 device records).

### 6. Start the Backend

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
{"level": "INFO", "message": "PostgreSQL schema ready"}
```

### 7. Ingest Data

```bash
curl -X POST http://localhost:8000/api/ingest
```

Expected response:
```json
{"status": "ok", "qa": 298, "device": 500}
```

### 8. Start the Frontend

```bash
# New terminal
npm start
```

Browser opens at http://localhost:3000.

## Verify Setup

```bash
curl http://localhost:8000/api/health | python3 -m json.tool
```

Expected:
```json
{
  "status": "healthy",
  "models": { "llm": "gpt-4o-mini", "embeddings": "text-embedding-3-small" },
  "databases": { "qa_collection_count": 298, "device_collection_count": 500 }
}
```

## Test Queries

| Query | Expected Route |
|-------|---------------|
| "What are symptoms of diabetes?" | Medical Q&A |
| "Contraindications for a pacemaker?" | Device Manual |
| "Latest COVID-19 antiviral medications?" | Web Search |

## What You Get

- **Backend API** at http://localhost:8000
- **Frontend UI** at http://localhost:3000
- **API Documentation** at http://localhost:8000/docs
- Streaming responses (token-by-token via SSE)
- Confidence scores and routing badges on every response
- Persistent conversation history per session

## Documentation

- **Full Setup & Deployment**: [SETUP.md](SETUP.md)
- **Architecture & Data Flow**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Implementation Details**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
