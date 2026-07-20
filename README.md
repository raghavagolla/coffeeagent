# coffeeagent — Coffee Recipe Lookup Agent

A small, single-purpose agent: ask for an espresso drink in plain language
("how do I make a flat white", "iced latte") and it returns the matching recipe
from a source document, cleanly formatted. If there's no match, it says so — it
**never invents a recipe**. It can also answer espresso-prep questions (grind
size, dose, brew ratio, …) from a second source document.

A scoped warm-up before a larger espresso troubleshooting assistant. See
[`PLAN.md`](PLAN.md) for the full design and rationale.

## How it works

```
query ──▶ match.py (1 LLM call: pick ONE known target, or "none")
             │
             ▼
        recipes.json / guide.json  ──▶ render.py (markdown) ──▶ answer
```

The LLM only *classifies* which recipe/guide section a query maps to. Every word
shown to the user comes from the parsed documents — the model never authors
recipe text. Parsing is plain deterministic code (`agent/parse.py`), run once to
produce `recipes.json` and `guide.json`.

## Layout

```
agent/
  parse.py    docx -> recipes.json ; pdf -> guide.json   (build step)
  match.py    the single LLM classification call (Groq default; env-swappable)
  render.py   record -> clean markdown
  core.py     answer(query) -> {kind, target, answer}
  cli.py      python -m agent.cli "..."
  api.py      FastAPI: POST /ask
data/         source documents
web/          Next.js frontend (single input -> answer page)
Dockerfile    containerizes the FastAPI backend (Render)
```

## Setup

Requires Python 3.11+ and (for the frontend) Node 18+.

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env             # then add your GROQ_API_KEY
```

Model/provider are set in `.env` (`MATCH_PROVIDER`, `MATCH_MODEL`). Default is
Groq `llama-3.3-70b-versatile` (free tier). Without an API key the matcher falls
back to a crude offline word-match stub so the CLI still runs during dev.

## Build the data (run once, and whenever the source docs change)

```bash
python -m agent.parse
# -> Wrote 10 recipes -> recipes.json
# -> Wrote 15 guide sections -> guide.json
```

## Run

**CLI**
```bash
python -m agent.cli "how do I make a flat white"
python -m agent.cli "what grind size for a dark roast?"
```

**API**
```bash
uvicorn agent.api:app --reload        # http://localhost:8000
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d "{\"query\":\"cortado\"}"
```

**Frontend**
```bash
cd web
npm install
cp .env.local.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                           # http://localhost:3000
```

## Deployment

- **Backend (FastAPI)** — build the `Dockerfile` and deploy to **Render** as a
  web service. Set `GROQ_API_KEY`, `MATCH_PROVIDER`, `MATCH_MODEL`, and
  `ALLOWED_ORIGINS` (your Vercel URL) in the Render dashboard. `recipes.json` /
  `guide.json` are baked into the image, so run `python -m agent.parse` and
  commit them before deploying.
- **Frontend (Next.js)** — deploy `web/` to **Vercel** with
  `NEXT_PUBLIC_API_URL` set to the Render backend URL.

Render (a persistent process) is chosen over serverless functions deliberately:
this v1's single classification call would be fine on serverless, but the later
troubleshooting assistant's retrieval + reasoning pipeline may need
longer-running requests, and we'd rather not re-migrate.

## Notes

- **Model choice is "for now."** The Groq free tier fits this prototype's call
  volume; production/real data shouldn't run on a free tier long-term. Claude
  (Haiku/Opus) is wired as a paid fallback — see the commented block in
  `.env.example`.
- Regenerate `recipes.json` / `guide.json` after editing anything in `data/`.
