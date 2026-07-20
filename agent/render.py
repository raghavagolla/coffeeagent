"""Pure functions that turn a parsed record into clean markdown.

These never call an LLM and never invent content — every line comes from the
stored record. Keeping rendering separate from matching is what lets us
guarantee the output is faithful to the source document.
"""
from __future__ import annotations


def render_recipe(recipe: dict) -> str:
    lines: list[str] = [f"# {recipe['name']}"]

    meta = []
    if recipe.get("serves"):
        meta.append(f"Serves {recipe['serves']}")
    if recipe.get("tools"):
        meta.append(f"Tools: {recipe['tools']}")
    if meta:
        lines.append(f"_{' · '.join(meta)}_")

    if recipe.get("description"):
        lines.append("")
        lines.append(recipe["description"])

    if recipe.get("ingredients"):
        lines.append("")
        lines.append("**Ingredients**")
        lines.extend(f"- {item}" for item in recipe["ingredients"])

    if recipe.get("steps"):
        lines.append("")
        lines.append("**Steps**")
        lines.extend(f"{i}. {step}" for i, step in enumerate(recipe["steps"], start=1))

    if recipe.get("notes"):
        lines.append("")
        lines.append(f"> {recipe['notes']}")

    return "\n".join(lines).strip()


def render_guide(entry: dict) -> str:
    section = f"{entry['section']} " if entry.get("section") else ""
    heading = f"## {section}{entry['heading']}".strip()

    body = entry.get("body", "").strip()
    # Turn inline "• " bullets into markdown list items for readability.
    if "•" in body:
        head, *bullets = body.split("•")
        parts = [head.strip()] + [f"- {b.strip()}" for b in bullets if b.strip()]
        body = "\n".join(p for p in parts if p)

    return f"{heading}\n\n{body}".strip()


def fallback(recipe_names: list[str]) -> str:
    names = ", ".join(recipe_names)
    return (
        "I don't have a recipe for that.\n\n"
        f"**I can help with these drinks:** {names}.\n\n"
        "I can also answer espresso prep questions — dose, grind size, brew ratio, "
        "water temperature, resting time, and tasting/adjusting."
    )
