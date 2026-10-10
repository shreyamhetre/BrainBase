# GitMore: GitLab Company Brain — Project Plan

Oct 3, 2026 · @Shreya Mhetre

## Overview

We will build a working company brain for GitLab in 8 weeks: one chat interface that answers employee questions from the real public handbook, docs and issues, plus synthetic Slack, Notion and Jira data, with cited answers and role-based permissions.

**Problem it solves.** GitLab is a \~2,000-person remote company. Knowledge is spread across a huge handbook, thousands of issues, chat threads and meetings. People waste time searching, ask the same questions repeatedly and miss decisions. The brain gives one place to ask, with trustworthy cited answers that respect who can see what.

**What we want to learn**

- How ingestion, chunking, embeddings and indexing work end to end
- How hybrid search, reranking and citations improve answer quality
- How connectors sync live tools and map permissions
- How to route between document search and structured queries
- How an agent takes actions in tools through MCP
- How to measure quality with an evaluation set

This is a learning project: GitLab data is used as public, openly licensed content, and the app should be labelled as unofficial.

## Data plan

Start with two real sources (handbook and docs), add issues, then layer in synthetic tools that reference the real content so everything feels like one company.

| Source | Real or synthetic | How to get it | Tests |
| --- | --- | --- | --- |
| Handbook | Real | Clone the public handbook repo (Markdown) | Policies, onboarding, long docs |
| Product docs | Real | Clone the docs repo (Markdown) | Technical how-to answers |
| Issues, epics, MRs | Real | Public GitLab API, a few projects only | Discussions, decisions, freshness |
| Meeting transcripts | Real | 10 to 20 GitLab Unfiltered videos, transcribed with Whisper | Spoken, messy text |
| Slack | Synthetic | Free workspace, channels filled by an LLM script | Chat threads, informal answers |
| Notion or Google Drive | Synthetic | Free workspace with meeting notes, plans | Mixed doc types |
| Jira or Linear | Synthetic | Free project with tickets linked to real issues | Cross-tool linking |

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

The brain has two halves: an ingestion pipeline that prepares all content ahead of time, and a fast query path that runs for each question.

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
    action    → action card → user confirms → MCP write (ticket · post · page)
                (uses search results as context when the action needs them)
  → LLM answer with citations (GPT-4o mini or similar) → stream to UI
  (every step traced in Langfuse)
```

**Ingestion**

- **Sync first:** connectors fetch only new or changed content, and deleted docs are removed from the index, so stale answers don't pile up.
- **Metadata and permissions at chunk time:** each chunk carries its source, URL, date and who can see it, copied from the original doc. The permission filter checks these fields later.

**Query**

- **One entry point, router decides:** users ask in plain language; a LangGraph router picks knowledge (RAG), action (MCP) or both, e.g. "Summarize the PTO policy and post it to #hr" searches first, then acts.
- **MCP for writes only:** all reads come from the indexed, permission-tagged data. Live MCP reads are skipped for now, because admin-connected MCP servers could see more than the user is allowed to.
- **Embed the question with the same model:** after rewriting, the question is embedded with BGE-M3, the same model used for chunks, or vector search won't match properly.
- **Permission filter inside the search:** applied as a WHERE condition in the same SQL query as the search, so restricted chunks never reach the LLM.
- **Merge before reranking:** vector and keyword search return separate lists, combined with reciprocal rank fusion (RRF).
- **Rerank a fixed number:** for example, top 50 in, top 5 out.
- **LLM:** GPT-4o mini for answers; check it is still offered when starting, since small models get replaced often. Any current small, fast model works; the design doesn't depend on it.
- **Tracing:** Langfuse records every step of the query path.

The Index (Postgres) is the shared store that connects both halves.

## Tech stack

Everything below is free or has a free tier, and runs on a laptop plus one LLM API key.

| Layer | Pick | Why |  |
| --- | --- | --- | --- |
| Language | Python 3.11+ | Best RAG ecosystem |  |
| Backend API | FastAPI | Simple, async, streaming support |  |
| Parsing | Markdown parser, Docling for PDFs |
| Embeddings | BGE-M3 (1024 dims), run with sentence-transformers on the local GPU (PyTorch 2.11, CUDA 12.8) | Strong, multilingual, 8,192-token input, free to self-host | 
| Vector + keyword DB | Postgres 18 with pgvector (Docker image), plus full-text search | One database for vectors, BM25-style search, metadata and users | 
| Reranker | BGE Reranker v2-m3 | Free, fast, proven baseline | 
| LLM | Claude or any strong API model | Good at grounded answers with citations | - LLM i am planning to use Gpt 4.0 mini
| Orchestration | LangGraph | Steps as a graph with shared state, branching and retries; built for agents |
| Connectors and actions | MCP servers, connected by an admin | Standard way to give agents tools; per-user permissions still enforced at retrieval | 
| Background sync | A scheduled job (APScheduler or cron) | Incremental re-sync of sources |
| Frontend | Next.js | Real product feel, streaming chat and admin console | 
| Evaluation | RAGAS plus a custom script | RAG-specific metrics: context precision, recall, faithfulness |
| Tracing | Langfuse (self-hosted in Docker) | Every step per question: chunks, prompt, tokens, cost, latency |
- [ ]

  ## UI: inputs and outputs

The app has two screens: a chat for employees and an admin console for you to see how the brain works inside.

**Chat inputs**

- Plain-language question box, with follow-up questions in the same thread
- Role switcher (Engineer, HR, Manager, Store-level guest) to demo permissions
- Filters: source, team, date range
- Upload a file to ask questions about it
- Actions asked in plain language ("create a Jira ticket for this bug"); the router decides. Slash commands such as /ticket or /who-knows are optional shortcuts

**Chat outputs**

- Streamed answer with numbered citations that open the exact source passage
- Sources panel showing which tools contributed and how fresh each source is
- "I couldn't find this" when evidence is missing, instead of a guess
- Conflict warning when sources disagree, with the newer one preferred
- Suggested experts for the topic
- Action cards to confirm before acting: create a Jira ticket, post to Slack, draft a Notion page
- Thumbs up or down on every answer, stored for evaluation

**Admin console**

- Connectors: status, last sync time, documents per source
- Query inspector: for any question, the rewritten query, retrieved chunks with scores, reranked order and final prompt
- Permission tester: run one question as two roles and compare results
- Evaluation dashboard: accuracy and retrieval metrics per test run
- Latency breakdown: retrieval, reranking, first token, total

## Milestones

Eight weeks at roughly 8 to 10 hours a week, with one gate: core RAG must pass the evaluation set before live tools are added.

&#91;embedded content: 8-week milestones · 4 phases, 1 gate\]

If week 3 misses the gate, spend week 4 fixing chunking and retrieval instead of adding sources; everything after builds on retrieval quality.

## Evaluation

Build a set of 80 test questions in week 1 and rerun it after every change, so each improvement is measured rather than guessed.

| Category | Count | Example | Pass means |
| --- | --- | --- | --- |
| Handbook policy | 20 | How does paid time off work? | Correct answer, cites the right page |
| Engineering process | 15 | How do I get a merge request merged? | Steps match the handbook |
| Cross-source | 15 | Why was feature X designed this way? | Uses issues plus handbook |
| Expertise | 10 | Who should I ask about Kubernetes? | Names a plausible owner with evidence |
| Conflicting or outdated | 10 | What is the current policy on X? | Prefers the newest source, flags the conflict |
| Permissions | 5 | An HR-only question asked as an engineer | Refuses or shows nothing restricted |
| No answer exists | 5 | A made-up policy | Says it doesn't know |

**Metrics to track**

- Retrieval hit rate at 5: the right chunk is in the top 5 results
- MRR: how high the right chunk ranks
- Answer correctness and faithfulness to sources (Ragas or an LLM judge, spot-checked by hand)
- Citation accuracy: cited passages actually support the claim
- Permission leak count: must stay at zero
- Latency: median and 95th percentile time to first token

## Stretch goals

Once the core works, each of these teaches one advanced idea:

- **Knowledge graph** of people, teams, projects and documents, to answer "who owns X?" and "what depends on Y?"
- **Structured data route**: put Jira tickets in SQL tables and let the brain choose SQL or document search
- **Proactive digests**: a daily summary of decisions and incidents posted to Slack
- **Memory**: remember a user's team and past questions to personalise answers
- **Multimodal**: diagrams and screenshots from docs, searched with an image-aware model
- **Cost and latency tuning**: semantic caching, prompt caching, a small model for easy questions

