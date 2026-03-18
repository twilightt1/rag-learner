#!/bin/bash
set -e
cd frontend
echo "📦 Installing frontend dependencies..."
npm install
echo "🚀 Starting frontend on http://localhost:5173"
npm run dev
