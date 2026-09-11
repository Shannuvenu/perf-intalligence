# Perf Intelligence

An internal developer tool that turns noisy PageSpeed Insights / Lighthouse
results for **Deccan Herald** and **Prajavani** into a stable,
evidence-backed, prioritized, root-cause-grouped fix list — not another
generic PageSpeed dashboard.

Runs fully offline with mock PSI + mock LLM providers. No Google API key,
no OpenAI key, no AWS account required to see the whole thing working.

---

## 1. What this is

Every PSI/Lighthouse run is noisy — the same URL can score differently
minute to minute. Screenshotting a single run and handing it to an LLM
produces confident-sounding but unreliable advice. Perf Intelligence instead:

1. Runs PSI multiple times per URL and takes the **median** across a
   rolling window (never a single run).
2. Extracts **deterministic evidence** from that stabilized data — actual
   thresholds, actual numbers — before any AI is involved.
3. Groups evidence into **candidate root causes** with a rule engine.
4. Only then asks an LLM to **synthesize** those candidates into a ranked,
   worded fix list — constrained to cite only the evidence it was given.
5. Validates the LLM's output against a strict schema and marks it
   `valid` / `needs_review` / `invalid` — the app never assumes AI output is
   automatically correct.
6. Assigns priority (P0–P3) via a transparent, documented formula — never a
   number the LLM invents.

## 2. Architecture

```
URL configuration
      |
      v
Scheduled/manual PSI execution  (APScheduler / POST .../run)
      |
      v
PageSpeed Insights API  (mock provider OR real Google API)
      |
      v
Raw PSI JSON  --------------------------> storage/raw/{site}/{date}/*.json
      |
      v
Normalization  (app/services/psi/normalizer.py)
      |
      v
Multi-run stabilization  (median + variability, app/services/stabilization)
      |
      v
Evidence extraction  (threshold-based, app/services/evidence)
      |
      v
Rule-based candidate signals  (app/services/recommendations/candidate_signals.py)
      |
      v
LLM synthesis  (mock or OpenAI, app/services/llm)
      |
      v
Pydantic validation + priority engine  (app/services/recommendations)
      |
      v
Developer recommendations  --> REST API --> Next.js dashboard + trend charts
```

```
perf-intelligence/
├── backend/            FastAPI + SQLAlchemy + Alembic + pytest
│   ├── app/
│   │   ├── api/            REST route handlers (thin - no business logic)
│   │   ├── core/            config.py - every threshold is env-configurable
│   │   ├── db/               engine/session + portable JSON column type
│   │   ├── models/          sites, urls, psi_runs, stabilized_metrics, llm_recommendations
│   │   ├── schemas/         Pydantic request/response + the recommendation validation contract
│   │   ├── services/
│   │   │   ├── psi/          provider interface, mock + real providers, normalizer, ingestion
│   │   │   ├── stabilization/  median + variability
│   │   │   ├── evidence/       deterministic threshold-based extraction
│   │   │   ├── recommendations/  rule engine, priority engine, orchestration
│   │   │   ├── llm/           mock + OpenAI synthesis providers, prompts
│   │   │   ├── storage.py      raw PSI storage abstraction (local now, S3-ready)
│   │   │   └── trends.py
│   │   ├── scheduler/       APScheduler wiring
│   │   ├── seed_demo.py    python -m app.seed_demo
│   │   └── main.py
│   ├── alembic/             hand-written initial migration (see §14)
│   └── tests/                37 pytest tests, see §18
├── frontend/            Next.js 14 (App Router) + TypeScript + Tailwind + Recharts
├── storage/raw/          raw PSI JSON lands here in STORAGE_MODE=local
├── scripts/               seed_demo.sh, run_tests.sh convenience wrappers
├── docker-compose.yml
└── .env.example
```

## 3. Requirements

- Docker + Docker Compose (recommended path)
- OR, to run without Docker: Python 3.12, Node.js 20, and a local PostgreSQL
  16 instance

## 4. Installation

```bash
git clone <this repo>        # or unzip perf-intelligence-mvp.zip
cd perf-intelligence
cp .env.example .env
```

The defaults in `.env.example` (`PSI_PROVIDER=mock`, `LLM_PROVIDER=mock`)
are what make the whole app demoable with zero external keys — leave them
as-is for now.

## 5. Docker setup

```bash
docker compose up --build
```

This builds and starts three services: `postgres`, `backend` (runs Alembic
migrations automatically on boot, then serves the API on :8000), and
`frontend` (serves the dashboard on :3000).

> **Honesty note on this step:** this Compose file was written to the spec
> and reviewed carefully, but it was **not executed** in the environment
> that built this project — that sandbox has no Docker daemon and no
> network access to Docker Hub, so `docker compose up` itself could not be
> run there. Everything it depends on WAS independently verified in that
> sandbox: the backend's full test suite (37/37 passing) against a real
> database schema, a live `uvicorn` server hit with real HTTP requests, the
> `seed_demo` script run end-to-end, and the Next.js production build
> (`npm run build`, `output: "standalone"`) serving real pages against that
> live backend. If `docker compose up --build` surfaces anything on your
> machine, it's most likely a Docker/networking environment quirk rather
than application logic — see Troubleshooting (§19).

## 6. Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://perf:perf@localhost:5432/perf_intelligence` | Overridden inside Docker Compose to point at the `postgres` service. |
| `PSI_PROVIDER` | `mock` | `mock` = realistic demo data, no key needed. `real` = calls Google PSI. |
| `PSI_API_KEY` | *(empty)* | Required only when `PSI_PROVIDER=real`. |
| `PSI_STRATEGY` | `mobile` | `mobile` or `desktop`. |
| `LLM_PROVIDER` | `mock` | `mock` = deterministic sample recommendations, no key needed. `openai` = calls OpenAI. |
| `OPENAI_API_KEY` | *(empty)* | Required only when `LLM_PROVIDER=openai`. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any OpenAI chat-completions model that supports JSON mode. |
| `STORAGE_MODE` | `local` | Only `local` is implemented in the MVP; see §5 in-code docstring (`app/services/storage.py`) for how to add S3. |
| `RUN_INTERVAL_HOURS` | `6` | How often the scheduler re-runs PSI for all enabled URLs. |
| `AUTO_LLM_ANALYSIS` | `false` | If `true`, the scheduler also generates recommendations automatically (costs OpenAI credits in `real`/`openai` mode - default is off on purpose). |
| `SCHEDULER_ENABLED` | `true` | Set `false` to disable the background scheduler entirely (tests already do this). |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | The URL your **browser** uses to reach the backend. Baked into the frontend at build time - see §16 if you change it. |

Every stabilization/evidence threshold (LCP/CLS/TBT/FCP good & poor
values, variability flag %, priority weights, etc.) is also configurable in
`backend/app/core/config.py` / as env vars — nothing is hard-coded.

## 7. How to start

```bash
docker compose up --build
```

Wait for the log lines `Application startup complete` (backend) and
`✓ Ready` (frontend), then continue to §8.

## 8. How to seed demo data

```bash
docker compose exec backend python -m app.seed_demo
# or: ./scripts/seed_demo.sh
```

This creates both sites (Deccan Herald, Prajavani), two URLs each
(homepage + article), runs mock PSI 6 times per URL, stabilizes, and
generates recommendations — fully verified end-to-end in the build
environment (see §18).

## 9. How to access the frontend

Open **http://localhost:3000**.

## 10. How to access the backend

API root: **http://localhost:8000** · Interactive OpenAPI docs:
**http://localhost:8000/docs** · Health check: **http://localhost:8000/health**

## 11. How to use the application

1. **Overview** (`/`) — lists your sites.
2. **Sites** (`/sites`) — add a site, or drill into one to see its URLs.
3. Click a URL to reach its **detail page**: stabilized metrics, scores,
   and the **Top Recommended Fixes** list (root cause → evidence →
   suggested fix, expandable, color-coded by P0–P3 priority).
4. **Run PageSpeed** / **Stabilize** / **Analyze** buttons on that page run
   the pipeline manually, without freezing the UI (async, with
   Running/Completed/Failed states).
5. **Trends** (per-URL, or via the sidebar) — charts of Performance,
   Accessibility, LCP, CLS, TBT, FCP with an Improving/Stable/Regressing
   label per metric.
6. **Runs** / **Recommendations** (sidebar) — cross-URL snapshot views.

## 12. How to add a new URL

Sites → click a site → **Add URL** → paste the URL, pick a category
(homepage / article / category / other).

## 13. How to run a manual PSI test

Open the URL's detail page → **Run PageSpeed**. In `PSI_PROVIDER=mock`
mode this returns realistic demo data instantly; in `real` mode it calls
the actual Google API (typically a few seconds).

## 14. How stabilization works

`app/services/stabilization/service.py` takes the most recent
`STABILIZATION_WINDOW_RUNS` (default 5) **successful** runs for a URL,
computes the **median** for LCP/CLS/TBT/FCP/Speed Index/scores, and flags
the window `flagged=true` if any metric's relative standard deviation
exceeds `VARIABILITY_FLAG_RELATIVE_STDEV` (default 20%). A minimum of
`STABILIZATION_MIN_RUNS` (default 3) is enforced — stabilizing too early
raises a `422` from the API rather than silently returning noisy numbers.

Worked example (from the spec, and asserted in
`tests/test_stabilization.py::test_median_lcp_matches_spec_example`):
LCP runs `3.2, 4.1, 2.9, 3.7, 3.4` → median **3.4s**, not whatever the
latest run happened to say.

## 15. How recommendations work

See the architecture diagram in §2. Concretely:
`app/services/recommendations/service.py::generate_recommendations()`
pulls the latest stabilized window → extracts evidence
(`app/services/evidence/extractor.py`) → generates candidate root-cause
signals (`app/services/recommendations/candidate_signals.py`) → calls the
LLM provider with **only** that evidence and those candidates → validates
the structured response against `RecommendationItem`/`LlmRecommendationSet`
(Pydantic, `app/schemas/recommendation.py`) → computes `validation_status`
ourselves (never trusts the model's self-assessment) → assigns priority via
`app/services/recommendations/priority.py` → persists everything, including
`source_run_ids` so every recommendation traces back to the exact runs that
justified it.

## 16. How to enable real PSI

1. Get a PageSpeed Insights API key from Google Cloud Console.
2. In `.env`: `PSI_PROVIDER=real` and `PSI_API_KEY=<your key>`.
3. `docker compose up --build backend` (or restart the backend service).

The real provider (`app/services/psi/real_provider.py`) handles timeouts,
HTTP errors, PSI API errors, rate limiting (429), and malformed responses -
failures are stored as a `run_status="failed"` row with `error_message`
rather than crashing the request.

## 17. How to enable OpenAI

1. In `.env`: `LLM_PROVIDER=openai`, `OPENAI_API_KEY=<your key>`, and
   optionally `OPENAI_MODEL` (default `gpt-4o-mini`).
2. Rebuild/restart the backend.

The real provider uses JSON-mode chat completions and validates the
response against the same Pydantic schema the mock provider satisfies — an
unparseable or schema-invalid response is caught and stored as
`validation_status="invalid"` rather than shown to a developer as fact.

⚠️ Real PSI + real OpenAI were **not** exercised in the build environment
(no external network access, no API keys available there). The request/
response handling was written defensively and code-reviewed, but you are
the first to actually run it against the live APIs — please treat the
first few runs as a smoke test.

## 18. How to run tests

```bash
docker compose run --rm backend pytest -q
# or: ./scripts/run_tests.sh
```

**This was genuinely run, not just written**, in the sandbox that built
this project (against a local venv + SQLite instead of the Docker Postgres
service — see `tests/conftest.py`'s docstring for why that's safe: a
portable `PortableJSON` SQLAlchemy type gives real `JSONB` on Postgres and
falls back to plain `JSON` on SQLite without the model definitions
diverging). Result at the time of writing: **37 passed, 0 failed.**

Coverage includes: PSI response parsing (valid + malformed), the exact
median example from the product spec, variability flagging (both
triggered and not), evidence extraction thresholds, majority-vote
accessibility evidence, Pydantic schema validation (including rejecting
empty-evidence recommendations), the priority engine's score→rank
boundaries, a simulated broken LLM provider (`invalid` status is produced,
not a crash), the `/health` endpoint, and a full API integration test that
walks the entire pipeline (create site → add URL → 5 PSI runs → stabilize
→ analyze → trends) end-to-end — which is effectively what `seed_demo`
does, exercised through pytest.

## 19. Troubleshooting

- **`docker compose up` fails to pull images** — you need outbound access
  to Docker Hub; check a corporate proxy/firewall isn't blocking it.
- **Frontend loads but shows no data / network errors in the browser
  console** — check `NEXT_PUBLIC_API_BASE_URL` in `.env` matches how you
  actually reach the backend (default assumes `localhost:8000`); rebuild
  the frontend after changing it (`docker compose up --build frontend`) -
  this variable is baked in at build time, not read at container start.
- **Backend can't reach Postgres** — the `backend` service waits on
  Postgres's healthcheck, but if you're running services individually,
  make sure Postgres is actually accepting connections first.
- **"Insufficient runs" (422) when stabilizing** — you need at least
  `STABILIZATION_MIN_RUNS` (default 3) successful runs first; click
  **Run PageSpeed** a few more times.
- **"No stabilized metrics yet" (422) when analyzing** — stabilize before
  you analyze; the pipeline is intentionally sequential (§2).
- **Port already in use** — `postgres` is mapped to host port `5433`
  (not 5432) specifically to avoid clashing with a local Postgres
  install; `backend`/`frontend` use `8000`/`3000` — free those or edit
  `docker-compose.yml`.

## 20. Production considerations

This is an MVP, not a hardened production deployment. Before running this
for real, at minimum:

- **Don't auto-run migrations on every container boot** (`alembic upgrade
  head` in the Docker `CMD`) in production — run migrations as a separate,
  deliberate deploy step.
- **Rotate/secure `PSI_API_KEY` and `OPENAI_API_KEY`** via a real secrets
  manager, not a `.env` file.
- **Add authentication** to the API and dashboard — there is none in the
  MVP; anyone who can reach port 8000/3000 can read and trigger runs.
- **Rate-limit** `POST /api/urls/{id}/run` and `/analyze` — nothing stops
  someone from hammering the PSI/OpenAI APIs (and your bill) via the API.
- **Move raw PSI storage to S3** (or similar) once you're running this
  against more than a couple of sites — see the docstring in
  `app/services/storage.py` for the exact extension point.
- **Add structured logging/monitoring** for the scheduler and LLM calls -
  right now failures are logged locally and visible per-run in the API,
  but there's no alerting.
- **Postgres backups** — the Compose file's `pgdata` volume is durable
  across restarts but is not a backup strategy.

## 21. Known limitations (read this before you demo it)

- Real PSI and real OpenAI code paths are written and schema-validated but
  **not exercised against the live APIs** in this build (no network/keys
  in the build sandbox) - see §16/§17.
- `docker compose up --build` was **not run** in the build environment (no
  Docker daemon there) - see §5's honesty note. Backend, frontend, and
  their integration were verified independently outside Docker instead.
- The Alembic initial migration was **hand-written** to mirror the
  SQLAlchemy models exactly (rather than autogenerated against a live
  Postgres, which wasn't available in the build sandbox). It's
  straightforward SQL/Alembic and was reviewed carefully, but if you add
  new models later, generate the *next* migration the normal way
  (`alembic revision --autogenerate`) against a real running Postgres.
- Evidence extraction and the rule-based candidate engine cover the
  patterns the spec calls out explicitly (third-party/ads, images, layout
  shift, render-blocking, unused JS, common accessibility audits) - real
  Lighthouse reports surface more audit types than this MVP models; extend
  `app/services/evidence/extractor.py` and
  `app/services/recommendations/candidate_signals.py` as needed.
- Trend direction (`improving`/`stable`/`regressing`) is a simple two-halves
  mean comparison (§16 in the spec explicitly asked to not overcomplicate
  this) - it's meant to be eyeballed on a chart, not a statistically
  rigorous forecast.
- No authentication/authorization anywhere (see Production Considerations).

## 22. Recommended next development phase

1. Run real PSI + real OpenAI against a couple of live Deccan
   Herald/Prajavani URLs and sanity-check the recommendations a developer
   actually gets.
2. Add auth (even basic HTTP auth in front of the whole app would be a big
   step up from "nothing").
3. Expand the evidence/rule-engine coverage based on what real Lighthouse
   reports for these two sites actually surface most often.
4. Add S3 raw storage once you're past a handful of sites (extension point
   already scaffolded in `app/services/storage.py`).
5. Wire the scheduler's `AUTO_LLM_ANALYSIS` to a Slack/email digest so
   developers see new P0/P1 findings without opening the dashboard.
