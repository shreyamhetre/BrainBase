<p align="center">
  <img src="docs/assets/gitMore-readme.png" alt="GitMore: your company's knowledge, in one place" width="560">
</p>

<p align="center">
  <b>Ask anything about the company. Get a cited answer from across its tools, filtered by who you are.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-in%20progress-f59e0b" alt="Status: in progress">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/postgres-18%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white" alt="Postgres 18 with pgvector">
  <img src="https://img.shields.io/badge/next.js-16-000000?logo=nextdotjs&logoColor=white" alt="Next.js 16">
</p>

<p align="center">
  <a href="#overview">Overview</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#access-control">Access control</a> ·
  <a href="#tech-stack">Tech stack</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="docs/project-plan.md">Project plan</a>
</p>

---

## Overview

GitMore is a company brain: one chat interface over everything a company knows, spread across its handbook, wiki, issues and chat.

It is built around GitLab, a remote company of about 2,000 people, using its **real public handbook** together with **synthetic Slack threads, wiki pages and confidential GitLab issues** that reference the real content, so the sources read like one company. The synthetic sources mirror the tools GitLab actually uses.

> [!NOTE]
> GitMore is an unofficial learning project. It is not affiliated with or endorsed by GitLab.

### Features

| Feature | Description |
|---|---|
| Hybrid search | Vector search for meaning and keyword search for exact terms, merged with reciprocal rank fusion |
| Reranking | A cross-encoder reads the top candidates closely and keeps the best five |
| Cited answers | Every claim links to the passage it came from |
| Role-based access | Each chunk records which roles may read it; restricted text never reaches the LLM |
| Admin console | Admins assign roles and deactivate accounts, with a confirmation before every change |
| Honest "I don't know" | Says so when there is no evidence instead of guessing |
| Measured quality | An evaluation set rerun after every change |
| Tracing | Every question traced in Langfuse: retrieved chunks, prompt, tokens, cost and latency |

## Architecture

GitMore has two halves. **Ingestion** prepares content ahead of time; the **query path** runs for every question. Postgres is the shared index between them.

```mermaid
flowchart LR
    subgraph Sources
        direction TB
        H[GitLab handbook]
        W[Wiki pages]
        I[GitLab issues<br/>incl. confidential]
        S[Slack threads]
    end

    subgraph Ingestion
        direction TB
        P[Parse and clean] --> C[Chunk by heading]
        C --> M[Attach metadata<br/>and allowed roles]
        M --> E[Embed<br/>BGE-M3]
    end

    Sources --> P
    E --> DB[(Postgres<br/>pgvector + full-text)]

    classDef store fill:#1e2a4a,stroke:#1e2a4a,color:#ffffff
    classDef step fill:#fff4ec,stroke:#fc6d26,color:#1b2140
    class DB store
    class P,C,M,E step
```

- **Metadata** is copied onto every chunk: source, URL, heading path, date, author, design-document status and the roles allowed to read it.
- **Selection rules** keep the handbook focused: recently changed pages, core policy sections and implemented design documents. About 25,000 chunks in total.

### Query path

```mermaid
flowchart TD
    U([Question + user's roles]) --> API[FastAPI<br/>JWT cookie checked]
    API --> G[LangGraph<br/>retrieve, then answer]
    G --> EQ[Embed question<br/>BGE-M3]

    subgraph PG[Postgres: one query, role filter in the WHERE clause]
        direction LR
        V[Vector search]
        K[Keyword search]
    end

    EQ --> V
    G --> K
    V --> F[Reciprocal rank fusion]
    K --> F
    F --> RR[Rerank<br/>top 30 to top 5]
    RR --> L[GPT-4o mini<br/>answer with citations]
    L --> A([Answer + sources])

    classDef io fill:#1e2a4a,stroke:#1e2a4a,color:#ffffff
    classDef step fill:#fff4ec,stroke:#fc6d26,color:#1b2140
    class U,A io
    class API,G,EQ,V,K,F,RR,L step
    style PG fill:#f7f7fb,stroke:#5d647e,color:#1b2140
```

- **The same embedding model** encodes chunks and questions, otherwise vector search would not match.
- **Fusion** combines the vector and keyword result lists by rank; the **reranker** then reads the pool closely and keeps the best five.
- **The permission filter runs inside the search query**, so restricted chunks are never retrieved, never ranked and never sent to the model.

### Planned extensions

- Query rewriting and follow-up questions that use the conversation history.
- A router that sends each message to search, an action, or a clarifying question.
- Actions through MCP (create an issue, post to Slack), always confirmed by the user first.
- Conflict detection when sources disagree, preferring the newer one and warning the user.

## Access control

```mermaid
flowchart LR
    L[Log in<br/>@gitmore.com only] --> T[JWT in an<br/>httpOnly cookie]
    T --> Q[Each request reads<br/>roles from the database]
    Q --> F[Search filtered to<br/>chunks the roles allow]
    AD[Admin console] -->|confirmed change| DB[(users table)]
    DB --> Q
```

| Role | Unlocks |
|---|---|
| everyone | The public handbook |
| engineer | Engineering channels and issues |
| hr | HR-only documents such as salary bands |
| manager | Leadership and restructuring plans |
| security | Security incidents and confidential security issues |
| sales | Sales channels and deals |

- New sign-ups get handbook access only; an admin grants roles.
- The admin holds every role. Admins cannot deactivate themselves.
- Roles are read from the database on every request, so a change takes effect immediately.

## Tech stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11+ | The strongest RAG ecosystem |
| Backend API | FastAPI | Simple, async, typed |
| Database | Postgres 18 + pgvector | Vectors, full-text search, metadata and users in one place |
| Embeddings | BGE-M3 (sentence-transformers, PyTorch CUDA) | Strong, multilingual, 8,192-token input, runs on a local GPU |
| Reranker | BGE Reranker v2-m3 | Free, fast, proven baseline |
| LLM | GPT-4o mini | Inexpensive, fast and good at grounded answers |
| Orchestration | LangGraph | Steps as a graph with state and branching |
| Auth | JWT, bcrypt | Stateless sessions in an httpOnly cookie |
| Frontend | Next.js 16, TypeScript, Tailwind CSS | Chat and admin console, responsive on all screen sizes |
| Tracing | Langfuse (self-hosted) | Chunks, prompt, tokens, cost and latency per question |
| Packaging | Docker Compose | One command for the database |

### Data sources

| Source | Type | What it tests |
|---|---|---|
| GitLab handbook | Real | Policies, onboarding, long documents |
| Slack threads | Synthetic | Informal answers, outdated answers |
| Wiki pages | Synthetic | Internal plans and restricted documents |
| GitLab issues | Synthetic, two confidential | Tickets linked to Slack discussions |

The synthetic content includes deliberate traps: an outdated PTO answer in Slack, HR-only salary bands, a managers-only restructuring plan and a security-only incident.

## Getting started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (on Windows it needs WSL2 and virtualization enabled in BIOS)
- Python 3.11+
- Node.js 20+
- An OpenAI API key
- An NVIDIA GPU is recommended for embedding; CPU works but is much slower

### 1. Configure `.env`

```bash
cp .env.example .env        # macOS/Linux
copy .env.example .env      # Windows
```

```env
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=company_db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/company_db

OPENAI_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

JWT_SECRET=                    # long random string
JWT_EXPIRE_HOURS=24
ALLOWED_EMAIL_DOMAIN=gitmore.com
ADMIN_EMAIL=you@gitmore.com
ADMIN_PASSWORD=
DEMO_USER_PASSWORD=            # shared password for the 20 demo people
```

`.env` is git-ignored. Changing `LLM_MODEL` or `LLM_BASE_URL` switches models without code changes. After the models download once, add `HF_HUB_OFFLINE=1` so they always load from the local cache.

### 2. Start Postgres

```bash
docker compose up -d
```

> [!TIP]
> The database user, password and name are created on the first start only. Data lives in a Docker volume and survives restarts; `docker compose down -v` deletes it.

### 3. Python environment

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS/Linux
pip install -r backend/requirements.txt        # NVIDIA GPU (CUDA 12.8)
pip install -r backend/requirements-cpu.txt    # no NVIDIA GPU
pip install -e backend
```

### 4. Create tables, ingest and seed users

All commands run from the project root.

```bash
python -m app.db.migrate
python -m app.ingestion.ingest_handbook
python backend/scripts/seed_users.py
```

This creates the admin and the 20 people in [data/synthetic/people.json](data/synthetic/people.json), with emails such as `priya.sharma@gitmore.com`. Sign-up and login only accept emails at `ALLOWED_EMAIL_DOMAIN`, checked in the backend.

### 5. Run GitMore

```bash
uvicorn app.api.main:app --reload --reload-dir backend/app   # API on :8000, docs at /docs
cd frontend && npm install && npm run dev                      # web app on http://localhost:3000
```

Log in as the admin to manage roles at `/admin`, or as a demo person to see answers for their role. From the command line:

```bash
python -m app.ask "How many weeks of parental leave do I get?"
```

### 6. Tracing (optional)

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

Langfuse opens at http://localhost:3100 and runs six containers separately from GitMore's database. It needs these settings in `.env`:

```env
LANGFUSE_BASE_URL=http://localhost:3100
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LF_INIT_USER_EMAIL=admin@gitmore.local
LF_INIT_USER_PASSWORD=
LF_SALT=
LF_ENCRYPTION_KEY=                   # 64 hex characters: openssl rand -hex 32
LF_NEXTAUTH_SECRET=
LF_POSTGRES_PASSWORD=
LF_CLICKHOUSE_PASSWORD=
LF_MINIO_PASSWORD=
LF_REDIS_PASSWORD=
```

## Evaluation

`python backend/scripts/evaluate.py` runs the questions in [eval/questions.md](eval/questions.md) and saves each run to `eval/results/`.

**Current baseline** (handbook, 10 questions):

| Metric | Result |
|---|---|
| Right page in the top 5 (hit@5) | 9 / 9 |
| Mean reciprocal rank | 0.81 |
| Right page cited | 9 / 9 |
| No-answer question handled | 1 / 1 |
| Time per question | about 4.3 s |

Permission, conflict and expertise questions are added as the synthetic sources are indexed. The target for permission leaks is zero.

## Roadmap

| Step | Scope | Status |
|---|---|---|
| 1 | Project setup, Postgres and pgvector in Docker | Done |
| 2 | Handbook ingestion: parse, chunk, embed, store with permission columns | Done |
| 3 | Query path: hybrid search, fusion, rerank, cited answers, Langfuse tracing | Done |
| 4 | Evaluation baseline | Done |
| 5 | Product docs and public issues | Skipped |
| 6 | Login and role-based access, synthetic Slack, wiki and issues published; connectors into the index | In progress |
| 7 | Next.js chat and admin console | In progress |
| 8 | Router, MCP actions with confirmation, clarifying questions | Planned |

## Project structure

```
GitMore/
├── backend/
│   ├── app/
│   │   ├── api/           FastAPI routes: ask, auth, admin
│   │   ├── auth.py        JWT cookies, password hashing, role checks
│   │   ├── ingestion/     selection rules, cleaning, chunking
│   │   ├── retrieval/     hybrid search, fusion, rerank, permission filter
│   │   ├── generation/    prompt, LLM call, citations
│   │   ├── graph.py       LangGraph pipeline
│   │   └── db/            connection and migration runner
│   ├── scripts/           seeding, publishing, evaluation and inspection scripts
│   └── requirements*.txt  GPU, CPU and shared dependencies
├── frontend/              Next.js chat and admin console
├── db/
│   ├── init/              runs on first database start (enables pgvector)
│   └── migrations/        numbered schema changes
├── data/
│   ├── raw/               cloned sources (git-ignored)
│   └── synthetic/         people, Slack, wiki and issue data
├── eval/                  evaluation questions and results
├── docs/                  project plan and assets
└── docker-compose.yml
```

## Data and licenses

- **GitLab Handbook** ([gitlab-com/content-sites/handbook](https://gitlab.com/gitlab-com/content-sites/handbook)) is published under the MIT License, Copyright (c) 2011-present GitLab B.V.
- **Slack threads, wiki pages, issues and people** in this repository are synthetic and invented for testing.

Raw GitLab content is downloaded locally into `data/raw/` and is not redistributed in this repository.

---

<p align="center">
  Built by <a href="https://github.com/shreyamhetre">Shreya Mhetre</a> to learn RAG, hybrid search, access control and agents end to end.
</p>
