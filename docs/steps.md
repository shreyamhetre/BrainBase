# Steps

✅ done · ⬜ next

## Step 1: Project setup and database ✅

- ✅ Git repo with GitHub remote
- ✅ Folder structure
- ✅ docker-compose.yml (pgvector 0.8.7, Postgres 18)
- ✅ db/init enables the vector extension
- ✅ .env.example, .gitignore, README.md
- ✅ Postgres 18.6 + pgvector 0.8.7 running in Docker
- ✅ Tables created: documents, chunks, schema_migrations (HNSW + GIN indexes)

## Step 2: Ingest the handbook ✅

- ✅ Handbook content cloned into data/raw/handbook (4,174 pages)
- ✅ backend/scripts/inspect_handbook.py: pages, tokens, sections, front matter
- ✅ Last 1 year of Git history fetched; backend/scripts/handbook_dates.py writes each page's last-change date
- ✅ Page selection rules (option B) in backend/app/ingestion/handbook_selection.py
- ✅ Python 3.14 .venv: PyTorch 2.11 + CUDA 12.8 (RTX 3050 detected), sentence-transformers 6.1, psycopg 3.3
- ✅ requirements split: GPU (requirements.txt), CPU (requirements-cpu.txt), shared (requirements-common.txt)
- ✅ BGE-M3 runs on the GPU: 1024-dim vectors, ~22 chunks/s, 2.8 GB VRAM (backend/scripts/check_embedding.py)
- ✅ Shortcode inventory: 81 Hugo shortcodes, 2,429 uses (backend/scripts/inspect_shortcodes.py)
- ✅ Includes folder (assets/includes) fetched; all 78 include targets resolve
- ✅ Markdown cleaner: shortcodes, includes, HTML, links; code fences untouched (app/ingestion/markdown_clean.py)
- ✅ Chunker: split at h1-h3, breadcrumbs, anchors, merge < 80 tokens, split > 800 (app/ingestion/chunker.py)
- ✅ Page loader: front matter, URL, section, design doc status, owners, date (app/ingestion/handbook.py)
- ✅ Migration 002: people column on chunks
- ✅ Chunk preview and dry run: 3,307 pages → 30,043 chunks, ~8.2M tokens (backend/scripts/chunk_stats.py)
- ✅ Folder structure cleaned up: backend is an installable package, scripts moved to backend/scripts
- ✅ People shortcodes fixed: team-by-manager-slug, manager-by-report-name, stable-counterparts with manager (85 pages with people)
- ✅ Selection counts back from the snapshot date (2026-10-04), not today: 3,309 pages, 30,053 chunks every run
- ✅ Ingest script: documents + chunks, embed in batches, skip unchanged pages (app/ingestion/ingest_handbook.py)
- ✅ Test run on core sections: 149 pages, 1,942 chunks, all with vectors (~26 chunks/s); re-run skips unchanged pages
- ✅ Full run: 3,253 documents, 30,053 chunks, 0 missing vectors, 8.2M tokens, 458 MB (~22 chunks/s)
- ✅ Search test (backend/scripts/search_test.py): expected page found in top 50 for 6/6 questions; top 5 for vector 2/6, keyword 3/6

## Step 3: Query path ✅

- ✅ OpenAI key added to .env (GPT-4o mini)
- ✅ Hybrid search in one SQL query: vector (HNSW) + keyword (all-words first), permission filter in both WHERE clauses, ~200-400 ms (app/retrieval/search.py)
- ✅ Duplicate BGE-M3 weights removed (4.25 → 2.14 GB); models load offline from cache (HF_HUB_OFFLINE=1 in .env)
- ✅ RRF merge + BGE Reranker v2-m3 (top 50 → top 5): expected page in top 5 for 6/6 questions, up from 2/6 (app/retrieval/rank.py, retrieve.py)
- ✅ LangGraph graph: retrieve → answer, no separate rewrite call (app/graph.py)
- ✅ GPT-4o mini answer with numbered citations, via the openai SDK (app/generation/answer.py)
- ✅ CLI: python -m app.ask "question" (app/ask.py); 6 test questions ~4-5 s each, ~2,000 tokens each
- ✅ First 20 evaluation questions with expected pages (eval/questions.md)
- ✅ Langfuse running locally (docker-compose.langfuse.yml, http://localhost:3100), project and API keys created
- ✅ Langfuse tracing wired in: one trace per question with retrieve and GPT call (tokens, cost)
- ✅ FastAPI: POST /ask and GET /health, models loaded at startup (app/api/main.py)
- ✅ Tested through http://localhost:8000/docs (by Shreya): answers looked good, citations per claim

## Step 4: Evaluation ✅

- ✅ Own evaluation script, RAGAS later (backend/scripts/evaluate.py): hit@5, MRR, cited, no-answer in code; faithful + correct graded by GPT-4o mini
- ✅ Set cut to the 10 most important questions (eval/questions.md)
- ✅ Baseline: hit@5 9/9, MRR 0.81, cited 9/9, no-answer 1/1; correct 8/10 by hand (Q1 scope, Q8 relevance accepted as known limitations)
- ✅ Rerank pool 50 → 30: same retrieval scores, 6.1 → 4.3 s per question
- ✅ Results and known limitations recorded in eval/questions.md; full runs in eval/results/

## Step 5: Add product docs and issues (skipped)

Skipped by decision: the handbook covers policy and process; tickets come from synthetic GitLab issues in step 6.

## Step 6: Connectors, synthetic data and role-based access (RBAC)

- ✅ GitLab: private group gitmore-demo-shreya with 6 projects (company-wiki, engineering, security, people-ops, leadership, sales); token verified
- ✅ Slack: GitMore Demo workspace, GitMore bot in 6 channels (#general, #engineering, #sales, #hr-private, #security-incidents, #managers); token verified
- ✅ Users table (migration 003): email, bcrypt password hash, roles, is_admin, team, title, Slack/GitLab handles
- ✅ Login API: signup (no roles by default), login (JWT, 24 h, httpOnly cookie), logout, /auth/me; roles read from DB on every request
- ✅ Admin API: list users, assign roles, make admin, deactivate (admins only)
- ✅ /ask requires login; permission filter uses the user's roles
- ✅ Seeded admin (gitmore@gmail.com) + 20 demo people from data/synthetic/people.json (backend/scripts/seed_users.py)
- ✅ Synthetic content as files for review (data/synthetic/): 28 Slack messages, 9 GitLab issues (2 confidential), 7 wiki pages; traps: outdated PTO answer, HR-only salary bands, managers-only restructuring plan, security-only incident
- ⬜ Shreya reviews the files and the open decisions (docs/open-decisions.md)
- ⬜ Publish reviewed content to Slack and GitLab
- ⬜ Connectors: GitLab issues + wiki, Slack messages → chunks with allowed_roles
- ⬜ Permission, conflict and expertise questions in the evaluation (zero leaks)

## Step 7: Next.js chat UI and admin console

- ✅ Next.js 16 + TypeScript + Tailwind app in frontend/, /api proxied to FastAPI (same origin, httpOnly cookie)
- ✅ Login / sign-up page
- ✅ Chat: example questions, answers with clickable [n] citation chips, source cards (section, date, design-doc status, link)
- ✅ Admin page: users table, click role chips to grant/remove, admin and active switches
- ✅ Tested end to end through the proxy: login cookie, chat answer, HR user gets 403 on admin, admin sees 21 users
- ⬜ Conversation follow-ups (previous question + history), streaming answers, admin query inspector
