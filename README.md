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

GitMore is built as a **configurable system**, with GitLab as the example company. Connectors, which roles can read each channel or project, and the MCP tools the assistant may use are all set up from the app by an admin, not in code.

> [!NOTE]
> GitMore is an unofficial learning project. It is not affiliated with or endorsed by GitLab.

### Features

| Feature | Description |
|---|---|
| Connectors (planned) | GitLab and Slack connectors, added from the app, sync content and its permissions into one index within seconds of a change |
| Router (planned) | One question box; the router chooses search, a live lookup, an action or a clarifying question |
| Actions through MCP (planned) | Create a GitLab issue or post to Slack through the official MCP servers, after the user confirms |
| Conversations (planned) | Chat history per user, so follow-up questions work |
| Hybrid search | Vector search for meaning and keyword search for exact terms, merged with reciprocal rank fusion |
| Reranking | A cross-encoder reads the top candidates closely and keeps the best five |
| Cited answers | Every claim links to the passage it came from |
| Role-based access | Each chunk records which roles may read it; restricted text never reaches the LLM |
| Admin console | Overview, users and roles, access requests and an activity log; every change is confirmed and recorded |
| Access requests | People ask for a role from their profile; the admin approves or denies with a note |
| Honest "I don't know" | Says so when there is no evidence instead of guessing |
| Measured quality | An evaluation set rerun after every change |
| Tracing | Every question traced in Langfuse: retrieved chunks, prompt, tokens, cost and latency |

## Architecture

GitMore has two halves. **Ingestion** keeps an index of every source up to date through connectors; the **query path** runs for every message and decides whether to answer from that index (RAG), take an action in a tool (MCP), or ask a clarifying question. Postgres is the shared index between them.

Solid boxes are built. Dashed boxes are designed and planned; see the [roadmap](#roadmap).

### 1. Ingestion: connectors sync every source into one index

```mermaid
flowchart LR
    subgraph Sources
        direction TB
        H[GitLab handbook<br/>real]
        I[GitLab issues<br/>incl. confidential]
        W[GitLab wiki]
        S[Slack channels]
    end

    subgraph Connectors[Connectors, configured in the app]
        direction TB
        CH[Handbook loader<br/>git clone + selection rules]
        CG[GitLab connector<br/>issues + wiki API]
        CS[Slack connector<br/>conversations API]
    end

    H --> CH
    I --> CG
    W --> CG
    S --> CS

    CH --> SY
    CG --> SY
    CS --> SY
    EV[Slack events + GitLab webhooks<br/>a change arrives within seconds] --> SY

    SY[Incremental sync<br/>new, changed, deleted] --> P[Parse and clean]
    P --> C[Chunk by heading<br/>or thread]
    C --> M[Metadata + allowed roles<br/>from project, channel, confidentiality]
    M --> E[Embed<br/>BGE-M3]
    E --> DB[(Postgres<br/>pgvector + full-text)]

    classDef store fill:#1e2a4a,stroke:#1e2a4a,color:#ffffff
    classDef built fill:#fff4ec,stroke:#fc6d26,color:#1b2140
    classDef planned fill:#ffffff,stroke:#5d647e,color:#1b2140,stroke-dasharray:5 4
    class DB store
    class CH,P,C,M,E built
    class CG,CS,SY,EV planned
```

- **Near real time.** Slack events (over Socket Mode, no public URL needed) and GitLab webhooks re-index a changed thread or issue within seconds. A scheduled sync, with its interval set per connector, catches anything missed and removes deleted items.
- **Connectors carry permissions.** Each source maps to roles: a Slack channel such as `#hr-private` maps to `hr`, a confidential issue in the security project maps to `security`, the handbook maps to everyone. Those roles are copied onto every chunk. A newly found channel or project is visible to admins only until it is mapped, so nothing leaks by default.
- **Incremental sync** fetches only new or changed content and removes deleted items, so stale answers don't pile up.
- **Metadata** on every chunk: source, URL, heading path or thread, author, date, design-document status and allowed roles.
- The synthetic Slack messages, issues and wiki pages are already published to a real Slack workspace and a private GitLab group by `backend/scripts/publish_synthetic.py`, so the connectors read them through the real APIs.

### 2. Query path: one question box, a router decides

```mermaid
flowchart TD
    U([Message + chat history + user's roles]) --> API[FastAPI<br/>JWT cookie checked]
    API --> RT{LangGraph router<br/>what does this need?}

    RT -- knowledge --> EQ[Embed question<br/>BGE-M3]
    RT -- action --> AC[Action card<br/>user confirms]
    RT -- unclear --> CL[Clarifying question]
    RT -- live lookup --> LL[Live lookup<br/>one named issue or channel<br/>roles checked first]
    LL --> L

    subgraph PG[Postgres: one query, role filter in the WHERE clause]
        direction LR
        V[Vector search]
        K[Keyword search]
    end

    EQ --> V
    RT -- knowledge --> K
    V --> F[Reciprocal rank fusion]
    K --> F
    F --> RR[Rerank<br/>top 30 to top 5]
    RR --> L[GPT-4o mini<br/>answer with citations]
    RR -. context, if the action needs it .-> AC
    AC --> MCP[MCP write<br/>GitLab issue, Slack post]
    MCP --> L
    L --> A([Answer + sources])
    CL --> A

    classDef io fill:#1e2a4a,stroke:#1e2a4a,color:#ffffff
    classDef built fill:#fff4ec,stroke:#fc6d26,color:#1b2140
    classDef planned fill:#ffffff,stroke:#5d647e,color:#1b2140,stroke-dasharray:5 4
    class U,A io
    class API,EQ,V,K,F,RR,L built
    class RT,AC,CL,MCP,LL planned
    style PG fill:#f7f7fb,stroke:#5d647e,color:#1b2140
```

- **The router picks the route**, so users never choose a tool or type a command. A single message can need both routes: "Summarize the PTO policy and post it to #hr" searches first, then acts.
- **The router also rewrites follow-ups.** With the last few turns of the conversation, "and for adoption?" becomes a full question before searching, in the same model call.
- **Knowledge goes through RAG; actions go through MCP.** Today every message takes the knowledge route.
- **Reads come from the index.** The one exception is the live lookup, for questions that name one item ("what's the latest on engineering#3?"): it fetches that item from the tool, but only after checking that the user's roles can read its project or channel. A tool connection sees more than any single user may, so GitMore never searches tools live on a user's behalf.
- **Actions run through the official GitLab and Slack MCP servers**, connected once by the admin. GitMore checks the user's role before every action and marks the post or issue "on behalf of" that person.
- **Every action needs the user's confirmation** before anything is written to Slack or GitLab.
- **The permission filter runs inside the search query**, so restricted chunks are never retrieved, ranked or sent to the model.
- **The same embedding model** encodes chunks and questions; **fusion** merges the vector and keyword lists by rank, and the **reranker** keeps the best five.

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
- People can request a role from their profile; the admin approves or denies it in the console, with an optional note.
- Every change to roles, accounts and requests is written to an activity log.

## Configuration and security

| Managed in the app | Who | What it controls |
|---|---|---|
| Connectors | Admin adds and runs; everyone sees status | Which tools are indexed, their tokens, sync interval, Sync now |
| Access mapping | Admin | Which roles can read each channel or project |
| MCP tools | Admin turns on or off; everyone sees what they can use | Which actions exist and which roles may use each one |
| Users, roles, requests | Admin | Who can read what |

- **Two kinds of secret, kept apart.** The login token (a JWT) lives in the browser in an httpOnly cookie that page scripts can't read. Tool tokens (Slack, GitLab) never reach the browser: they are stored in the database **encrypted**, with the key in `.env`, so a copy of the database alone can't use them.
- **Passwords** are bcrypt hashes. **Tool tokens** get the fewest permissions possible: read-only for syncing, a separate connection for actions.
- **The database** is reachable only from the machine (or private network) running GitMore, and the app connects as a user limited to its own tables.

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
| Connectors | GitLab API and webhooks, Slack API and Events (Socket Mode) | Sync issues, wiki pages and channels with their permissions, within seconds of a change |
| Actions | Official GitLab and Slack MCP servers | Standard way to give the agent tools; connected once by the admin |
| Background sync | APScheduler | Scheduled safety-net sync per connector |
| Secrets | Fernet encryption (Python `cryptography`) | Tool tokens encrypted in the database, key in `.env` |
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

JWT_SECRET=                    # python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_EXPIRE_HOURS=24
ALLOWED_EMAIL_DOMAIN=gitmore.com
ADMIN_EMAIL=you@gitmore.com
ADMIN_PASSWORD=
DEMO_USER_PASSWORD=            # shared password for the 20 demo people
SECRETS_KEY=                   # encrypts tool tokens: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
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
python backend/scripts/seed_connectors.py   # optional: demo Slack + GitLab connectors
```

This creates the admin and the 20 people in [data/synthetic/people.json](data/synthetic/people.json), with emails such as `priya.sharma@gitmore.com`. Sign-up and login only accept emails at `ALLOWED_EMAIL_DOMAIN`, checked in the backend.

`seed_connectors.py` reads `SLACK_BOT_TOKEN`, `GITLAB_URL`, `GITLAB_TOKEN` and `GITLAB_GROUP` from `.env` once, stores the tokens encrypted in the database and maps each channel and project to roles from the synthetic data. You can also add connectors from the Connectors page instead.

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
| 6 | Login and role-based access; synthetic Slack, wiki and issues published | Done |
| 7 | Next.js app: sidebar layout, chat, profile, settings, admin console with access requests and activity log | Done |
| 8 | Settings foundation: roles, connectors and access mapping managed in the app, encrypted tokens | Done |
| 9 | Connectors: GitLab and Slack sync, Slack events and GitLab webhooks | Next |
| 10 | Permission evaluation: questions asked as specific users, zero leaks | Planned |
| 11 | Conversations: chat history, sidebar list, follow-up questions | Planned |
| 12 | Router: knowledge, live lookup, action and clarify routes | Planned |
| 13 | MCP actions: official servers connected in the app, action cards with confirmation, role checks | Planned |
| 14 | Routing evaluation, streaming answers, query inspector | Planned |

## Project structure

```
GitMore/
├── backend/
│   ├── app/
│   │   ├── api/           FastAPI routes: ask, auth, account, admin
│   │   ├── auth.py        JWT cookies, password hashing, role checks
│   │   ├── audit.py       activity log
│   │   ├── vault.py       encrypts tool tokens (key in .env)
│   │   ├── roles.py       roles from the database
│   │   ├── connectors/    Slack and GitLab clients
│   │   ├── ingestion/     selection rules, cleaning, chunking
│   │   ├── retrieval/     hybrid search, fusion, rerank, permission filter
│   │   ├── generation/    prompt, LLM call, citations
│   │   ├── graph.py       LangGraph pipeline
│   │   └── db/            connection and migration runner
│   ├── scripts/           seeding, publishing, evaluation and inspection scripts
│   └── requirements*.txt  GPU, CPU and shared dependencies
├── frontend/              Next.js app: chat, profile, settings, connectors, MCP tools, admin console
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
