# GitMore: GitLab Company Brain — Project Plan

By Shreya Mhetre

## Overview

We will build a working company brain for GitLab: one chat interface that answers employee questions from the real public handbook, docs and issues, plus synthetic Slack, Google Docs and confidential GitLab issues, with cited answers and role-based permissions.

**Problem it solves.** GitLab is a \~2,000-person remote company. Knowledge is spread across a huge handbook, thousands of issues, chat threads and meetings. People waste time searching, ask the same questions repeatedly and miss decisions. The brain gives one place to ask, with trustworthy cited answers that respect who can see what.

**What we want to learn**

- How ingestion, chunking, embeddings and indexing work end to end
- How hybrid search, reranking and citations improve answer quality
- How connectors sync tools into the index and carry their permissions
- How a router decides between search, actions and clarifying questions
- How an agent takes actions in tools through MCP
- How to measure quality with an evaluation set

This is a learning project: GitLab data is used as public, openly licensed content, and the app should be labelled as unofficial.

## Data plan

Start with one real source (the handbook), add docs and issues, then layer in synthetic tools that reference the real content so everything feels like one company.

| Source | Real or synthetic | How to get it | Tests |
| --- | --- | --- | --- |
| Handbook | Real | Clone the public handbook repo (Markdown) | Policies, onboarding, long docs |
| Product docs | Real | Clone the docs repo (Markdown) | Technical how-to answers |
| Issues, epics, MRs | Real | Public GitLab API, a few projects only | Discussions, decisions, freshness |
| Meeting transcripts | Real | 10 to 20 GitLab Unfiltered videos, transcribed with Whisper | Spoken, messy text |
| Slack | Synthetic | Free workspace, channels filled by an LLM script | Chat threads, informal answers |
| Google Docs / Drive | Synthetic | Free Google Drive with meeting notes, plans and an HR-only doc | Mixed doc types, sharing permissions |
| Confidential GitLab issues | Synthetic | Free private GitLab project with internal tickets linked to real issues | Cross-tool linking; same connector as real issues |

GitLab uses Slack for chat, Google Docs for meeting notes and plans, Zoom for meetings and its own GitLab issues for tickets; it doesn't use Jira or Notion internally. The synthetic sources mirror that, so the demo matches how GitLab really works.

**Which handbook pages are ingested**

The handbook is ~4,200 pages (~10.5M tokens). Dates come from the last year of Git history. Rules live in `backend/app/ingestion/handbook_selection.py`:

- Pages changed in the last year are kept.
- Core policy sections are kept whatever their age: values, company, people-policies, total-rewards, people-group, hiring, communication, leadership.
- Design documents: implemented, ongoing, accepted and rejected are kept whatever their age; proposals untouched for over a year are dropped. Each chunk stores the doc's status so a proposal is never presented as how GitLab works.

Result: about 9M tokens, roughly 25,000 chunks.

**Rules for synthetic data**

- Invent one consistent cast: about 20 people across Engineering, HR, Sales and Security, each with a role and team.
- Cover 3 to 6 months of activity so dates, updates and outdated answers exist.
- Reference real handbook pages and issue numbers so sources connect.
- Plant deliberate traps: a Slack answer that contradicts a newer handbook page, an HR-only doc, a question with no answer anywhere.

## Architecture

The brain has two halves: an ingestion pipeline that prepares all content ahead of time, and a fast query path that runs for each message.

```
INGESTION (runs ahead of time, on a schedule)
  connector sync (new/changed/deleted only) → parse → chunk
  → attach metadata + permissions → embed (BGE-M3)
  → Postgres (pgvector + full-text + metadata + permissions)

QUERY (runs for every message)
  message → LangGraph router: what does this need?
    knowledge → rewrite → embed question (BGE-M3)
      → hybrid search (vector + keyword, permission filter in the same query)
      → merge with RRF → rerank top 50 → top 5 (BGE v2-m3)
      → LLM answer with citations (GPT-4o mini)
    action    → action card → user confirms → MCP write (ticket · post · page)
                (uses search results as context when the action needs them)
      → LLM reply with the result (e.g. "Ticket ENG-123 created")
    unclear   → ask a clarifying question (greetings, vague requests)
  → stream to UI
  (every step traced in Langfuse)
```

**Ingestion**

- **Sync first:** connectors fetch only new or changed content, and deleted docs are removed from the index, so stale answers don't pile up.
- **Metadata and permissions at chunk time:** each chunk carries its source, URL, date and who can see it, copied from the original doc. The permission filter checks these fields later.

**Query**

- **One entry point, router decides:** users ask in plain language; a LangGraph router picks knowledge (RAG), action (MCP), both, or a clarifying question. For example, "Summarize the PTO policy and post it to #hr" searches first, then acts.
- **No separate rewrite call:** each message costs one answer call. Step 3 answers standalone questions (retrieve → answer). Follow-ups in the chat (step 7) search with the previous question plus the new one and pass the chat history to the answer call, still one call. In step 8 the router's call also returns the standalone question, so rewriting adds no extra call.
- **MCP for writes only:** all reads come from the indexed, permission-tagged data. Live MCP reads are skipped for now, because admin-connected MCP servers could see more than the user is allowed to.
- **Embed the question with the same model:** after rewriting, the question is embedded with BGE-M3, the same model used for chunks, or vector search won't match properly.
- **Permission filter inside the search:** applied as a WHERE condition in the same SQL query as the search, so restricted chunks never reach the LLM.
- **Merge before reranking:** vector and keyword search return separate lists, combined with reciprocal rank fusion (RRF).
- **Rerank a fixed number:** for example, top 50 in, top 5 out.
- **LLM:** GPT-4o mini through the official OpenAI API. The model name and base URL live in `.env`, so switching models is a config change, not a code change.
- **Tracing:** Langfuse records every step of the query path, including the route chosen.

The Index (Postgres) is the shared store that connects both halves.

## Tech stack

Everything below is free or has a free tier, and runs on a laptop plus one LLM API key.

| Layer | Pick | Why |
| --- | --- | --- |
| Language | Python 3.11+ | Best RAG ecosystem |
| Backend API | FastAPI | Simple, async, streaming support |
| Parsing | Markdown parser, Docling for PDFs | Keeps headings and tables |
| Embeddings | BGE-M3 (1024 dims), run with sentence-transformers on the local GPU (PyTorch 2.11, CUDA 12.8) | Strong, multilingual, 8,192-token input, free to self-host |
| Vector + keyword DB | Postgres 18 with pgvector (Docker image), plus full-text search | One database for vectors, BM25-style search, metadata and users |
| Reranker | BGE Reranker v2-m3 | Free, fast, proven baseline |
| LLM | GPT-4o mini (OpenAI API) | Cheap, fast, good at grounded answers |
| Orchestration | LangGraph | Steps as a graph with shared state, branching and retries; built for agents |
| Connectors and actions | MCP servers, connected by an admin, used for writes only | Standard way to give agents tools; reads stay on permission-tagged data |
| Background sync | A scheduled job (APScheduler or cron) | Incremental re-sync of sources |
| Frontend | Next.js | Real product feel, streaming chat and admin console |
| Evaluation | RAGAS plus a custom script | RAG-specific metrics: context precision, recall, faithfulness |
| Tracing | Langfuse (self-hosted in Docker) | Every step per question: chunks, prompt, tokens, cost, latency |
| Packaging | Docker Compose | One command to run it all |

## UI: inputs and outputs

The app has two screens: a chat for employees and an admin console for you to see how the brain works inside.

**Chat inputs**

- Plain-language question box, with follow-up questions in the same thread
- Role switcher (Engineer, HR, Manager, Guest) to demo permissions; in a real product the role comes from login, never a dropdown
- Filters: source, team, date range
- Upload a file to ask questions about it
- Actions asked in plain language ("create an issue for this bug"); the router decides. Slash commands such as /ticket or /who-knows are optional shortcuts

**Chat outputs**

- Streamed answer with numbered citations that open the exact source passage
- Sources panel showing which tools contributed and how fresh each source is
- "I couldn't find this" when evidence is missing, instead of a guess
- Conflict warning when sources disagree, with the newer one preferred
- Suggested experts for the topic
- Action cards to confirm before acting: create a GitLab issue, post to Slack, draft a Google Doc
- A clarifying question when the request is unclear
- Thumbs up or down on every answer, stored for evaluation

**Admin console**

- Connectors: status, last sync time, documents per source
- Query inspector: for any question, the route chosen, the rewritten query, retrieved chunks with scores, reranked order and final prompt
- Permission tester: run one question as two roles and compare results
- Evaluation dashboard: accuracy and retrieval metrics per test run
- Latency breakdown: retrieval, reranking, first token, total

## Roadmap

Steps run in this order, with no fixed dates. One gate: core RAG must pass the evaluation set before new sources are added.

| Step | What gets built | Done when |
| --- | --- | --- |
| 1 | Project setup, Postgres + pgvector in Docker | Database runs, tables created |
| 2 | Ingest the handbook: parse, chunk, embed, store. Permission and metadata columns created now, defaulting to everyone | ~25,000 chunks stored with metadata |
| 3 | Query path: LangGraph graph with the knowledge route, hybrid search, RRF, rerank, cited answers. First 20 eval questions. Langfuse tracing. Test through a CLI script or FastAPI's /docs page | Questions return cited answers; traces visible |
| 4 | Full evaluation set and baseline scores. **Gate:** core RAG passes before new sources are added | Baseline metrics recorded |
| 5 | Add product docs and issues | Cross-source questions pass |
| 6 | Synthetic Slack, Google Docs and confidential GitLab issues through connector sync, plus role-based permissions enforced | Permission tests pass with zero leaks |
| 7 | Next.js chat and admin console | Full demo runs in the browser |
| 8 | Action route: MCP writes with confirmation, clarify route, then stretch goals | Actions work after user confirms |

If step 4 misses the gate, fix chunking and retrieval before adding sources; everything after builds on retrieval quality.

## Evaluation

Start with 20 questions in step 3 and grow to the full set of 90 in step 4. Rerun it after every change, so each improvement is measured rather than guessed.

| Category | Count | Example | Pass means |
| --- | --- | --- | --- |
| Handbook policy | 20 | How does paid time off work? | Correct answer, cites the right page |
| Engineering process | 15 | How do I get a merge request merged? | Steps match the handbook |
| Cross-source | 15 | Why was feature X designed this way? | Uses issues plus handbook |
| Expertise | 10 | Who should I ask about Kubernetes? | Names a plausible owner with evidence |
| Conflicting or outdated | 10 | What is the current policy on X? | Prefers the newest source, flags the conflict |
| Routing | 10 | Summarize the PTO policy and post it to #hr | Picks the right route: knowledge, action, both or clarify |
| Permissions | 5 | An HR-only question asked as an engineer | Refuses or shows nothing restricted |
| No answer exists | 5 | A made-up policy | Says it doesn't know |

**Metrics to track**

- Retrieval hit rate at 5: the right chunk is in the top 5 results
- MRR: how high the right chunk ranks
- Answer correctness and faithfulness to sources (RAGAS or an LLM judge, spot-checked by hand)
- Citation accuracy: cited passages actually support the claim
- Routing accuracy: share of messages sent to the right route
- Permission leak count: must stay at zero
- Latency: median and 95th percentile time to first token

## Stretch goals

Once the core works, each of these teaches one advanced idea:

- **Live MCP reads with per-user authentication:** fetch fresh data from tools using the asking user's own access, not the admin's
- **Knowledge graph** of people, teams, projects and documents, to answer "who owns X?" and "what depends on Y?"
- **Structured data route**: put issues (labels, assignees, states) in SQL tables and let the brain choose SQL or document search
- **Proactive digests**: a daily summary of decisions and incidents posted to Slack
- **Memory**: remember a user's team and past questions to personalise answers
- **Multimodal**: diagrams and screenshots from docs, searched with an image-aware model
- **Cost and latency tuning**: semantic caching, prompt caching, a small model for easy questions