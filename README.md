<p align="center">
  <img src="docs/assets/gitmore-logo.png" alt="GitMore: one brain across your company's tools" width="480">
</p>

<p align="center">
  <b>Ask anything about the company. Get a cited answer from across the company's tools, filtered by who you are.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-in%20progress-f59e0b?style=for-the-badge" alt="Status: in progress">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/postgres-18-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="Postgres 18">
  <img src="https://img.shields.io/badge/pgvector-0.8.7-7c3aed?style=for-the-badge" alt="pgvector 0.8.7">
</p>

<p align="center">
  <a href="#-how-it-works">How it works</a> ·
  <a href="#-tech-stack">Tech stack</a> ·
  <a href="#-getting-started">Getting started</a> ·
  <a href="#-roadmap">Roadmap</a> ·
  <a href="docs/project-plan.md">Full plan</a>
</p>

---

## 🦊 What is GitMore?

GitMore is a **company brain**: one chat interface over everything a company knows, spread across its handbook, docs, issues, meetings, Slack and Google Docs.

It's built around GitLab, a ~2,000-person remote company, using its **real public handbook, docs and issues** plus **synthetic Slack threads, Google Docs and confidential GitLab issues** that reference the real content, so it all feels like one company. These mirror the tools GitLab actually uses.

> [!NOTE]
> GitMore is an unofficial learning project. It is not affiliated with or endorsed by GitLab.

## ✨ Features

| | |
|---|---|
| 🔎 **Hybrid search** | Vector search for meaning plus keyword search for exact terms, merged with reciprocal rank fusion |
| 📌 **Cited answers** | Every claim links to the exact source passage it came from |
| 🔐 **Real permissions** | Each chunk knows who can see it; restricted text never reaches the LLM |
| 🧭 **One question box** | A router decides whether to search, act or ask you to clarify |
| ⚖️ **Conflict detection** | When sources disagree, the newer one wins and you're warned |
| 🙅 **Honest "I don't know"** | Says so when there's no evidence, instead of guessing |
| 🧑‍💻 **Who knows this?** | Suggests the people with expertise on a topic |
| ⚡ **Actions through MCP** | Create a GitLab issue, post to Slack or draft a Google Doc, after you confirm |
| 📊 **Measured quality** | A 90-question evaluation set, rerun after every change |

## 🧠 How it works

GitMore has two halves: **ingestion** prepares all content ahead of time, and the **query path** runs for every message. Postgres is the shared index that connects them.

### 1. Ingestion (runs on a schedule)

```mermaid
flowchart LR
    subgraph SRC["📥 Sources"]
        direction TB
        H["📘 Handbook"]
        D["📗 Product docs"]
        I["🐛 Issues & MRs"]
        M["🎙️ Meetings"]
        SL["💬 Slack"]
        N["📝 Google Docs"]
        J["🔒 Confidential issues"]
    end

    SRC --> SY["🔄 Sync<br/>new · changed · deleted"]
    SY --> P["📄 Parse"]
    P --> C["✂️ Chunk"]
    C --> MD["🏷️ Metadata +<br/>permissions"]
    MD --> E["🧮 Embed<br/>BGE-M3"]
    E --> DB[("🐘 Postgres<br/>pgvector + full-text")]

    classDef src fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef step fill:#f5f3ff,stroke:#8b5cf6,color:#2e1065
    classDef store fill:#7c3aed,stroke:#4c1d95,color:#ffffff
    class H,D,I,M,SL,N,J src
    class SY,P,C,MD,E step
    class DB store
```

- **Sync** fetches only new or changed content, and removes deleted docs, so stale answers don't pile up.
- **Metadata + permissions** are copied onto every chunk: source, URL, date, author and which roles can see it.

### 2. Query (runs for every message)

```mermaid
flowchart TD
    Q(["🙋 Message + your role"]) --> RT{"🧭 LangGraph router<br/>what does this need?"}

    RT -- "knowledge" --> RW["✏️ Rewrite query"]
    RW --> EQ["🧮 Embed question<br/>same BGE-M3 model"]

    subgraph PG["🐘 Postgres: one query, permission filter in the WHERE clause"]
        direction LR
        V["🧭 Vector search"]
        K["🔤 Keyword search"]
    end

    EQ --> V
    RW --> K
    V --> RRF["🔀 Merge with RRF"]
    K --> RRF
    RRF --> RR["🏅 Rerank<br/>top 50 → top 5<br/>BGE v2-m3"]
    RT -- "action" --> ACT["⚡ Action card<br/>you confirm"]
    RR -. "context, if the action needs it" .-> ACT
    ACT --> MCPW["🔌 MCP write<br/>ticket · post · page"]
    RT -- "unclear" --> CL["💭 Ask a<br/>clarifying question"]

    RR --> LLM["🤖 LLM answer<br/>with citations"]
    MCPW --> LLM
    LLM --> A(["💬 Streamed answer<br/>+ sources + freshness"])
    CL --> A

    classDef io fill:#7c3aed,stroke:#4c1d95,color:#ffffff
    classDef step fill:#f5f3ff,stroke:#8b5cf6,color:#2e1065
    classDef route fill:#fef9c3,stroke:#ca8a04,color:#422006
    classDef act fill:#fff7ed,stroke:#f97316,color:#7c2d12
    class Q,A io
    class RT route
    class RW,EQ,V,K,RRF,RR,LLM,CL step
    class ACT,MCPW act
    style PG fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
```

- **The router decides the route**, so users never pick a tool or type a command. One question box for everything.
- **Knowledge comes from the index through RAG; actions go through MCP.** A single request can use both: "Summarize the PTO policy and post it to #hr" searches first, then acts.
- **Unclear messages get a clarifying question** instead of a search, such as greetings or vague requests.
- **Every action needs your confirmation** before anything is written to Slack, GitLab or Google Docs.
- **Permissions apply to every answer:** all reads come from indexed, permission-tagged data, filtered inside the same SQL query as the search, so restricted chunks are never retrieved. MCP is used only for writes, not for reading live data.
- **Same embedding model** for chunks and questions, or vector search won't match.
- **RRF** (reciprocal rank fusion) combines the vector and keyword lists by rank, then the **reranker** reads the top 50 closely and keeps the best 5.
- **Langfuse traces every step**: route chosen, retrieved chunks, prompt, tokens, cost and latency.

## 🛠️ Tech stack

<p align="center">
  <img src="https://skillicons.dev/icons?i=python,fastapi,postgres,docker,nextjs,ts&theme=dark" alt="Python, FastAPI, Postgres, Docker, Next.js, TypeScript">
</p>

| Layer | Tool | Why |
|---|---|---|
| 🐍 Language | ![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) | Best RAG ecosystem |
| 🚀 Backend API | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) | Simple, async, streaming |
| 📄 Parsing | ![Markdown](https://img.shields.io/badge/Markdown-000000?logo=markdown&logoColor=white) ![Docling](https://img.shields.io/badge/Docling-PDFs-555555) | Keeps headings and tables |
| 🧮 Embeddings | ![Hugging Face](https://img.shields.io/badge/BGE--M3-FFD21E?logo=huggingface&logoColor=black) ![sentence-transformers](https://img.shields.io/badge/sentence--transformers-555555) ![PyTorch](https://img.shields.io/badge/PyTorch_CUDA-EE4C2C?logo=pytorch&logoColor=white) | Strong, multilingual, 8,192-token input, runs on a local GPU |
| 🐘 Vector + keyword DB | ![PostgreSQL](https://img.shields.io/badge/Postgres_18-4169E1?logo=postgresql&logoColor=white) ![pgvector](https://img.shields.io/badge/pgvector-7c3aed) | Vectors, full-text, metadata and users in one database |
| 🏅 Reranker | ![Hugging Face](https://img.shields.io/badge/BGE_Reranker_v2--m3-FFD21E?logo=huggingface&logoColor=black) | Free, fast, proven baseline |
| 🤖 LLM | ![OpenAI](https://img.shields.io/badge/GPT--4o_mini-412991?logo=openai&logoColor=white) | Cheap, fast, good at grounded answers |
| 🕸️ Orchestration | ![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white) | Steps as a graph with state, branching and retries |
| 🔌 Connectors + actions | ![MCP](https://img.shields.io/badge/MCP-000000?logo=modelcontextprotocol&logoColor=white) | Standard way to give agents tools; used for writes only |
| ⏰ Background sync | ![APScheduler](https://img.shields.io/badge/APScheduler-555555) | Incremental re-sync of sources |
| 🖥️ Frontend | ![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white) | Streaming chat and admin console |
| 📊 Evaluation | ![RAGAS](https://img.shields.io/badge/RAGAS-555555) | Context precision, recall, faithfulness |
| 📈 Tracing | ![Langfuse](https://img.shields.io/badge/Langfuse-0A0A0A) | Chunks, prompt, tokens, cost and latency per question |
| 🐳 Packaging | ![Docker](https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white) | One command to run it all |

### Data sources

| Source | | Type | Tests |
|---|---|---|---|
| ![GitLab](https://img.shields.io/badge/Handbook-FC6D26?logo=gitlab&logoColor=white) | 📘 | Real | Policies, onboarding, long docs |
| ![GitLab](https://img.shields.io/badge/Product_docs-FC6D26?logo=gitlab&logoColor=white) | 📗 | Real | Technical how-to answers |
| ![GitLab](https://img.shields.io/badge/Issues_&_MRs-FC6D26?logo=gitlab&logoColor=white) | 🐛 | Real | Discussions, decisions, freshness |
| ![YouTube](https://img.shields.io/badge/Unfiltered_meetings-FF0000?logo=youtube&logoColor=white) | 🎙️ | Real, transcribed | Spoken, messy text |
| ![Slack](https://img.shields.io/badge/Slack-4A154B?logo=slack&logoColor=white) | 💬 | Synthetic | Chat threads, informal answers |
| ![Google Docs](https://img.shields.io/badge/Google_Docs-4285F4?logo=googledocs&logoColor=white) | 📝 | Synthetic | Meeting notes, plans, an HR-only doc |
| ![GitLab](https://img.shields.io/badge/Confidential_issues-FC6D26?logo=gitlab&logoColor=white) | 🔒 | Synthetic | Internal tickets linked to real issues |

## 🚀 Getting started

### Prerequisites

- 🐳 [Docker Desktop](https://www.docker.com/products/docker-desktop/). On Windows it needs WSL2 and virtualization enabled in BIOS.
- 🐍 Python 3.11+ (developed on 3.14)
- 🎮 An NVIDIA GPU is recommended for embedding (CPU works, much slower)
- 🌿 Git
- 🔑 An OpenAI API key
- 🟢 Node.js 20+ (later, for the frontend)

### 1. Create `.env` from the example

```bash
cp .env.example .env        # macOS/Linux
copy .env.example .env      # Windows
```

Then fill in your values:

```env
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=company_db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/company_db

OPENAI_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

After the models are downloaded once (the first ingest or search does it), add `HF_HUB_OFFLINE=1` to `.env` so they always load from the local cache.

`.env` is git-ignored, so your keys never get committed. Changing `LLM_MODEL` or `LLM_BASE_URL` switches models with no code changes.

### 2. Start Postgres with pgvector

```bash
docker compose up -d
```

> [!TIP]
> The database user, password and name are created on the **first start only**. Data lives in a Docker volume and survives restarts; `docker compose down -v` deletes it.

### 3. Python environment

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS/Linux
pip install -r backend/requirements.txt        # NVIDIA GPU (CUDA 12.8)
pip install -r backend/requirements-cpu.txt    # no NVIDIA GPU
pip install -e backend                         # makes the backend's `app` package importable
```

### 4. Create the tables

```bash
python -m app.db.migrate
```

All commands run from the project root.

### 5. Create the users

Add to `.env`:

```env
JWT_SECRET=...                 # long random string
JWT_EXPIRE_HOURS=24
ADMIN_EMAIL=you@example.com    # your admin login
ADMIN_PASSWORD=...
DEMO_USER_PASSWORD=...         # shared password for the 20 demo people
```

```bash
python backend/scripts/seed_users.py
```

This creates the admin and the 20 invented people in [data/synthetic/people.json](data/synthetic/people.json) (emails like `priya.sharma@gitmore.example`).

### 6. Run GitMore

```bash
uvicorn app.api.main:app --reload --reload-dir backend/app   # backend on :8000 (API docs at /docs)
cd frontend && npm install && npm run dev                      # web app on http://localhost:3000
```

Log in as the admin to manage roles at `/admin`, or as a demo person to see answers for their role. From the command line: `python -m app.ask "How many weeks of parental leave do I get?"`.

Test questions with expected sources: [eval/questions.md](eval/questions.md).

### 7. Langfuse tracing (optional)

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

Opens at http://localhost:3100. It needs these settings in `.env` (generate random values for the secrets):

```env
LANGFUSE_BASE_URL=http://localhost:3100
LANGFUSE_PUBLIC_KEY=pk-lf-...        # any value; becomes the project's API key on first start
LANGFUSE_SECRET_KEY=sk-lf-...
LF_INIT_USER_EMAIL=admin@gitmore.local
LF_INIT_USER_PASSWORD=...            # your Langfuse login
LF_SALT=...
LF_ENCRYPTION_KEY=...                # 64 hex characters: openssl rand -hex 32
LF_NEXTAUTH_SECRET=...
LF_POSTGRES_PASSWORD=...
LF_CLICKHOUSE_PASSWORD=...
LF_MINIO_PASSWORD=...
LF_REDIS_PASSWORD=...
```

It runs 6 containers (web, worker, Postgres, ClickHouse, Redis, MinIO) separately from GitMore's database.

## 🗺️ Roadmap

| | Step | |
|---|---|---|
| 1 | 🐘 Project setup, Postgres + pgvector in Docker | ✅ |
| 2 | 📥 Ingest the handbook: parse, chunk, embed, store (permission columns included, default everyone) | ✅ |
| 3 | 🔎 Query path: LangGraph knowledge route, hybrid search, RRF, rerank, cited answers, first 20 eval questions, Langfuse tracing | ✅ |
| 4 | 📊 Evaluation: 10 key questions, baseline scores (hit@5 9/9, MRR 0.81), known limitations recorded | ✅ |
| 5 | 📗 Add product docs and issues | skipped |
| 6 | 💬 Synthetic Slack, GitLab wiki and confidential GitLab issues through connector sync + login and role-based access (RBAC) | ⏳ |
| 7 | 🖥️ Next.js chat and admin console | ⏳ |
| 8 | ⚡ Action route (MCP writes with confirmation), clarify route and stretch goals | |

Detailed progress: [docs/steps.md](docs/steps.md)

## 📊 Evaluation

Quality is measured, not guessed. `python backend/scripts/evaluate.py` runs the questions in [eval/questions.md](eval/questions.md) and records each run. It starts with the 10 most important handbook questions and grows as sources arrive: cross-source, expertise, conflicting sources, routing and permissions.

**Current baseline:** right page in the top 5 for 9/9 answerable questions, MRR 0.81, the right page cited 9/9, the no-answer question handled correctly, ~4.3 s per question. Known limitations are listed with the results.

| Metric | What it checks |
|---|---|
| 🎯 Hit rate @5 | The right chunk is in the top 5 results |
| 🥇 MRR | How high the right chunk ranks |
| ✅ Faithfulness | The answer sticks to its sources |
| 📌 Citation accuracy | Cited passages actually support the claim |
| 🧭 Routing accuracy | Messages go to the right route: knowledge, action, both or clarify |
| 🔐 Permission leaks | Must stay at **zero** |
| ⏱️ Latency | Median and p95 time to first token |

## 📁 Project structure

```
Company_Brain/
├── backend/
│   ├── app/               the Python package
│   │   ├── config.py      settings from .env
│   │   ├── api/           HTTP routes
│   │   ├── ingestion/     selection rules, cleaning, chunking, embedding
│   │   ├── retrieval/     hybrid search, RRF, rerank, permission filter
│   │   ├── generation/    prompts, LLM calls, citations
│   │   └── db/            migration runner and database access
│   ├── scripts/           inspection and check scripts (not part of the app)
│   ├── tests/
│   ├── pyproject.toml     makes `app` installable (pip install -e backend)
│   └── requirements*.txt  GPU, CPU and shared dependencies
├── frontend/              Next.js chat and admin console (later)
├── db/
│   ├── init/              SQL run on first database start (enables pgvector)
│   └── migrations/        numbered schema changes, applied once each
├── data/
│   ├── raw/               cloned sources (git-ignored)
│   └── synthetic/         generated Slack / Google Docs / issue data
├── eval/                  evaluation questions and results
├── docs/                  plan, progress, assets
├── .env                   your settings, shared by Docker Compose and the backend (git-ignored)
└── docker-compose.yml
```

## 📜 Data and licenses

- **GitLab Handbook** ([gitlab-com/content-sites/handbook](https://gitlab.com/gitlab-com/content-sites/handbook)): the repository is published under the MIT License, Copyright (c) 2011-present GitLab B.V.
- **GitLab product docs** (`doc/` in [gitlab-org/gitlab](https://gitlab.com/gitlab-org/gitlab)): licensed under [Creative Commons CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Slack threads, Google Docs and confidential issues** in this project are synthetic and invented for testing.

Raw GitLab content is downloaded locally into `data/raw/` and is not redistributed in this repository.

---

<p align="center">
  Built by <a href="https://github.com/shreyamhetre">Shreya Mhetre</a> as a hands-on way to learn RAG, hybrid search, permissions and agents.
</p>