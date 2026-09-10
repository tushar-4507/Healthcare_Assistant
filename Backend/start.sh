#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "🔁 Building/loading FAISS Vectorstore..."
python creatememoryllm.py

echo "🚀 Starting FastAPI server..."
uvicorn api:app --host 0.0.0.0 --port 8000
