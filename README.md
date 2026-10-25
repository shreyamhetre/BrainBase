<div align="center">

<img src="assets/brainbase-hero.svg" alt="Brainbase — A configurable foundation for company intelligence" width="100%">

<br/>

<p>
  <strong>A configurable foundation for company intelligence.</strong><br>
  Connect company knowledge. Retrieve with evidence. Respect permissions. Enable AI-powered workflows.
</p>

<p>
  <a href="#meet-gitmore">Explore GitMore</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#run-locally">Run locally</a>
</p>

<p>
  <img src="https://img.shields.io/badge/status-in%20development-orange?style=flat-square" alt="Project status: in development">
  <img src="https://img.shields.io/badge/Python-FastAPI-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python and FastAPI">
  <img src="https://img.shields.io/badge/Orchestration-LangGraph-1C3C3C?style=flat-square" alt="LangGraph">
  <img src="https://img.shields.io/badge/Database-PostgreSQL%20%2B%20pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL and pgvector">
  <img src="https://img.shields.io/badge/UI-Next.js-black?style=flat-square&logo=next.js" alt="Next.js">
</p>

</div>

---

## The problem

Company knowledge rarely lives in one place. It is spread across repositories, handbooks, issue trackers, chat threads, documents, and internal tools.

People waste time searching, repeat questions, and struggle to tell which source is authoritative. A unified assistant introduces another challenge: **it must never expose information a person is not allowed to see.**

## The idea

**Brainbase is a configurable foundation for building company-specific AI brains.**

Rather than hardcoding one assistant for one organization, Brainbase is designed around configurable sources, indexing and retrieval, model settings, workflow routing, roles, access mappings, and external tools.

- **Connect:** bring knowledge together from organizational tools.
- **Retrieve:** combine semantic and keyword search, then rerank evidence.
- **Answer:** generate grounded responses with citations.
- **Respect access:** filter restricted content before it reaches the language model.
- **Act:** route requests to tools through controlled, auditable workflows.
- **Measure:** inspect traces and evaluate retrieval and answer quality.

The aim is bigger than a chatbot: one configurable foundation that can support different company-brain implementations.

## Meet GitMore

<a id="meet-gitmore"></a>

**GitMore is Brainbase's reference implementation**: a company brain for the GitLab ecosystem.

It demonstrates how a company-specific experience can bring together GitLab projects and issues, Slack conversations, and company documentation through one interface. Synthetic internal content is used to demonstrate confidential information, role restrictions, and conflicting answers.

<div align="center">

<img src="assets/brainbase-gitmore-flow.svg" alt="Brainbase foundation powering GitMore with GitLab, Slack and company documentation" width="100%">

</div>

### What GitMore demonstrates

- A chat interface with clickable source citations.
- Handbook ingestion, hybrid retrieval, reciprocal rank fusion, and reranking.
- User authentication and database-backed roles.
- Source-level access mappings for GitLab projects and Slack channels.
- Configurable connector settings and encrypted connector credentials.
- Manual and scheduled synchronization, plus event-handling infrastructure.
- An admin console for users, roles, access requests, connectors, and activity logs.
- Tracing and a repeatable evaluation script for retrieval and answer quality.

GitMore is an example configuration—not the boundary of Brainbase's intended scope.

## Architecture

Brainbase has two main paths: **ingestion**, which prepares and updates the knowledge index, and **query execution**, which processes a user's request.

<a id="architecture"></a>

<div align="center">

<img src="assets/brainbase-architecture.svg" alt="Brainbase architecture: configurable sources, ingestion, PostgreSQL vector index, retrieval, routing, grounded answers and controlled actions" width="100%">

</div>

### 1. Configure sources and access

Administrators configure connector credentials, synchronization, roles, source-level access mappings, and MCP tool settings. Connector credentials are encrypted at rest.

### 2. Ingest and index

Content is parsed, cleaned, split into meaningful chunks, enriched with metadata, embedded, and stored in PostgreSQL with pgvector and full-text search. Synchronization updates changed content and removes content that no longer exists in a source.

### 3. Retrieve evidence

The query path combines vector and keyword search, merges candidate lists using reciprocal rank fusion (RRF), and reranks results to prioritize relevant evidence. Access restrictions are applied in the retrieval query before content is passed to the language model.

### 4. Generate grounded answers

The language model answers from retrieved context and provides source citations. The intended behavior is to surface missing evidence and source conflicts rather than present unsupported guesses as facts.

### 5. Route and act

LangGraph provides the orchestration layer for multi-step workflows. The intended routing model covers knowledge retrieval, authorized live lookups, tool actions, and clarification. MCP enables standardized tool integration; write operations should require authorization, user confirmation, and audit logging.

## Demo

Screenshots from GitMore running locally with the demo data.

**Cited answers across sources.** An engineer asks about PTO notice. The answer follows the handbook and points out that an older Slack thread said something different.

<img src="assets/screenshots/chat-cited-answer.png" alt="GitMore chat: an answer about PTO notice citing two handbook pages and naming an older, conflicting Slack thread, with source cards below" width="100%">

**Permissions before generation.** The same question about draft salary bands, asked by an engineer and by someone in HR. Restricted content never reaches the model for the engineer.

<table>
  <tr>
    <th width="50%">Engineer</th>
    <th width="50%">HR</th>
  </tr>
  <tr>
    <td valign="top"><img src="assets/screenshots/permissions-engineer.png" alt="An engineer asks for the 2027 salary bands and gets: I couldn't find this in the sources you can access" width="100%"></td>
    <td valign="top"><img src="assets/screenshots/permissions-hr.png" alt="Someone in HR asks the same question and gets the draft bands, cited from the HR-only wiki page and the private HR Slack channel" width="100%"></td>
  </tr>
</table>

**Connectors and access mapping.** Admins connect Slack and GitLab, sync on a schedule or on demand, and choose which roles can read each channel or project.

<img src="assets/screenshots/connectors.png" alt="Connectors page: Slack and GitLab connectors with sync status, and a table mapping each Slack channel to the roles that can read it" width="100%">

**Admin console.** People, roles, access requests and an activity log, with a confirmation before every change.

<img src="assets/screenshots/admin-console.png" alt="Admin console: overview tiles, people per role, and the users table with role dropdowns and active switches" width="100%">

### Suggested walkthrough

1. Ask a question about a company policy or engineering process.
2. Inspect the cited sources and open the original document or issue.
3. Sign in as a different demo user and compare what information is visible.
4. Open the connector settings to inspect synchronization and source access.
5. Review the admin console and activity log.

> **Demo environment:** GitMore is an unofficial learning/reference implementation. GitLab handbook content is public content; synthetic internal records are used for confidential-data and permission demonstrations. Do not enter real secrets or private company data into a public demo.

## Engineering highlights

### Retrieval quality

The current pipeline uses BGE-M3 embeddings, hybrid vector and keyword search, reciprocal rank fusion, and BGE Reranker v2-m3.

Initial evaluation baseline:

| Metric | Baseline |
|---|---:|
| Retrieval hit@5 | 9/9 |
| Mean reciprocal rank (MRR) | 0.81 |
| Questions with citations | 9/9 |
| Correct answers by manual review | 8/10 |
| No-answer test | 1/1 |

These results are from the initial evaluation set, not a comprehensive benchmark. They serve as a baseline for further improvements.

### Permission-aware retrieval

- Role definitions are stored in the database.
- Source access mappings control which roles can read each project or channel.
- Newly discovered sources are denied to ordinary users until access is mapped.
- Retrieval filters restricted chunks before they reach the model.

Permission correctness is a critical system requirement and should be validated continuously with cross-role tests.

### Synchronization and freshness

- Scheduled synchronization, with the interval set per connector, plus an on-demand **Sync now**.
- Per-connector locking and change-aware upserts: unchanged content is never re-embedded.
- Deletion handling to remove content that disappears from a source.
- Access changes apply to indexed content immediately, without waiting for the next sync.

### Security and observability

- Password hashes stored with bcrypt.
- JWT session delivered through an HTTP-only cookie.
- Connector tokens encrypted in the database using Fernet.
- Secret material supplied through environment configuration.
- Langfuse tracing for model and retrieval activity, including token usage, cost, and latency.
- Evaluation scripts for retrieval metrics, citation presence, no-answer behavior, and model-assisted answer grading.

## Technology stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS | Chat and admin experience |
| API | Python, FastAPI | Application endpoints |
| Orchestration | LangGraph | Workflow execution |
| LLM | GPT-4o mini via OpenAI SDK | Answer generation |
| Embeddings | BGE-M3 | Local embedding generation |
| Reranker | BGE Reranker v2-m3 | Relevance ranking |
| Database | PostgreSQL 18, pgvector 0.8.7 | Vectors, full-text search, metadata, users |
| Connectors | GitLab API, Slack API | Content and metadata synchronization |
| Tool integration | MCP | Standardized external tool interfaces |
| Observability | Langfuse | Tracing and model-call metrics |
| Local infrastructure | Docker Compose | Database and supporting services |

## Run locally

Brainbase is a local development project: Docker Compose for the database, a Python (FastAPI) backend, and a Next.js frontend. All commands run from the repository root unless noted.

### Prerequisites

- Git
- Docker Desktop with virtualization enabled (on Windows: WSL2)
- Python 3.11+
- Node.js 20+ and npm
- An OpenAI API key (or any OpenAI-compatible endpoint)
- An NVIDIA GPU is recommended for the embedding and reranker models; CPU works, more slowly
- GitLab and Slack credentials if you want to try the connectors and actions

### 1. Clone the repository

```bash
git clone https://github.com/shreyamhetre/BrainBase.git
cd BrainBase
```

### 2. Configure environment variables

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Fill in `.env`. Each setting is explained in `.env.example`; at minimum set the database values, `OPENAI_API_KEY`, `JWT_SECRET`, `SECRETS_KEY` and the seed account passwords. `.env` is git-ignored: keep API keys, tokens and secrets out of Git.

### 3. Start PostgreSQL with pgvector

```bash
docker compose up -d
```

### 4. Set up the Python backend

```bash
python -m venv .venv
.venv\Scripts\activate                        # Windows
source .venv/bin/activate                     # macOS/Linux
pip install -r backend/requirements.txt       # NVIDIA GPU (CUDA)
pip install -r backend/requirements-cpu.txt   # or: no NVIDIA GPU
pip install -e backend                        # makes the backend's `app` package importable
python -m app.db.migrate                      # create the tables
python backend/scripts/seed_users.py          # the admin and 20 demo people
```

### 5. Index the GitLab handbook

The handbook is a large repository; only the pages and one year of history are fetched:

```bash
git clone --filter=blob:none --no-checkout --shallow-since="1 year ago" https://gitlab.com/gitlab-com/content-sites/handbook.git data/raw/handbook
git -C data/raw/handbook sparse-checkout set content/handbook assets/includes
git -C data/raw/handbook checkout main
python backend/scripts/handbook_dates.py      # each page's last-change date
python -m app.ingestion.ingest_handbook       # chunk, embed and store (about 30,000 chunks)
```

The first run downloads the BGE-M3 and reranker models. Afterwards, set `HF_HUB_OFFLINE=1` in `.env` so they load from the local cache.

### 6. Run GitMore

```bash
uvicorn app.api.main:app --reload --reload-dir backend/app   # API on http://localhost:8000 (docs at /docs)
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                                   # web app on http://localhost:3000
```

Log in with `ADMIN_EMAIL` and `ADMIN_PASSWORD`, or as a demo person such as `aiko.tanaka@gitmore.com` with `DEMO_USER_PASSWORD`.

### 7. Connect Slack and GitLab (optional)

- **Connectors** (search): on the Connectors page, add Slack (bot token) and GitLab (URL, group, token), choose which roles can read each channel or project, then click Sync now. For the demo data, `python backend/scripts/seed_connectors.py` does the same from the tokens in `.env`.
- **Actions** (MCP): on the MCP tools page, connect GitLab's official MCP server with a fine-grained personal access token (Duo permission "MCP tool: Execute"), and Slack's with a user token from your Slack app (with Slack MCP server access enabled for the app). Then turn on the actions people may use and choose their roles.

### 8. Tracing and checks (optional)

```bash
docker compose -f docker-compose.langfuse.yml up -d          # Langfuse on http://localhost:3100
python -m unittest discover -s backend/tests                  # fast tests
python backend/scripts/evaluate_access.py --retrieval-only    # permission check, no GPT calls
```

## Design principles

- **Configurable over hardcoded:** organization-specific settings should be expressed through configuration wherever practical.
- **Evidence over guesses:** answers should be grounded in sources and acknowledge missing evidence.
- **Permissions before generation:** restricted content must be filtered before it reaches the model.
- **Actions with accountability:** external write operations should be authorized, confirmed, and recorded.
- **Measure before optimizing:** retrieval and routing improvements should be evaluated against repeatable test sets.
- **Build incrementally:** keep the system understandable while expanding its capabilities.

---

<div align="center">

### Brainbase

**A foundation for building company brains.**

Built by **Shreya Mhetre**

<sub>Brainbase is an independent project. GitMore is an unofficial reference implementation and is not affiliated with or endorsed by GitLab.</sub>

</div>
