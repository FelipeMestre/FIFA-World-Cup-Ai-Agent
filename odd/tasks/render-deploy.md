# Feature: Render deployment config (Blueprint + production Dockerfiles)

## Objective
Prepare the repo to deploy to Render with minimal ops: a `render.yaml` Blueprint
plus production-grade Dockerfiles, WITHOUT breaking the existing local
docker-compose dev workflow. Config only — nothing is deployed or pushed.

## Why
User chose Render (lowest ops effort). Current Dockerfiles are dev images
(`uvicorn --reload`, `npm run dev`, bind-mounted source). Render needs production
start commands, managed Postgres/Key Value wiring, migrations on deploy, and real
hostnames instead of localhost.

## Target topology (Render service types)
- `backend`: Web Service, Docker runtime (`backend/`), FastAPI on `$PORT`
- `worker`: Background Worker, same backend image, `arq src.infra.task_queue.worker.WorkerSettings`
- `frontend`: Web Service, Docker runtime (`frontend/`), `next build` + `next start`
- Postgres: managed database
- Redis: Render Key Value (type `keyvalue`), used by backend + worker
- Migrations: `alembic upgrade head` as backend's pre-deploy command

## Scope
- Root `render.yaml` Blueprint (services, database, Key Value, env var wiring via
  `fromDatabase`/`fromService`, secrets as `sync: false`, region/plan sensible cheap defaults).
- Production Dockerfiles WITHOUT clobbering dev: keep existing dev Dockerfiles
  working for docker-compose (e.g. `Dockerfile` stays dev; add `Dockerfile.prod`,
  or multi-stage with a `prod` target — choose whichever keeps docker-compose.yml
  unchanged and working). Prod images: non-root user, no `--reload`, no dev deps,
  frontend multi-stage build (deps -> build -> runner), `.dockerignore` checked.
- Handle known gotchas (verify each against real code, don't assume):
  1. Render's Postgres connection string is `postgresql://…`; backend needs
     `postgresql+asyncpg://…`. Find how `PostgresConfig.DATABASE_URL` is consumed and
     solve this cleanly (e.g. normalize the scheme in config code, or build the URL in
     the start command) — prefer a small, tested code-level normalization over shell hacks.
  2. Backend must bind `$PORT` (Render sets it) — check how uvicorn is started.
  3. `CORS_ORIGINS`, `OPENROUTER_APP_URL`, and the frontend's `BACKEND_API_URL` need
     real deployed URLs; use Blueprint `fromService` host/URL references where possible,
     document any value the user must set manually.
  4. docker-compose.yml passes `CHAT_WS_PUBLIC_URL` to the frontend — determine whether the
     frontend still uses it (chat moved WebSocket -> SSE per project history) and whether
     browsers ever talk to the backend directly (vs only via Next.js Route Handlers);
     this decides whether the backend needs a public URL in CORS/frontend env. Report findings.
  5. Cookies: check `frontend/src/lib/auth/session.ts` for `secure`/sameSite behavior in
     production (NODE_ENV=production) — confirm login works over HTTPS behind Render's proxy.
  6. Backend/worker share code+env: worker needs the same secrets (`JWT_SECRET`,
     `OPENROUTER_API_KEY`, `DATABASE_URL`, `REDIS_URL`) — use an env group if cleaner.
  7. Next.js 16 (`cacheComponents: true`): read `frontend/node_modules/next/dist/docs/` for
     the current standalone/`output` guidance BEFORE choosing the prod build approach;
     do not assume Next 13-15 conventions. Only change `next.config.ts` if truly needed.
  8. Ingestion `data/` dir is bind-mounted in dev only; confirm prod never needs it
     (seed script is dev-only; admin ingestion goes through the API).
- A short `docs/deploy-render.md` (or README section): manual steps (create Blueprint from
  repo, set secrets, first admin user creation, custom domain) — concise.

## Out of scope
- Actually deploying, pushing, or opening a PR (user's call).
- Changing app behavior beyond the minimal config normalization in gotcha 1.
- Vercel frontend variant (mention as an alternative in docs only).

## Constraints
- `backend/AGENTS.md` conventions (400-line cap, layer-first, type safety); TDD mode is on
  for any real code change (the DATABASE_URL normalization gets a RED->GREEN unit test).
- Never break `docker compose up` local workflow: verify with `docker compose config`
  (static validation only).
- HAZARD (real, previously caused an incident): the running docker-compose containers may be
  bind-mounted to a DIFFERENT git worktree. Do NOT `docker exec`/`docker cp` into
  `world-cup-ai-scout-*` containers. Building prod images locally with `docker build`
  (no compose containers touched) is fine. Run pytest via local `backend/venv`
  (export DATABASE_URL/REDIS_URL/JWT_SECRET/OPENROUTER_API_KEY as shell vars).
- Validate `render.yaml` if a validator is available (e.g. `render blueprints validate`
  via Render CLI) — if not installed, say so plainly; do not install global tooling without need.

## Tasks
- [x] T1: Investigate gotchas 1-8, record findings
- [x] T2: DATABASE_URL scheme normalization (TDD) if needed
- [x] T3: Backend production Dockerfile
- [x] T4: Frontend production Dockerfile (+ next.config change only if required)
- [x] T5: `render.yaml` Blueprint
- [x] T6: Deploy doc
- [x] T7: Verification (docker compose config, local `docker build` of both prod images, ruff/pytest for T2, frontend tests untouched)

## Verification
- `docker compose config` still valid; dev Dockerfiles untouched in behavior
- `docker build` both prod images succeed locally; backend prod image boots and answers `/health` when given env (run a throwaway container on a free port with env vars, then remove it — this is NOT one of the shared compose containers)
- ruff + relevant pytest via local venv

## Delivery
- Branch `feat/render-deploy` (already created off main)
- Conventional Commits, local only — do NOT push or open a PR

## Progress
All tasks done; route: inline (single writer session). TDD: enabled (pytest, backend/venv).

### Findings (gotchas)
1. `PostgresConfig.DATABASE_URL` feeds the engine and Alembic env.py (via `postgres_settings`). Fixed with a `field_validator` normalizing `postgres://`/`postgresql://` -> `postgresql+asyncpg://` (RED test then GREEN; verified end-to-end with `alembic upgrade head` against a throwaway postgres using a plain `postgresql://` URL).
2. Dev image hard-coded port 8000; prod CMD uses `${PORT:-8000}`; backend pinned `PORT=8000` in render.yaml.
3. Browser never calls the backend (only Next Route Handlers), so CORS is irrelevant; `BACKEND_API_URL=http://backend:8000/api/v1` (private network, literal, relies on service name `backend`). `OPENROUTER_APP_URL` is `sync: false` (only an HTTP-Referer header).
4. `CHAT_WS_PUBLIC_URL` is read by nothing in frontend/src (SSE migration); compose still passes it (left untouched). Backend needs no public URL for the frontend.
5. session.ts: `secure: NODE_ENV==="production"`, `sameSite: "lax"`, httpOnly; image sets NODE_ENV=production; Render terminates TLS so the browser sees HTTPS. OK. Not exercised against a real Render deploy.
6. Env group `scout-backend-shared` (JWT_SECRET generateValue, JWT_ALG, JWT_EXP_MINUTES, ENVIRONMENT) shared by backend+worker; DATABASE_URL/REDIS_URL via fromDatabase/fromService in each; OPENROUTER_API_KEY sync:false in each (groups cannot hold sync:false).
7. Read Next docs (output.md/self-hosting.md): standalone is optional. Chose `next start` with `npm ci --omit=dev` runner, so next.config.ts unchanged. Verified: image runs, /login 200.
8. `data/` is git-ignored and not in prod; seed script is dev-only. Admin created via Render Shell snippet (tested against throwaway postgres), data via admin ingestion API.

### Unplanned blockers found and fixed (pre-existing on main)
- `alembic upgrade head` failed: two heads (3f9a675e70e1, b3d6f1a29c47). Added single-head unit test (RED) + merge revision 33e53bae72d2 (GREEN); upgrade verified on empty postgres:16.
- `next build` failed type-check (nullable API schema vs interfaces, unused className prop, onSave Promise<void>, 2 test typings). Type-only fixes; build now passes.
- Pre-existing, NOT fixed: vitest `login-form.test.tsx` "submits valid credentials..." fails on main too; ruff E501 in chat_service.py.

### Decisions
- `Dockerfile.prod` next to dev Dockerfiles (compose untouched). Backend prod filters pytest/ruff/iniconfig/pluggy out of requirements.txt.
- Plans: 0.5c-512mb (services), 0.1c-256mb Postgres 16, Key Value 256mb noeviction, region frankfurt; names taken from the Blueprint spec fetch.

### Verification
- `docker compose config -q`: ok. Both prod images built. Throwaway containers: backend /health 200 (non-root `app`, PORT=10000, no pytest/ruff, postgres:// normalized), frontend /login 200 (non-root `node`); containers removed.
- Unit tests: 118 passed; ruff clean on touched files. Integration tests need real DB, not run. tsc clean except `LayoutProps` (build-generated global).
- render.yaml: parsed as YAML, hand-checked vs spec; Render CLI not installed, not machine-validated.

### Commits
see `git log feat/render-deploy` (DATABASE_URL, Dockerfiles, frontend types, alembic merge, render.yaml+docs).

