# FinSight — Presentation Speaker Script

*Use this alongside FinSight_Presentation.pptx. Each section corresponds to one slide. Speak naturally — this is a guide, not a script to memorize word-for-word.*

---

## Opening / Self-Introduction (before Slide 1, or while Slide 1 is up)

> Good morning/afternoon everyone. My name is **Yashasvi Singh**, registration number **12319052**, and today I'll be presenting my project, **FinSight — an AI-powered personal finance advisor**.
>
> In short, FinSight lets a user upload their bank statement as a CSV file and then simply *chat* with it in plain English — asking things like "how much did I spend on food last month" or "why did my spending go up in June" — and get back a real, data-backed answer instead of just a chart to interpret themselves.
>
> Over the next few minutes I'll walk through the problem this solves, how the system is architected, the core tools that power it, some of the key design decisions I made and why, and I'll also be upfront about its current limitations. Let's begin.

---

## Slide 1 — Title

> This is FinSight — an AI-powered personal finance advisor, built as a full-stack LLM agent application. The stack, at a glance, is LangGraph for agent orchestration, FastAPI for the backend, Streamlit for the frontend, SQLite for storage, and Gemini as the underlying LLM.

---

## Slide 2 — Agenda

> Here's how I'll structure the talk. I'll start with the problem and the solution, then move into the system architecture and data layer, walk through the four core tools in detail, explain the agent design and the key design decisions behind it, cover testing and deployment, be honest about limitations and what's next, and close with a quick anticipated-questions recap.

---

## Slide 3 — The Problem

> Most personal finance apps stop at a dashboard — a bar chart, a pie chart — and leave all the *interpretation* to the user. If I see I spent ₹18,000 on food, that chart alone doesn't tell me whether that's normal for me, what changed, or what I should do about it.
>
> There are really three problems I wanted to solve:
> First, dashboards give numbers but not answers.
> Second, if you just throw raw LLMs like GPT-4o at financial data, they tend to hallucinate figures — they'll confidently state a number that's simply wrong.
> And third, real bank statement CSVs are genuinely messy — different banks export data in six or more different column formats, with different date styles, and no common standard.
>
> FinSight is built to answer that very real question: *"Why did I overspend in June?"* — with an actual grounded answer.

---

## Slide 4 — Solution Overview

> So, in one sentence: FinSight is a full-stack LLM agent that lets a user upload a bank statement CSV and chat in plain English — and critically, every number in every answer comes from deterministic Python tools, never from the LLM's imagination.
>
> The flow is simple: the user uploads their CSV, it gets parsed and stored in SQLite, they ask a question, the agent reasons about which tool to call, and it returns a grounded answer streamed back into the chat.

---

## Slide 5 — Six Core Features

> FinSight has six core capabilities. A spend analyser that gives a category-level breakdown with percentage share for any date range. A month-over-month comparison tool. An anomaly detector that uses Z-score analysis to flag statistically unusual transactions. A budget planner that generates a personalised saving plan. A flexible CSV parser that auto-detects columns regardless of format. And a streaming chat interface with per-session conversation memory.

---

## Slide 6 — System Architecture

> Here's how everything connects. The Streamlit frontend on port 8501 talks to the FastAPI backend on port 8000 over HTTP, using server-sent-event style streaming for the chat responses.
>
> The backend exposes three routes: POST /upload, which parses the CSV and loads it into SQLite; POST /chat, which streams the agent's response; and GET /health, a liveness probe.
>
> At the core is a LangGraph `create_react_agent`, running on Gemini 3.1 Flash-Lite, with a MemorySaver checkpointer for conversation memory, and access to the four tools I mentioned. The data itself lives in SQLite, in a single Transaction table, and the whole thing is containerized with Docker Compose for deployment to Render.
>
> The key design principle I want to highlight here: the LLM's job is only intent recognition, tool routing, and synthesizing a natural-language response. All the actual arithmetic happens in plain, deterministic Python.

---

## Slide 7 — Tech Stack

> Quickly on the tech stack: FastAPI for the async backend, Streamlit for the UI, LangGraph for orchestration, Gemini 3.1 Flash-Lite as the LLM, SQLAlchemy over SQLite for persistence, pandas and numpy for the actual data crunching inside the tools, and Docker Compose plus Render for deployment.
>
> One thing I want to flag proactively: the project's README documentation mentions GPT-4o and a LangChain AgentExecutor — but if you look at the actual `agent.py` code, it's actually using Gemini via LangGraph's `create_react_agent`. This is a case of the documentation drifting from the implementation over the course of development, and I think it's important to always verify against the source code rather than the docs.

---

## Slide 8 — The Transaction Model

> The entire data layer really comes down to one table: `Transaction`. It has an id, a `session_id` that scopes every row to a particular upload, a date, a description, a signed amount — negative for debit, positive for credit — and a category.
>
> The `session_id` is doing a lot of work here. Every time someone uploads a file, they get a fresh UUID session, and every single query in every tool filters `WHERE session_id = X`. That means one SQLite database file can safely isolate many different users' data without needing a full login system.
>
> And if someone re-uploads a corrected statement, `load_csv()` first deletes all existing rows for that session before inserting the new ones — so re-uploads replace data rather than duplicating it.

---

## Slide 9 — CSV Parsing Pipeline

> This was honestly the hardest part of the project, because real bank statements are inconsistent. The `load_csv()` function goes through six steps: it normalizes headers to lowercase with underscores, finds the date column by looking for any header containing "date", resolves the amount — either from a direct amount column or by computing credit minus debit — resolves the description from any of several possible column names, infers the category either from an explicit column or by keyword matching against eight categories, defaulting to "Other" if nothing matches, and finally inserts everything with per-row error handling so one bad row doesn't kill the whole upload.

---

## Slide 10 — Tool 1 & 2: Spend Analyser and MoM Compare

> Let's go into the tools themselves, starting with the first two.
>
> `spend_analyser` takes an optional start and end date, filters for negative amounts — meaning debits — groups by category, sums them, and computes each category's percentage of the total. It's what fires when someone asks "how much did I spend on X" or "where's my money going."
>
> `mom_compare` takes two months in YYYY-MM format, computes the total per category for each, and reports the direction and percentage change. This is what answers "am I spending more this month" or "what changed."
>
> You can see in the example on screen — shopping went from about ₹4,900 to ₹19,900, a 306% increase — and that jump is exactly the kind of thing the anomaly detector and this comparison tool are designed to surface clearly.

---

## Slide 11 — Tool 3 & 4: Anomaly Detector and Budget Planner

> The third tool is the anomaly detector, and this is probably the most interesting one from a design standpoint. It computes a Z-score for each transaction — that's (value minus the category mean) divided by the category standard deviation — computed *within each category*, not globally. Any transaction with a Z-score of 2.0 or above gets flagged, up to the top 5 by default. There's a guard clause too: it requires at least 5 transactions in a category before running, and it handles the case where standard deviation is zero safely.
>
> In the example shown, a ₹6,700 Amazon purchase gets flagged with Z equals 2.8 — not because ₹6,700 is a huge amount in absolute terms, but because this particular user's typical Amazon transaction is around ₹1,000, so this one stands out relative to their own pattern.
>
> The fourth tool, budget planner, takes a lookback window and a saving-goal percentage, computes the average monthly spend per category, and proportionally trims each category to hit that saving target. If income data isn't available, it falls back to applying the saving percentage directly to spend.

---

## Slide 12 — Agent Design

> Now, how does the agent actually get built and how does it route between these tools? The `build_agent` function does five things: it instantiates a `ChatGoogleGenerativeAI` model — Gemini 3.1 Flash-Lite, temperature 0.2, thinking budget set to zero — it instantiates all four tools bound to the current session, sets up a `MemorySaver` checkpointer for per-thread conversation state, wires everything together with LangGraph's `create_react_agent`, and rebuilds fresh on every upload.
>
> On the right, you can see the core rules baked into the system prompt: always use a tool before answering — never invent numbers — be concise but warm, format currency consistently in rupees, suggest one concrete action when a problem is detected, acknowledge new uploads, and redirect off-topic questions back to finance.

---

## Slide 13 — Two Design Decisions Worth Defending

> I want to spend a moment on two design decisions I think are worth explaining in more depth, because they're the ones most likely to come up in questions.
>
> First: why an agent with tools, instead of a RAG — retrieval-augmented-generation — approach where I'd embed transactions and retrieve by similarity? My reasoning is that financial analysis is fundamentally structured and deterministic. "How much did I spend on food in May" has exactly one correct answer, and a `GROUP BY` query beats embedding similarity search every time for that kind of question. RAG is great for unstructured document retrieval, but transactions are structured rows, not prose — so matching the strategy to the data type mattered more to me than following the more fashionable RAG trend.
>
> Second: why Z-score instead of something like a fixed 90th-percentile threshold, or a more sophisticated method like Isolation Forest? A fixed percentile would just flag every high-value spend, even routine ones like rent. Isolation Forest is a legitimate machine learning approach, but it's overkill for this data volume and much harder to explain to an end user. Z-score per category is interpretable, computationally cheap, and statistically well-grounded — which is why I chose it.

---

## Slide 14 — Endpoints & Streaming

> On the API side, there are three endpoints: GET /health for liveness checks, POST /upload which parses the CSV and rebuilds the agent for that session, and POST /chat, which streams the response back.
>
> The streaming itself works through `agent.astream(..., stream_mode="messages")`, which actually emits output from every node in the LangGraph — including the tool-call and tool-result events. My generator specifically filters to only yield chunks where the LangGraph node is "agent", so the end user only ever sees natural language tokens, not raw tool JSON leaking into the chat.
>
> I'll also be upfront that CORS is currently wide open — fine for a demo, but it would need to be locked down for any real production, multi-tenant deployment.

---

## Slide 15 — Testing Strategy

> For testing, I have a pytest suite covering all four tools plus the CSV loader — testing things like correct breakdown output, income exclusion, date filtering behaviour on empty databases, direction arrows and deltas in the month comparison, threshold and top-n behaviour in the anomaly detector, and category inference in the CSV loader.
>
> All of these tests use a mocked SQLAlchemy session, so they don't need a real database or API key — which makes them fast and CI-friendly.
>
> I do want to flag a gap here rather than hide it: I don't currently have tests covering the agent orchestration layer or the FastAPI routes directly. The tool logic itself is well unit-tested, but true end-to-end routing and streaming behaviour is not — that's an honest limitation of the current test suite.

---

## Slide 16 — Deployment

> For deployment, there are three supported paths. Locally, it's a standard venv plus pip install, running uvicorn and Streamlit in two separate terminals. With Docker Compose, `docker compose up --build` spins up both services identically across Linux and Windows. And for cloud deployment, there's a `render.yaml` blueprint that deploys the backend and the Streamlit UI as two managed services on Render.com.

---

## Slide 17 — Limitations & Roadmap

> I want to be transparent about the current limitations. Keyword-based category inference will miss some edge cases — for instance, "Blinkit" isn't in the food keyword list currently, so it falls into "Other." The tools don't share context with each other — each call independently re-reads the session's data. The in-memory agent cache is lost on server restart. There's no authentication on the API yet, and CORS is wide open by default. And right now it's CSV-only, with no PDF statement support.
>
> On the roadmap: PostgreSQL support for real multi-tenant deployments, Redis-backed session persistence, embedding-based category inference to handle those edge cases better, multi-turn tool memory, PDF statement parsing, and proper API authentication.

---

## Slide 18 & 19 — Viva Prep Q&A

> I've also put together some questions I anticipated being asked, along with my answers — I'll leave these up briefly rather than reading through all eight, but I'm happy to take questions on any of these, or anything else about the project, right now.

*(These two slides are your safety net — if the panel asks something close to one of these eight, you already have a tight, prepared answer memorized from earlier practice. No need to narrate them line by line unless specifically asked.)*

---

## Slide 20 — Thank You / Demo

> That covers the full design of FinSight — from the problem it solves, through the architecture, the tools, the key design decisions, and its current limitations. I'd now like to move into a quick live demo, and then I'm happy to take any questions. Thank you.

---

## Quick-Reference: If You Get Cornered

- **"Why not just use ChatGPT directly?"** → No grounding — it would hallucinate numbers. FinSight's tools guarantee every figure traces back to a deterministic calculation on the user's actual data.
- **"What's the biggest weakness of this project?"** → Be honest: no auth on the API, no tests on the agent/routing layer, and category inference is keyword-based rather than ML-based. Then pivot to the roadmap slide to show you've already thought about fixing it.
- **"Could this scale to production?"** → SQLite and the in-memory agent cache are the two things that would need to change first — Postgres and Redis are already on the roadmap for exactly that reason.
- **If you don't know something** → It's fine to say "That's not something I optimized for in this version, but here's how I'd approach it" — panels respond well to honest, reasoned answers over guessing.
