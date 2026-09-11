#!/usr/bin/env bash
# Convenience wrapper: seed demo data into the running Docker Compose stack.
# Usage: ./scripts/seed_demo.sh
set -euo pipefail
docker compose exec backend python -m app.seed_demo
