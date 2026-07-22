#!/usr/bin/env bash
set -euo pipefail

echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Backend deploy target: Render/Railway"
echo "Use: uvicorn backend.main:app --host 0.0.0.0 --port \$PORT"
