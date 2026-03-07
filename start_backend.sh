#!/bin/bash

# Medical Agentic RAG – Backend Startup Script
# =============================================

set -e

echo "🏥 Starting Medical Agentic RAG Backend..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env with your API keys and run this script again."
    exit 1
fi

# Check for required API keys
if ! grep -q "OPENAI_API_KEY=sk-" .env; then
    echo "❌ OPENAI_API_KEY not set in .env"
    exit 1
fi

echo "✓ Environment configured"
echo ""

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "✓ Virtual environment ready"
echo ""

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "📚 Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Start backend
echo "🚀 Starting FastAPI server on http://0.0.0.0:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo "❌ Press Ctrl+C to stop"
echo ""

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info
