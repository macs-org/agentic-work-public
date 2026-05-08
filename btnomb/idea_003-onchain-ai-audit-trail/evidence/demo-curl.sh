#!/usr/bin/env bash
set -euo pipefail
BASE_URL=${BASE_URL:-http://localhost:8000}

curl -s "$BASE_URL/health" | python3 -m json.tool
curl -s -X POST "$BASE_URL/api/actions"   -H 'content-type: application/json'   -d '{"agent_id":"agent-alpha","action_type":"tool_call","input_hash":"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824","output_hash":"486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65260e9cb8a7","timestamp":"2026-05-08T12:00:00Z","description":"Fetched public company filing and summarized the change."}' | python3 -m json.tool
curl -s -X POST "$BASE_URL/api/batches/commit" | python3 -m json.tool
curl -s -X POST "$BASE_URL/api/verify"   -H 'content-type: application/json'   -d '{"agent_id":"agent-alpha","action_type":"tool_call","input_hash":"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824","output_hash":"486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65260e9cb8a7","timestamp":"2026-05-08T12:00:00Z","description":"Fetched public company filing and summarized the change."}' | python3 -m json.tool
