#!/usr/bin/env bash
set -euo pipefail

# Support Render services configured either at repo root or backend root.
if [ -f "backend/app.py" ]; then
  cd backend
fi

exec gunicorn app:app --bind 0.0.0.0:${PORT:-5000}
