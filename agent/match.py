"""The single classification call: map a natural-language query to one known
target (a recipe name or a guide heading) or 'none'.

The LLM only *classifies* — it never writes recipe or guide text. The model,
provider, and key come from the environment:

    MATCH_PROVIDER = groq (default) | anthropic
    MATCH_MODEL    = llama-3.3-70b-versatile (default) | claude-haiku-4-5 | ...
    GROQ_API_KEY / ANTHROPIC_API_KEY

If no key is configured, we fall back to a deterministic offline stub so the
CLI still works during development.
"""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv

load_dotenv()

_KINDS = {"recipe", "guide", "none"}

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["recipe", "guide", "none"]},
        "target": {"type": ["string", "null"]},
        "confidence": {"type": "string", "enum": ["high", "low"]},
    },
    "required": ["kind", "target", "confidence"],
    "additionalProperties": False,
}


def _system_prompt(recipe_names: list[str], guide_headings: list[str]) -> str:
    recipes = "\n".join(f"- {n}" for n in recipe_names)
    guide = "\n".join(f"- {h}" for h in guide_headings)
    return (
        "You are a router for a coffee lookup tool. Map the user's request to "
        "exactly ONE item from the catalogs below, or to 'none'. You never answer "
        "the question or write any recipe or instructions — you only classify.\n\n"
        f"RECIPES:\n{recipes}\n\n"
        f"GUIDE TOPICS:\n{guide}\n\n"
        "Rules:\n"
        "- If the request names or describes one of the drinks (including casual "
        "phrasing, e.g. 'iced latte' -> 'Café Latte'), return kind='recipe' and "
        "target set to the exact recipe name.\n"
        "- If it asks about espresso preparation or dialing in (dose, grind, brew "
        "ratio, water temperature, roast, resting time, tasting), return "
        "kind='guide' and target set to the exact guide topic heading.\n"
        "- Otherwise return kind='none' and target=null.\n"
        "- target MUST be copied verbatim from one of the lists above, or null.\n"
        'Respond with ONLY a JSON object: {"kind": ..., "target": ..., "confidence": "high"|"low"}.'
    )


def _coerce(raw: dict, recipe_names: list[str], guide_headings: list[str]) -> dict:
    """Validate the model output and force it back into the known set."""
    kind = raw.get("kind")
    target = raw.get("target")
    confidence = raw.get("confidence", "low")
    if kind not in _KINDS:
        return {"kind": "none", "target": None, "confidence": "low"}

    if kind == "recipe":
        match = next((n for n in recipe_names if n.lower() == str(target).lower()), None)
        if match is None:
            return {"kind": "none", "target": None, "confidence": "low"}
        return {"kind": "recipe", "target": match, "confidence": confidence}

    if kind == "guide":
        match = next((h for h in guide_headings if h.lower() == str(target).lower()), None)
        if match is None:
            return {"kind": "none", "target": None, "confidence": "low"}
        return {"kind": "guide", "target": match, "confidence": confidence}

    return {"kind": "none", "target": None, "confidence": confidence}


def _route_groq(query: str, system: str, model: str) -> dict:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def _route_anthropic(query: str, system: str, model: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": query}],
        output_config={"format": {"type": "json_schema", "schema": ROUTE_SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def _route_stub(query: str, recipe_names: list[str], guide_headings: list[str]) -> dict:
    """Offline, no-LLM fallback: crude word-overlap match for local dev."""
    q = query.lower()
    for name in recipe_names:
        words = [w for w in name.lower().replace("-", " ").split() if len(w) > 2]
        if any(w in q for w in words):
            return {"kind": "recipe", "target": name, "confidence": "low"}
    for heading in guide_headings:
        words = [w for w in heading.lower().split() if len(w) > 3]
        if sum(w in q for w in words) >= 2:
            return {"kind": "guide", "target": heading, "confidence": "low"}
    return {"kind": "none", "target": None, "confidence": "low"}


def route(query: str, recipe_names: list[str], guide_headings: list[str]) -> dict:
    """Return {kind, target, confidence}. Never raises for a normal query."""
    provider = os.environ.get("MATCH_PROVIDER", "groq").lower()
    system = _system_prompt(recipe_names, guide_headings)

    try:
        if provider == "groq" and os.environ.get("GROQ_API_KEY"):
            model = os.environ.get("MATCH_MODEL", "llama-3.3-70b-versatile")
            raw = _route_groq(query, system, model)
        elif provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            model = os.environ.get("MATCH_MODEL", "claude-haiku-4-5")
            raw = _route_anthropic(query, system, model)
        else:
            return _route_stub(query, recipe_names, guide_headings)
    except Exception as exc:  # network/key/parse issues -> degrade, don't crash
        print(f"[match] provider '{provider}' failed ({exc}); using offline stub.")
        return _route_stub(query, recipe_names, guide_headings)

    return _coerce(raw, recipe_names, guide_headings)
