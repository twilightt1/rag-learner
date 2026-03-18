#!/bin/bash
# Run the RAG Learner backend (from project root)
set -e

echo "📦 Installing dependencies..."
pip install -r requirements.txt --quiet

echo "🎭 Installing Playwright browsers..."
playwright install chromium --with-deps 2>/dev/null || true

echo "🚀 Starting backend on http://localhost:8000"
echo "📖 API docs: http://localhost:8000/docs"

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload