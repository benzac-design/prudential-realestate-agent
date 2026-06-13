#!/bin/bash
# Reads .env and pushes each var to Vercel production
set -e

ENV_FILE="$(dirname "$0")/../.env"

while IFS='=' read -r key value; do
  # Skip comments and empty lines
  [[ "$key" =~ ^#.*$ ]] && continue
  [[ -z "$key" ]] && continue

  echo "Adding $key..."
  echo "$value" | npx vercel env add "$key" production --scope benprojects --force 2>&1
done < "$ENV_FILE"

echo "Done. All env vars added to Vercel."
