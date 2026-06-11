#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

pids=()
trap 'kill "${pids[@]}" 2>/dev/null; exit' INT TERM

echo "Starting retrieval  → http://localhost:8081"
uvicorn retrieval.app.main:app    --port 8081 & pids+=($!)
echo "Starting agent      → http://localhost:8082"
uvicorn agent.app.main:app        --port 8082 & pids+=($!)
echo "Starting mcp_server → http://localhost:8083 (SSE)"
uvicorn mcp_server.app.server:app --port 8083 & pids+=($!)

echo
echo "All services running. Chat at http://localhost:8082"
echo "Press Ctrl-C to stop all."
wait
