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

## Step 2: Ingest the handbook

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
- ⬜ Fix people shortcodes that were dropped (team-by-manager-slug, stable-counterparts)
- ⬜ Ingest script: documents + chunks, embed in batches, skip unchanged pages (content_hash)
- ⬜ Test run on ~300 core pages, check rows in Postgres
- ⬜ Full run: ~30,000 chunks embedded (~23 min)
- ⬜ Search test: vector + keyword search return the right pages for sample questions

## Step 3: Query path

- ⬜ OpenAI key added to .env (you add it; GPT-4o mini)
- ⬜ Hybrid search in SQL: vector + keyword, permission filter in the WHERE clause
- ⬜ Merge with RRF, rerank top 50 → top 5 (BGE Reranker v2-m3)
- ⬜ LangGraph graph with the knowledge route
- ⬜ GPT-4o mini answer with citations
- ⬜ First 20 evaluation questions
- ⬜ Langfuse tracing
- ⬜ Test through a CLI script and FastAPI /docs
