# Profiler Bounded Context

Public-web capture, evidence store, and ML inference plug-in for OSINT.

**Documentation:** See [PROFILER_USER_FLOW.md](./PROFILER_USER_FLOW.md) for a full explanation of the user flow, data storage, worker pipeline, and API usage.

## Prerequisites

- MongoDB (existing)
- Redis
- Azure Blob Storage (or Azurite for local dev)

## Quick Start

### 1. Start Redis (and optionally Azurite)

```bash
# Redis only
docker compose -f docker-compose.profiler-dev.yml up -d redis

# Redis + Azurite (for local Blob)
docker compose -f docker-compose.profiler-dev.yml --profile azurite up -d
```

**Blob credentials** – use either:
- `AZURE_BLOB_CONNECTION_STRING` (connection string)
- or existing vars: `AZURE_STORAGE_ACCOUNT_NAME` + `AZURE_STORAGE_ACCOUNT_KEY` (with optional `AZURE_STORAGE_CONTAINER_NAME`, default: `uploads`)

For Azurite local dev:
```
AZURE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;
```

### 2. Start API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Start Worker

**Option A: Local (requires `playwright install chromium` in venv)**

```bash
python -m app.profiler.workers.run_profiler_worker
```

**Option B: Docker (Chromium included in image)**

```bash
docker compose -f docker-compose.profiler-dev.yml up -d redis profiler-worker
```

The profiler-worker image includes Playwright Chromium for scraping Facebook, Instagram, and X.

### 4. Example curl flows

**Create case (requires auth token)**

```bash
TOKEN="<your-jwt>"
BASE="http://localhost:8000/api"

# Create case
curl -X POST "$BASE/profiler/cases" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Case", "description": "Profiler demo"}'

# List cases
curl -s "$BASE/profiler/cases" -H "Authorization: Bearer $TOKEN"

# Add target (replace {case_id} with ID from create)
curl -X POST "$BASE/profiler/cases/{case_id}/targets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_type": "url", "input_value": "https://example.com"}'

# Enqueue collect (replace case_id, target_id)
curl -X POST "$BASE/profiler/cases/{case_id}/targets/{target_id}/collect" \
  -H "Authorization: Bearer $TOKEN"

# Check job status
curl -s "$BASE/profiler/jobs/{job_id}" -H "Authorization: Bearer $TOKEN"

# List artifacts
curl -s "$BASE/profiler/cases/{case_id}/targets/{target_id}/artifacts" \
  -H "Authorization: Bearer $TOKEN"

# Enqueue inference
curl -X POST "$BASE/profiler/cases/{case_id}/targets/{target_id}/infer" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "text_summary",
    "inputs": [{"ref_type": "source_document_id", "ref": "<doc_id>"}],
    "context": {"org_id": "", "case_id": "", "target_id": "", "job_id": ""}
  }'
```

**Note:** Add `PROFILER` to user's `features` array in MongoDB for feature gating, or use an admin/org_admin user (they bypass feature check).

## Architecture

- **Beanie models**: `profiler_cases`, `profiler_targets`, `profiler_jobs`, `profiler_source_documents`, `profiler_artifacts`
- **Redis Stream**: `profiler_jobs` with consumer group `profiler_workers`
- **Blob path**: `profiler/{org_id}/{case_id}/{target_id}/{job_id}/{timestamp}_{sha256}.html`

## Security

- Public-web capture only: no login, credentials, or cookie import
- Content requiring sign-in/interstitial/age wall → `NOT_COLLECTIBLE`
- No evasion, stealth, or anti-bot circumvention
