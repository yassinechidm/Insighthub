#!/usr/bin/env bash
# Test manuel de bout en bout de la source ServiceNow, une fois
# l'application démarrée (docker-compose up, ou uvicorn en local) et
# SERVICENOW_* configuré dans .env avec de vraies infos d'instance.
#
# Usage :
#   chmod +x scripts/test_servicenow_e2e.sh
#   ./scripts/test_servicenow_e2e.sh [BASE_URL]
#
# BASE_URL par défaut : http://localhost:8000

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

echo "== 1) Healthcheck =="
curl -sf "${BASE_URL}/health" | tee /dev/stderr
echo

echo "== 2) Sync ServiceNow (table par défaut = incident, full sync) =="
curl -sf -X POST "${BASE_URL}/ingestion/servicenow/sync" \
  -H "Content-Type: application/json" \
  -d '{}' | tee /dev/stderr
echo

echo "== 3) Sync incrémental (uniquement les tickets modifiés après une date) =="
curl -sf -X POST "${BASE_URL}/ingestion/servicenow/sync" \
  -H "Content-Type: application/json" \
  -d '{"updated_after": "2026-01-01 00:00:00"}' | tee /dev/stderr
echo

echo "== 4) Recherche sémantique restreinte à la source servicenow =="
curl -sf -X POST "${BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
        "question": "Quels sont les incidents liés au VPN ?",
        "source": "servicenow",
        "top_k": 5,
        "generate": true
      }' | tee /dev/stderr
echo

echo "== Terminé =="
