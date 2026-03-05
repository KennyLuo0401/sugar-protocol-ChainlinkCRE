#!/bin/bash
set -e

echo "🍬 Sugar Protocol — Starting..."

# Set PYTHONPATH
export PYTHONPATH=/app

# Run uvicorn
exec uvicorn api.main:app 
    --host 0.0.0.0 
    --port 8000 
    --workers ${WORKERS:-1} 
    --log-level ${LOG_LEVEL:-info}
