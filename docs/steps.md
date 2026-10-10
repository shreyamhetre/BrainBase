# Steps

## Step 1: Project setup and database ✅

- ✅ Git repo with GitHub remote
- ✅ Folder structure
- ✅ docker-compose.yml (pgvector 0.8.7, Postgres 18)
- ✅ db/init enables the vector extension
- ✅ .env.example, .gitignore, README.md
- ✅ Postgres 18.6 + pgvector 0.8.7 running in Docker

## Step 2: Ingest the handbook

- ✅ Handbook content cloned into data/raw/handbook (4,174 pages)
- ✅ scripts/inspect_handbook.py: pages, tokens, sections, front matter
- ✅ Last 1 year of Git history fetched; scripts/handbook_dates.py writes each page's last-change date
- ✅ Page selection rules (option B) in backend/app/ingestion/handbook_selection.py
- ✅ Python 3.14 .venv: PyTorch 2.11 + CUDA 12.8 (RTX 3050 detected), sentence-transformers 6.1, psycopg 3.3
