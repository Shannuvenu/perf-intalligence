#!/usr/bin/env bash
# Convenience wrapper: run the backend test suite inside the Docker Compose
# stack's backend container image (build it first if you haven't).
# Usage: ./scripts/run_tests.sh
set -euo pipefail
docker compose run --rm backend pytest -q
