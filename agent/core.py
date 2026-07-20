"""Orchestration shared by the CLI, the API, and (via the API) the frontend.

answer(query) is the single entry point:
    route the query -> look the target up in the parsed JSON -> render it,
    or return the fallback when nothing matches.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import match, render

ROOT = Path(__file__).resolve().parent.parent
RECIPES_JSON = ROOT / "recipes.json"
GUIDE_JSON = ROOT / "guide.json"


@lru_cache(maxsize=1)
def _load() -> tuple[list[dict], list[dict]]:
    if not RECIPES_JSON.exists() or not GUIDE_JSON.exists():
        raise FileNotFoundError(
            "recipes.json / guide.json not found — run `python -m agent.parse` first."
        )
    recipes = json.loads(RECIPES_JSON.read_text(encoding="utf-8"))
    guide = json.loads(GUIDE_JSON.read_text(encoding="utf-8"))
    return recipes, guide


def answer(query: str) -> dict:
    """Return {kind, target, answer} for a natural-language query."""
    recipes, guide = _load()
    recipe_names = [r["name"] for r in recipes]
    guide_headings = [g["heading"] for g in guide]

    if not query or not query.strip():
        return {"kind": "none", "target": None, "answer": render.fallback(recipe_names)}

    result = match.route(query.strip(), recipe_names, guide_headings)
    kind, target = result["kind"], result["target"]

    if kind == "recipe":
        recipe = next((r for r in recipes if r["name"] == target), None)
        if recipe:
            return {"kind": "recipe", "target": target, "answer": render.render_recipe(recipe)}

    if kind == "guide":
        entry = next((g for g in guide if g["heading"] == target), None)
        if entry:
            return {"kind": "guide", "target": target, "answer": render.render_guide(entry)}

    return {"kind": "none", "target": None, "answer": render.fallback(recipe_names)}
