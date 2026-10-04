# GitLab Company Brain (unofficial)

A learning project: one chat interface that answers questions about GitLab from its public handbook, docs and issues, plus synthetic Slack, Notion and Jira data, with cited answers and role-based permissions.

Not affiliated with or endorsed by GitLab.

**Status:** in progress. Database setup is done; the RAG backend is next. See [docs/steps.md](docs/steps.md).

- Plan: [docs/project-plan.md](docs/project-plan.md)
- Progress: [docs/steps.md](docs/steps.md)

## How it works

The brain has two halves: ingestion prepares all content ahead of time, and the query path runs for every question.

```
INGESTION (runs ahead of time, on a schedule)
  connector sync (new/changed/deleted only) → parse → chunk
  → attach metadata + permissions → embed (BGE-M3)
  → Postgres (pgvector + full-text + metadata + permissions)

QUERY (runs for every question)
  question → rewrite → embed question (BGE-M3)
  → hybrid search (vector + keyword, permission filter in the same query)
  → merge with RRF → rerank top 50 → top 5 (BGE v2-m3)
  → LLM answer with citations → stream to UI
  (every step traced in Langfuse)
```

- Each chunk carries its source, URL, date and who can see it, so the permission filter runs inside the search query and restricted text never reaches the LLM.
- Vector search finds passages with similar meaning; keyword search finds exact terms. Reciprocal rank fusion (RRF) merges both lists before reranking.
- Answers cite the exact passages they used, and say "I couldn't find this" when the evidence is missing.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (on Windows it needs WSL2 and virtualization enabled in BIOS)
- Python 3.11+
- Git
- An OpenAI API key
- Node.js 20+ (later, for the frontend)

## Run the database

1. Create a `.env` file in the project root:

   ```
   POSTGRES_USER=your_user        # must not start with "pg_"
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=company_db
   POSTGRES_PORT=5432
   DATABASE_URL=postgresql://your_user:your_password@localhost:5432/company_db

   OPENAI_API_KEY=
   ```

2. Start Postgres with pgvector:

   ```
   docker compose up -d
   ```

The user, password and database are created on the first start only. Data is kept in a Docker volume and survives restarts; `docker compose down -v` deletes it.

## Folder structure

```
backend/         FastAPI app (Python)
  app/api/         HTTP routes
  app/ingestion/   sync, parse, chunk, embed
  app/retrieval/   hybrid search, RRF, rerank, permission filter
  app/generation/  prompts, LLM calls, citations
  app/db/          schema and database access
  tests/
frontend/        Next.js chat and admin console (later)
db/init/         SQL run on first database start
data/raw/        cloned sources (git-ignored)
data/synthetic/  generated Slack / Notion / Jira data
eval/            evaluation questions and results
scripts/         one-off helper scripts
docs/            plan and progress
```

## Data and licenses

- **GitLab Handbook** ([gitlab-com/content-sites/handbook](https://gitlab.com/gitlab-com/content-sites/handbook)): the repository is published under the MIT License, Copyright (c) 2011-present GitLab B.V.
- **GitLab product docs** (`doc/` in [gitlab-org/gitlab](https://gitlab.com/gitlab-org/gitlab)): licensed under [Creative Commons CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Slack, Notion and Jira data** in this project is synthetic and invented for testing.

Raw GitLab content is downloaded locally into `data/raw/` and is not redistributed in this repository.
