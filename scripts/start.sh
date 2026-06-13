#!/bin/bash
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env file — fill in your API keys before starting"
  exit 1
fi

pip install -r requirements.txt -q
uvicorn app.main:app --reload --port 8000
