# Profiler User Flow

This document explains the complete flow of the Profiler system: how a user (or API client) triggers a collection, how data moves through the pipeline, and how results are retrieved. It is written in plain English so that someone returning to the codebase months later can understand the flow without reading the source code.

---

## Table of Contents

1. [What is the Profiler?](#what-is-the-profiler)
2. [High-Level Architecture](#high-level-architecture)
3. [Data Storage Strategy](#data-storage-strategy)
4. [Complete User Flow (Step by Step)](#complete-user-flow-step-by-step)
5. [Worker Pipeline: How Jobs Chain Together](#worker-pipeline-how-jobs-chain-together)
6. [Scraper vs. HTTP Capture](#scraper-vs-http-capture)
7. [Docker and Playwright](#docker-and-playwright)
8. [API Reference Summary](#api-reference-summary)

---

## What is the Profiler?

The Profiler is a bounded context within the OSINT backend that:

1. **Captures** public web profiles (Facebook, Instagram, X/Twitter) via scraping or plain HTTP
2. **Parses** the content into structured JSON (identity, posts, comments, locations, interactions)
3. **Stores** evidence in Azure Blob Storage and metadata in MongoDB
4. **Normalizes** the data into canonical entities (profiles, posts, comments, etc.)
5. **Analyzes** the entities to produce artifacts (engagement, hashtags, locations, lifestyle, beliefs, etc.)
6. **Optionally runs inference** (AI tasks like summarization, face clustering) on the collected evidence

All of this runs asynchronously: the user triggers collection and receives a job ID immediately. A background worker processes the job. The user polls for job status and fetches results when ready.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER / API CLIENT                                    │
│                     (No UI yet – use API endpoints directly)                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTP requests (create case, add target, collect)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI ROUTER                                       │
│                         /profiler/cases, targets, jobs, etc.                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Creates jobs, enqueues job IDs
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              REDIS STREAM                                         │
│                    Queue of job IDs (public_capture, normalize, analyze)          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Worker claims jobs one at a time
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              PROFILER WORKER                                      │
│    Processes jobs: capture → normalize → analyze (each step enqueues the next)    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│   AZURE BLOB          │   │   MONGODB             │   │   EXTERNAL            │
│   Storage             │   │   (Beanie models)     │   │   Inference Client    │
│                       │   │                       │   │   (for AI tasks)      │
│ • Raw HTML            │   │ • Cases, targets      │   │                       │
│ • Extracted JSON      │   │ • Jobs, source docs   │   │                       │
│   (single source      │   │ • Entities            │   │                       │
│   of truth)           │   │ • Artifacts          │   │                       │
└───────────────────────┘   └───────────────────────┘   └───────────────────────┘
```

---

## Data Storage Strategy

Understanding where data lives is critical for debugging and extending the system.

### Azure Blob Storage (Single Source of Truth)

| What is stored | Format | When |
|----------------|--------|------|
| **Extracted JSON** (Facebook, Instagram, X) | `.json` | After scraper parses the page |
| **Raw HTML** (other sources) | `.html` | After plain HTTP GET |

Path pattern: `profiler/{org_id}/{case_id}/{target_id}/{job_id}/{timestamp}_{sha256}.json` or `.html`

The extracted JSON is the **single source of truth** for scraped profiles. It contains:

- **Provenance**: raw URL, capture timestamp, HTTP status, headers (sanitized), sha256, blob path, parser version
- **Identity**: handle, display name, bio, profile URL, profile image, followers/following (if visible), verified flag
- **Content**: posts (id, url, text, media, hashtags, mentions), comments
- **Interactions**: target → other account (reply, comment, mention, tag)
- **Locations**: place names, lat/lng if available, timestamps
- **Reviews**: (Google only; empty for FB/IG/X)

### MongoDB (Metadata and Derived Data)

| Collection | Purpose |
|------------|---------|
| `profiler_cases` | Investigation containers (name, description) |
| `profiler_targets` | What to collect (URL or username, canonical_url, detected_source) |
| `profiler_jobs` | Job queue state (queued, running, succeeded, failed, not_collectible) |
| `profiler_source_documents` | **Meta** for each capture: `blob_path`, `sha256`, `url`, `captured_at`, `fetch_method`, etc. Points to the JSON or HTML in Blob |
| `profiler_artifacts` | Derived outputs: profile_card, coverage, timeline, engagement, hashtags, locations, etc. |
| Entity collections | ProfileEntity, PostEntity, CommentEntity, LocationEntity, etc. (normalized from parsed data) |

**Key rule:** The `blob_path` in `profiler_source_documents` points to the stored file in Azure Blob. The JSON in Blob is authoritative; MongoDB holds references and indexes.

---

## Complete User Flow (Step by Step)

### Phase 1: Setup – Create a Case and Add a Target

**Step 1.1: Create a Case**

A case is a container for an investigation (e.g., "Background check: John Doe").

| API | `POST /profiler/cases` |
|-----|------------------------|
| Body | `{ "name": "Investigation X", "description": "...", "org_id": "optional" }` |
| Response | `{ "data": { "id": "<case_id>", ... } }` |

The case is stored in MongoDB. The user needs the `case_id` for all subsequent steps.

---

**Step 1.2: Add a Target to the Case**

A target is the person or page to profile: a URL or a username.

| API | `POST /profiler/cases/{case_id}/targets` |
|-----|-----------------------------------------|
| Body | `{ "target_type": "url" \| "username", "input_value": "https://facebook.com/johndoe" or "@johndoe" }` |
| Response | `{ "data": { "id": "<target_id>", "canonical_url": "...", "detected_source": "facebook" \| "instagram" \| "x" \| "unknown" } }` |

**What happens behind the scenes:**

- If `target_type` is `"url"`: the URL is normalized and the platform is detected from the hostname (facebook.com, instagram.com, x.com, twitter.com).
- If `target_type` is `"username"`: the connector (Facebook, Instagram, or X) converts the username to a canonical URL. The platform is inferred from hints in the input (e.g., "instagram" in the string) or defaults to X.

The target is stored with `canonical_url` and `detected_source`. These determine whether the worker uses a **scraper** (Playwright) or **plain HTTP** capture.

---

### Phase 2: Trigger Collection

**Step 2.1: Start Collection**

| API | `POST /profiler/cases/{case_id}/targets/{target_id}/collect` |
|-----|------------------------------------------------------------|
| Response | `{ "data": { "id": "<job_id>", "status": "queued", ... } }` |

**What happens:**

1. A new `ProfilerJob` is created in MongoDB with `job_type="public_capture"` and `status="queued"`.
2. The job ID is pushed to a Redis Stream.
3. The API returns immediately with the job ID. **The actual work has not started yet.**

The user must save the `job_id` to poll for status and to understand when results are ready.

---

### Phase 3: Worker Processes the Pipeline (Background)

A worker process runs in a loop. It:

1. Claims the next job from Redis
2. Loads the job from MongoDB
3. Executes the handler for `job_type` (public_capture, normalize, analyze, or inference)
4. On success for capture/normalize, **creates and enqueues the next job**
5. Acknowledges the message and loops back to step 1

The pipeline is **capture → normalize → analyze**. Each step is a **separate job**. The worker does not "remember" what to do next; it only processes whatever job comes off the queue. The next step runs because the previous step explicitly creates and enqueues a new job.

---

**Step 3.1: public_capture Job**

The worker runs `run_public_capture(job)`.

**For Facebook, Instagram, or X (scraper path):**

1. The worker selects the connector (`FacebookPublicConnector`, `InstagramPublicConnector`, or `XPublicConnector`) based on `target.detected_source`.
2. The connector calls `fetch_and_parse(canonical_url)`:
   - **Playwright** launches headless Chromium, navigates to the URL, waits for content.
   - The platform **parser** extracts structured data from the rendered HTML (og:meta, JSON-LD, DOM).
   - Returns an `ExtractedProfile`-shaped dict with identity, content, interactions, locations, provenance.
3. The worker computes SHA256 of the JSON, stores it in Azure Blob via `put_json_evidence`.
4. A `ProfilerSourceDocument` is created in MongoDB with `fetch_method="scrape"`, `content_type="application/json"`, `blob_path` pointing to the JSON.
5. `ProfilerService.write_artifacts` creates initial artifacts: `coverage`, `profile_card`, `timeline`.

**For other sources (HTTP path):**

1. `CollectorService` performs a plain HTTP GET.
2. Raw HTML is stored in Blob.
3. `ProfilerSourceDocument` is created with `fetch_method="http"`.

If the capture succeeds, the worker creates a **normalize** job and enqueues it to Redis. If it fails (login wall, 401/403), the job status is set to `not_collectible` and the pipeline stops.

---

**Step 3.2: normalize Job**

The worker runs `run_normalize(job)`.

**For scrape documents (JSON in Blob):**

1. Load the JSON from Blob via `evidence_store.get_json(blob_path)`.
2. Map the ExtractedProfile structure directly to entities: ProfileEntity, PostEntity, CommentEntity, LocationEntity, InteractionEntity, ReviewEntity, TagEntity.

**For HTTP documents (HTML in Blob):**

1. Load the HTML from Blob.
2. Detect source from URL hostname.
3. Run the platform parser (FacebookParser, InstagramParser, XParser, GoogleParser) to produce `ParseResult`.
4. Map `ParseResult` to the same entity types.

Entities are stored in MongoDB. They feed the **analyze** step.

On success, the worker creates an **analyze** job and enqueues it.

---

**Step 3.3: analyze Job**

The worker runs `run_analyze(job)`.

All analyzers run in sequence:

| Analyzer | What it does | Artifact type |
|----------|--------------|---------------|
| EngagementAnalyzer | Aggregates engagement metrics from posts | engagement |
| HashtagsAnalyzer | Extracts and ranks hashtags | hashtags |
| LocationsAnalyzer | Summarizes locations | locations |
| ActivityAnalyzer | Activity patterns over time | activity |
| CommentsAnalyzer | Comment volume and patterns | comments_summary |
| PhotosAnalyzer | Media analysis | photos_summary |
| LifestyleAnalyzer | Reviews, categories, ratings | lifestyle |
| BeliefsAnalyzer | Topics, exposure, beliefs | beliefs |

Each analyzer reads entities (and optionally calls the inference client), produces a `ProfilerArtifact`, and saves it to MongoDB.

The analyze step is the **end of the automatic pipeline**. No further jobs are enqueued automatically.

---

### Phase 4: User Retrieves Results

**Step 4.1: Poll Job Status**

| API | `GET /profiler/jobs/{job_id}` |
|-----|------------------------------|
| Response | `{ "data": { "status": "queued" \| "running" \| "succeeded" \| "failed" \| "not_collectible", "metrics": {...}, "error": {...} } }` |

The user polls until `status` is `succeeded`, `failed`, or `not_collectible`.

**Important:** The job returned is the **public_capture** job. The normalize and analyze jobs are separate jobs created by the worker. For a full pipeline run, the capture job succeeds quickly; normalize and analyze run as subsequent jobs. The artifacts are linked to the **target**, not to a specific job, so the user fetches artifacts by case and target.

---

**Step 4.2: Fetch Artifacts (Results)**

| API | `GET /profiler/cases/{case_id}/targets/{target_id}/artifacts` |
|-----|--------------------------------------------------------------|
| Response | `{ "data": [ { "id": "...", "artifact_type": "profile_card", "payload": {...}, ... }, ... ] }` |

Artifact types include:

- `profile_card` – Canonical URL, handle, display name, followers (if scraped), capture time
- `coverage` – Whether the target was collectible
- `timeline` – Capture events (URL, timestamp, sha256)
- `engagement`, `hashtags`, `locations`, `activity`, `comments_summary`, `photos_summary`, `lifestyle`, `beliefs` – Analysis outputs
- `inference_result` – Results from optional AI inference jobs

---

### Phase 5: Optional Inference (AI Tasks)

**Step 5.1: Run Inference**

| API | `POST /profiler/cases/{case_id}/targets/{target_id}/infer` |
|-----|-----------------------------------------------------------|
| Body | `InferenceRequest` with `task_type`, `inputs` (e.g., ref to source document), `context` |
| Response | `{ "data": { "id": "<job_id>", "status": "queued", ... } }` |

This creates an **inference** job. The worker runs it separately from the capture pipeline. When complete, an `inference_result` artifact is stored. The user fetches it via the same artifacts endpoint.

---

## Worker Pipeline: How Jobs Chain Together

A common question: *"After public_capture succeeds, how does the worker know to run normalize?"*

**Answer:** It does not "know." Each step is a **different job**. When public_capture succeeds, the worker **creates a new job** of type `normalize` and **pushes it to Redis**. The next time the worker (or another worker) claims a job from the queue, it may receive that normalize job.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORKER MAIN LOOP                                      │
│                                                                               │
│   while True:                                                                 │
│       msg_id, job_id = claim_next(Redis)    ◄── Get next job from queue      │
│       job = ProfilerJob.get(job_id)                                            │
│                                                                               │
│       if job_type == "public_capture":                                        │
│           run_public_capture(job)                                             │
│           if succeeded:                                                       │
│               create Job B (normalize)  ──────►  enqueue Job B to Redis       │
│                                                                               │
│       elif job_type == "normalize":                                           │
│           run_normalize(job)                                                  │
│           if succeeded:                                                       │
│               create Job C (analyze)   ──────►  enqueue Job C to Redis       │
│                                                                               │
│       elif job_type == "analyze":                                             │
│           run_analyze(job)           (no next job – pipeline ends)            │
│                                                                               │
│       ack(msg_id)                                                             │
│       (loop again – claim next job)                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Timeline:**

| Time | Event |
|------|-------|
| T0 | API creates Job A (public_capture), enqueues to Redis |
| T1 | Worker claims Job A, runs public_capture, succeeds, creates Job B (normalize), enqueues B, acks A |
| T2 | Worker claims Job B, runs normalize, succeeds, creates Job C (analyze), enqueues C, acks B |
| T3 | Worker claims Job C, runs analyze, acks C |
| T4 | No more pipeline jobs; worker waits for next message |

Multiple workers can run in parallel. Redis Streams with consumer groups distribute jobs across workers. Each job is processed by exactly one worker.

---

## Scraper vs. HTTP Capture

| Aspect | Scraper (FB, IG, X) | HTTP (other sources) |
|--------|----------------------|-----------------------|
| Technology | Playwright (headless Chromium) | Plain HTTP GET (httpx) |
| Output | Extracted JSON | Raw HTML |
| Blob format | `.json` | `.html` |
| fetch_method | `"scrape"` | `"http"` |
| Parser | Platform parser (FacebookParser, etc.) in connector | Parser runs later in NormalizerService |
| Login wall | Detected → `not_collectible` | Detected → `not_collectible` |

The worker chooses the path based on `target.detected_source`:

```
if detected_source in ("facebook", "instagram", "x"):
    → use connector.fetch_and_parse()  (Playwright + parser)
else:
    → use CollectorService.collect()   (plain HTTP)
```

---

## Docker and Playwright

Playwright requires two parts:

1. **Python package** (`pip install playwright`) – the control layer (API, protocol)
2. **Browser binaries** – the actual Chromium browser

The Python package does **not** include the browser. You must run:

```bash
playwright install chromium
```

This downloads Chromium and installs it (typically under `~/.cache/ms-playwright/`).

**In Docker**, the image is minimal. Base images do not include Chromium. So you must add to your Dockerfile:

```dockerfile
RUN pip install playwright
RUN playwright install chromium
RUN playwright install-deps   # Linux system libraries (fonts, etc.)
```

Without these steps, `PlaywrightScraperClient.fetch_html()` will fail with "Executable doesn't exist."

---

## API Reference Summary

| Purpose | Method | Endpoint |
|---------|--------|----------|
| Create case | POST | `/profiler/cases` |
| List cases | GET | `/profiler/cases` |
| Get case | GET | `/profiler/cases/{case_id}` |
| Add target | POST | `/profiler/cases/{case_id}/targets` |
| List targets | GET | `/profiler/cases/{case_id}/targets` |
| Trigger collection | POST | `/profiler/cases/{case_id}/targets/{target_id}/collect` |
| Get job status | GET | `/profiler/jobs/{job_id}` |
| Get artifacts (results) | GET | `/profiler/cases/{case_id}/targets/{target_id}/artifacts` |
| Run inference | POST | `/profiler/cases/{case_id}/targets/{target_id}/infer` |

All endpoints require authentication (Bearer token) and the `PROFILER` feature for the user.

---

## Quick Reference: What Gets Stored Where

| Data | Storage |
|------|---------|
| Extracted profile JSON (FB, IG, X) | Azure Blob |
| Raw HTML (other sources) | Azure Blob |
| Case, target, job records | MongoDB |
| Source document metadata (blob_path, sha256, url) | MongoDB |
| Normalized entities (profiles, posts, comments, etc.) | MongoDB |
| Artifacts (profile_card, engagement, hashtags, etc.) | MongoDB |

---

*Document last updated: February 2025. For implementation details, see the source code in `app/profiler/`.*
