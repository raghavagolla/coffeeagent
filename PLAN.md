# Coffee Recipe Lookup Agent — v1 Design

## Overview

A small, single-purpose agent: you ask for a drink in plain language ("how do I make a flat white", "iced latte") and it returns the matching recipe from our source document, cleanly formatted. If there's no match, it says so — **it never invents a recipe.**

A small, scoped warm-up project before the larger espresso troubleshooting assistant — meant to validate the approach end-to-end on something simple first. The whole point is that it's small and easy to explain: one bounded job, no memory, no conversation state, no database, no vector search. We add retrieval/RAG properly in the next phase.

## Goals

- Parse the source document into clean, structured recipe records.
- Match a casual, natural-language request to the right recipe (handling phrasing variation like "iced latte").
- Return the recipe as readable output (ingredients + numbered steps).
- Give a clear fallback when nothing matches — never fabricate.
- Be understandable end-to-end by someone new to the codebase.

## Non-goals (v1)

Troubleshooting/diagnosis logic, multiple recipe books, shot history or pattern tracking, other brew methods, any write actions or external integrations, and vector store / embeddings. No agent framework (LangChain/LangGraph) — a single classification call doesn't justify one. All deferred to the next phase.

---

## How it works

One request flows straight through — no loops, no state:

```
  user query ("how do i make a flat white")
        │
        ▼
  ┌───────────┐   picks ONE known target      ┌──────────────┐
  │  match.py │ ────────────────────────────▶ │ recipes.json │
  │ (1 LLM    │   {kind, target} or "none"     │  guide.json  │
  │  call)    │                                └──────┬───────┘
  └───────────┘                                       │ look up target
        │                                             ▼
        │                                       ┌───────────┐
        └──────────────── "none" ──────────────▶│ render.py │  formats the
                          (fallback)             └─────┬─────┘  stored record
                                                       ▼
                                              formatted answer (markdown)
```

The important part: **the LLM only chooses *which* recipe (or "none"). It never writes the recipe text.** Every word shown to the user comes from the parsed document. That single design choice is what makes "never invent a recipe" true by construction rather than by hoping the model behaves.

The JSON files are built once, ahead of time, by parsing the documents — so at request time there's no parsing and no source ambiguity.

---

## Confirmed decisions

| Area | Decision | Why |
|---|---|---|
| **Language** | Python | Matches the AI ecosystem and the next-phase RAG work. (Not yet installed on this machine — install is step 0. Node v25 is present for the frontend.) |
| **Matching** | One constrained LLM call → known target or "none" | LLM classifies only; text always rendered from parsed records. This is the safety property. |
| **Model** | Groq `llama-3.3-70b-versatile` (free tier) by default; swappable via `MATCH_MODEL` | Matching is a simple classification call. Groq is fast and quick to set up (we've used it before), and the free tier comfortably covers this prototype's call volume. **This is a "for now" choice, not permanent** — production/real-data usage shouldn't run on a free tier long-term. Claude (Haiku/Opus) is kept as a documented paid fallback in `.env.example` for later. |
| **Interfaces** | CLI + FastAPI endpoint + minimal Next.js/React frontend | All three call one shared core function, so logic lives in one place. |
| **PDF source** | Included as a second source type ("prep guide") | See note below. |

**On the PDF:** `Espresso Preparation Checklist.pdf` turned out to be an *Espresso Preparation Guide* (coffee selection, dialing in, pulling the shot, + a roast-parameter table) — reference/how-to content, not recipes. We fold it in as a separate **"prep guide"** source the matcher can route to (e.g. "what grind size for a dark roast?"). It stays a **lookup**, not diagnosis — actual troubleshooting logic remains out of scope for v1.

---

## Source documents (verified)

**`Classic_Espresso_Drinks.docx`** — 10 recipes, and every one follows the exact same structure, which is why parsing can be plain deterministic code:

- `Heading 1` = drink name — Cappuccino, Café Latte, Flat White, Macchiato, Americano, Red Eye, Cortado, Espresso con Panna, Breve, Cubano
- `Serves 1` and `Tools Needed: …` lines (metadata)
- a description paragraph
- `Heading 3` "Ingredients" → list items
- `Heading 3` "Steps" → list items
- optional `Recipe Tip: …` paragraph → notes

**`Espresso Preparation Checklist.pdf`** — numbered sections (`1. Coffee Selection`, `2.1 Setting the dose`, … `3.3 Tasting and adjusting`) plus a "Quick Reference: Parameters by Roast Degree" table.

---

## Architecture

Everything under `coffeeagent\`:

```
coffeeagent/
  data/
    Classic_Espresso_Drinks.docx        # move existing files here
    Espresso Preparation Checklist.pdf
  agent/
    __init__.py
    parse.py        # docx -> recipes.json ; pdf -> guide.json  (build step)
    match.py        # constrained LLM matcher (the single LLM call)
    render.py       # structured record -> clean markdown
    core.py         # answer(query) -> {kind, target, answer}
    cli.py          # python -m agent.cli "how do i make a flat white"
    api.py          # FastAPI: POST /ask
  recipes.json      # generated build artifact
  guide.json        # generated build artifact
  Dockerfile        # containerizes the FastAPI backend (for Render)
  requirements.txt  # groq, python-docx, pypdf, fastapi, uvicorn, python-dotenv (+ anthropic for the paid fallback)
  .env.example      # GROQ_API_KEY=, MATCH_MODEL=llama-3.3-70b-versatile (Claude fallback documented)
  web/              # Next.js/React frontend (create-next-app)
```

`.env.example`:
```
# Matcher — Groq free tier (default for this prototype)
GROQ_API_KEY=
MATCH_PROVIDER=groq
MATCH_MODEL=llama-3.3-70b-versatile

# Paid fallback for later (Anthropic) — swap provider + model, add key:
# MATCH_PROVIDER=anthropic
# MATCH_MODEL=claude-haiku-4-5      # or claude-opus-4-8
# ANTHROPIC_API_KEY=
```

### Module responsibilities

**`parse.py`** — pure, deterministic, run once to build the JSON.
- *DOCX* via `python-docx`: walk paragraphs by style name. `Heading 1` starts a new recipe; the current `Heading 3` ("Ingredients"/"Steps") decides which bucket the following list items go into (both sections share one list style — the heading disambiguates); `Serves …` / `Tools Needed: …` become fields; other pre-Ingredients text is the description; `Recipe Tip:` becomes notes.
- *PDF* via `pypdf`: split on the numbered-heading pattern into `{section, heading, body}` entries; keep the roast table as one entry.
- Rebuild only when the source documents change — nothing parses at request time.

**`match.py`** — the single LLM call. Builds a compact catalog from the JSON — the 10 recipe names as-is, plus the guide headings — and asks the model to pick exactly one known target or "none". The model handles casual phrasing and variation itself as part of that one classification call (no hand-maintained alias map). Uses structured JSON output so the reply is guaranteed-parseable and can't drift outside the known set. Provider/model come from env (`MATCH_PROVIDER` / `MATCH_MODEL`).

**`render.py`** — pure markdown templates: `render_recipe`, `render_guide`, and `fallback`.

**`core.py`** — `answer(query)`: route → look up in JSON → render; on "none" or a miss, return the fallback. The one function CLI, API, and frontend all go through.

### Data shapes

`recipes.json` (one entry per drink):
```json
{
  "slug": "flat-white",
  "name": "Flat White",
  "serves": "1",
  "tools": "Espresso machine, milk frother",
  "description": "A silky espresso-and-steamed-milk drink…",
  "ingredients": ["2 shots espresso", "4 oz steamed milk"],
  "steps": ["Pull two shots of espresso.", "Steam milk to a fine microfoam.", "…"],
  "notes": "Recipe Tip: aim for a glossy, paint-like microfoam."
}
```

`guide.json` (one entry per section):
```json
{ "section": "2.3", "heading": "Setting the grind size", "body": "…" }
```

The matcher returns:
```json
{ "kind": "recipe" | "guide" | "none", "target": "Flat White" | null, "confidence": "high" | "low" }
```

### Interfaces
- **CLI** — `python -m agent.cli "how do i make a flat white"`, prints the answer.
- **API** — FastAPI `POST /ask` `{query}` → `{kind, target, answer}`; permissive CORS for local dev (and the deployed frontend origin); `uvicorn agent.api:app --reload`.
- **Frontend** — `web/` via `create-next-app` (App Router, TypeScript): one page, a text box + submit that POSTs to `/ask` and renders the returned markdown (`react-markdown`). Single component, no state library. API base URL from `NEXT_PUBLIC_API_URL`.

---

## Deployment

- **Backend (FastAPI)** — containerized with a `Dockerfile` and deployed to **Render** as a persistent web service. Env vars (`GROQ_API_KEY`, `MATCH_PROVIDER`, `MATCH_MODEL`) set in the Render dashboard. The generated `recipes.json` / `guide.json` are baked into the image at build time.
- **Frontend (Next.js)** — deployed to **Vercel**, pointed at the Render backend via `NEXT_PUBLIC_API_URL`. FastAPI CORS allows the Vercel origin.

**Why Render (persistent process) over serverless:** serverless Python functions (e.g. Vercel Functions) are stateless with execution-time limits. That's perfectly fine for this v1 — a single quick classification call well under any timeout. But we're deliberately choosing a persistent-process host *now* because the later troubleshooting assistant's retrieval + reasoning pipeline may need longer-running requests (and warm in-process state), and we'd rather not re-migrate the backend later.

---

## Build order

1. `parse.py` → commit `recipes.json` + `guide.json`; eyeball the output.
2. `render.py` + `core.py` with a *stub* matcher (exact-name match, no LLM) → CLI works offline.
3. `match.py` → swap the stub for the real Groq call.
4. `api.py` → expose `/ask`.
5. `web/` → thin frontend over the endpoint.
6. `Dockerfile` + deploy: backend to Render, frontend to Vercel.

Each step is independently runnable, so we can review as we go.

---

## Verification (end-to-end)

1. **Env:** Python 3.11+; `pip install -r requirements.txt`; set `GROQ_API_KEY` in `.env`.
2. **Parsing:** `python -m agent.parse` → 10 recipe records (non-empty ingredients + steps) and the guide sections + roast table. Spot-check Flat White and Cubano.
3. **CLI matching:**
   - `"how do I make a flat white"` → Flat White recipe, verbatim.
   - `"iced latte"` → Café Latte, text unchanged (not paraphrased).
   - `"what grind size for a dark roast?"` → PDF grind-size / roast-table section.
   - `"pumpkin spice frappuccino?"` → fallback, no invented recipe.
4. **API:** `POST /ask {"query":"cortado"}` → the Cortado recipe.
5. **Frontend:** `npm run dev`; submit "flat white" and a nonsense drink; recipe renders, fallback shows for the miss.
6. **Deploy smoke test:** hit the Render URL's `/ask` and load the Vercel frontend end-to-end.

---

## Open questions for the reviewer

1. **Keep the PDF in v1?** It stretches "recipe lookup" toward prep-reference. Fine as a second source, or hold it for the troubleshooting phase?
2. **Frontend scope:** is a single input→answer page the right size, or do we want recipe browsing / a list view too?
3. **Anything here that feels over-built for a warm-up?**

---

## Out of scope / next phase

Troubleshooting & diagnosis logic, multiple source documents, shot history / pattern tracking, other brew methods, write actions & external integrations, and the vector store / embeddings + RAG retrieval that the larger assistant will need.
