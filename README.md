# ☕ coffeeagent — Coffee Recipe Lookup Agent

Ask for an espresso drink in plain language ("how do I make a flat white",
"iced latte") and get the matching recipe from a source document, cleanly
formatted. If there's no match, it says so — it **never invents a recipe**. It
also answers espresso‑prep questions (grind size, dose, brew ratio, water
temperature, …) from a second source document.

A scoped warm‑up before a larger espresso troubleshooting assistant. Full design
rationale lives in [`PLAN.md`](PLAN.md).

---

## Table of contents

1. [What's in this branch](#whats-in-this-branch)
2. [How it works](#how-it-works)
3. [Project structure](#project-structure)
4. [Prerequisites](#prerequisites)
5. [Backend — setup & run](#backend--setup--run)
6. [Frontend — setup & run](#frontend--setup--run)
7. [Environment variables](#environment-variables)
8. [Usage examples](#usage-examples)
9. [Regenerating the data](#regenerating-the-data)
10. [Deployment](#deployment)
11. [Troubleshooting](#troubleshooting)
12. [Design notes](#design-notes)

---

## What's in this branch

Branch: `feature/recipe-lookup-agent`. This branch adds the entire v1 build:

- **Deterministic parser** (`agent/parse.py`) that turns the two source
  documents in `data/` into JSON build artifacts (`recipes.json`, `guide.json`).
- **Single‑LLM matcher** (`agent/match.py`) — one constrained classification
  call that maps a query to a known recipe / guide section or "none". Groq by
  default, Anthropic as a paid fallback, plus an offline stub.
- **Pure renderers** (`agent/render.py`) and an **orchestrator**
  (`agent/core.py`) shared by every interface.
- **Three interfaces:** CLI (`agent/cli.py`), FastAPI (`agent/api.py`), and a
  Next.js frontend (`web/`).
- **Deployment scaffolding:** `Dockerfile` (backend → Render), frontend → Vercel.
- Config: `requirements.txt`, `.env.example`, `.gitignore`, `web/` project.
- Source docs moved from the repo root into `data/`.

---

## How it works

```
   query ("how do I make a flat white")
     │
     ▼
  match.py ── one LLM call: pick ONE known target, or "none" ──┐
     │                                                          │
     │  {kind: "recipe"|"guide"|"none", target, confidence}     │
     ▼                                                          ▼
  core.py ── look target up in ──▶ recipes.json / guide.json ──▶ render.py ──▶ markdown answer
     │
     └── "none" / not found ─────────────────────────────────▶ fallback message
```

**The safety property:** the LLM only *classifies* which recipe/section a query
maps to. Every word shown to the user is rendered from the parsed JSON — the
model never authors recipe text, so it cannot fabricate a recipe. Parsing is
plain deterministic code, run once to build the JSON.

---

## Project structure

```
coffeeagent/
├── agent/                 # Python backend package
│   ├── parse.py           #   docx -> recipes.json ; pdf -> guide.json  (build step)
│   ├── match.py           #   the single LLM classification call (env-swappable)
│   ├── render.py          #   record -> clean markdown (pure, no LLM)
│   ├── core.py            #   answer(query) -> {kind, target, answer}
│   ├── cli.py             #   python -m agent.cli "..."
│   └── api.py             #   FastAPI app: POST /ask, GET /healthz
├── data/                  # source documents (inputs to the parser)
│   ├── Classic_Espresso_Drinks.docx
│   └── Espresso Preparation Checklist.pdf
├── web/                   # Next.js frontend (App Router, TypeScript)
│   ├── app/               #   layout.tsx, page.tsx, globals.css
│   ├── package.json
│   └── .env.local.example
├── recipes.json           # generated artifact (committed; baked into Docker image)
├── guide.json             # generated artifact (committed)
├── Dockerfile             # containerizes the FastAPI backend (Render)
├── requirements.txt
├── .env.example
├── PLAN.md                # design document
└── README.md              # this file
```

---

## Prerequisites

- **Python 3.11+** (developed on 3.12). On Windows the `py` launcher is used below.
- **Node.js 18+** and npm (for the frontend).
- A **Groq API key** (free tier) for live matching — get one at
  <https://console.groq.com>. Without it, the matcher runs on an offline stub.

---

## Backend — setup & run

> **All backend commands run from the `coffeeagent` folder** (the one containing
> the `agent/` package). Running from the parent `coffee/` folder causes
> `ModuleNotFoundError: No module named 'agent'`.

### 1. Create and activate a virtual environment

From the repo root (the `coffeeagent` folder, which contains `agent/`):

**Windows (PowerShell):**
```powershell
cd coffeeagent
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
cd coffeeagent
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```powershell
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
```

Open `.env` and paste your key into `GROQ_API_KEY=`. (See
[Environment variables](#environment-variables).)

### 4. Build the data (once, and after any change to files in `data/`)

```bash
python -m agent.parse
```
Expected output:
```
Wrote 10 recipes -> recipes.json
Wrote 15 guide sections -> guide.json
```

### 5. Run

**CLI:**
```bash
python -m agent.cli "how do I make a flat white"
```

**API server:**
```bash
uvicorn agent.api:app --reload
```
Serves on <http://localhost:8000>. Check <http://localhost:8000/healthz> → `{"status":"ok"}`.
Interactive API docs: <http://localhost:8000/docs>.

---

## Frontend — setup & run

> Frontend commands run from the **`web/`** folder.

From the `web/` folder (inside `coffeeagent`):
```powershell
cd web
npm install
copy .env.local.example .env.local      # Windows  (cp on macOS/Linux)
npm run dev
```

Open <http://localhost:3000>. Type a drink (or click an example) and submit.

`.env.local` sets `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).
The backend must be running for the frontend to return answers.

To verify a production build:
```bash
npm run build
```

---

## Environment variables

### Backend (`coffeeagent/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | Groq API key. If unset, the matcher uses the offline stub. |
| `MATCH_PROVIDER` | `groq` | `groq` or `anthropic`. |
| `MATCH_MODEL` | `llama-3.3-70b-versatile` | Model id for the chosen provider. |
| `ANTHROPIC_API_KEY` | — | Only needed when `MATCH_PROVIDER=anthropic`. |
| `ALLOWED_ORIGINS` | `*` | Comma‑separated CORS origins. Set to the frontend URL in production. |

**Switching to the paid Anthropic fallback** — in `.env`:
```
MATCH_PROVIDER=anthropic
MATCH_MODEL=claude-haiku-4-5      # or claude-opus-4-8
ANTHROPIC_API_KEY=sk-ant-...
```

### Frontend (`coffeeagent/web/.env.local`)

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the FastAPI backend. |

> `.env` and `.env.local` are git‑ignored — only the `.example` templates are committed. Never commit real keys.

---

## Usage examples

**CLI:**
```bash
python -m agent.cli "iced latte"
python -m agent.cli "what grind size for a dark roast?"
python -m agent.cli "pumpkin spice frappuccino"     # -> fallback, no invented recipe
```

**API (curl):**
```bash
curl -X POST http://localhost:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"cortado\"}"
```
Response shape:
```json
{ "kind": "recipe", "target": "Cortado", "answer": "# Cortado\n_Serves 1 ..." }
```
`kind` is one of `recipe` | `guide` | `none`; `answer` is markdown.

**Expected routing:**

| Query | Result |
|---|---|
| `how do I make a flat white` | Flat White recipe |
| `iced latte` | Café Latte (phrasing handled) |
| `what grind size for a dark roast?` | Prep guide §2.3 (from the PDF) |
| `pumpkin spice frappuccino` | Fallback — not in the source, no fabrication |

---

## Regenerating the data

The parser is the only thing that reads the source documents. Re‑run it whenever
you edit anything in `data/`, then commit the updated JSON:

```bash
python -m agent.parse
git add recipes.json guide.json
```

`recipes.json` / `guide.json` are intentionally committed because the Docker
image copies them in at build time (the container does not parse at runtime).

---

## Deployment

### Backend → Render (Docker)

1. Ensure `recipes.json` / `guide.json` are generated and committed.
2. Create a **Web Service** on Render from this repo, using the `Dockerfile`.
3. Set environment variables in the Render dashboard: `GROQ_API_KEY`,
   `MATCH_PROVIDER`, `MATCH_MODEL`, and `ALLOWED_ORIGINS` (your Vercel URL).
4. Render provides `$PORT`; the container already binds to it.

Local Docker sanity check:
```bash
docker build -t coffeeagent .
docker run -p 8000:8000 --env-file .env coffeeagent
```

### Frontend → Vercel

1. Import the repo into Vercel with the **root directory set to `web/`**.
2. Set `NEXT_PUBLIC_API_URL` to the Render backend URL.
3. Deploy (Next.js is auto‑detected).

**Why Render (a persistent process) over serverless functions:** this v1's single
classification call would be fine on serverless, but the later troubleshooting
assistant's retrieval + reasoning pipeline may need longer‑running requests, and
we'd rather not re‑migrate the backend later.

---

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `ModuleNotFoundError: No module named 'agent'` | You're in the wrong folder. `cd` into `coffeeagent` (the folder with `agent/`) before running `uvicorn`/`python -m agent...`. |
| `FileNotFoundError: recipes.json / guide.json not found` | Run `python -m agent.parse` first. |
| Console log `[match] provider 'groq' failed ...; using offline stub.` | Missing/invalid `GROQ_API_KEY`, or no network — matching fell back to the crude offline stub. Set a valid key in `.env`. |
| Matches feel too literal / only exact words work | You're on the offline stub (no key). Add `GROQ_API_KEY` for real phrasing handling. |
| Frontend loads but every query errors | Backend not running, or `NEXT_PUBLIC_API_URL` wrong. Start `uvicorn` and check the URL in `web/.env.local`. |
| CORS error in the browser console | Set `ALLOWED_ORIGINS` on the backend to include the frontend origin. |
| `Activate.ps1 cannot be loaded` (PowerShell) | Run `Set-ExecutionPolicy -Scope Process RemoteSigned` in that terminal, then activate again. |
| Non‑ASCII shows as `�` in the terminal | Windows console display only — the JSON/API responses are correct UTF‑8. |

---

## Design notes

- **Model choice is "for now."** The Groq free tier fits this prototype's call
  volume; production/real data shouldn't run on a free tier long‑term. Anthropic
  (Haiku/Opus) is wired as a paid fallback via env vars.
- **No agent framework.** A single classification call doesn't justify
  LangChain/LangGraph, and there's no vector store — that arrives in the next
  phase (the larger troubleshooting assistant).
- **The guide (PDF) is a lookup, not diagnosis.** It's a second source type the
  matcher can route to; actual troubleshooting logic is out of scope for v1.
