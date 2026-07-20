"""Deterministic parsing of the source documents into JSON build artifacts.

Run once (and again only when the source documents change):

    python -m agent.parse

Produces:
    recipes.json  — one entry per drink from Classic_Espresso_Drinks.docx
    guide.json    — one entry per section from Espresso Preparation Checklist.pdf

No LLM is involved here. The documents are regular enough to parse with plain
rules, which is what guarantees the output is faithful to the source.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from docx import Document
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCX_PATH = DATA / "Classic_Espresso_Drinks.docx"
PDF_PATH = DATA / "Espresso Preparation Checklist.pdf"
RECIPES_JSON = ROOT / "recipes.json"
GUIDE_JSON = ROOT / "guide.json"


def slugify(text: str) -> str:
    """'Café Latte' -> 'cafe-latte' (ASCII, lowercase, hyphen-separated)."""
    ascii_text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _style(paragraph) -> str:
    """Normalized style name, e.g. 'Heading 1' / 'Heading1' -> 'heading1'."""
    name = paragraph.style.name if paragraph.style else ""
    return (name or "").lower().replace(" ", "")


def _is_list_item(paragraph) -> bool:
    """True for numbered/bulleted list paragraphs (by style or numbering props)."""
    if "listparagraph" in _style(paragraph):
        return True
    p_pr = paragraph._p.pPr
    return p_pr is not None and p_pr.numPr is not None


def parse_recipes(docx_path: Path = DOCX_PATH) -> list[dict]:
    """Walk the docx paragraph-by-paragraph, splitting on Heading 1 boundaries."""
    document = Document(str(docx_path))
    recipes: list[dict] = []
    current: dict | None = None
    section: str | None = None  # 'ingredients' | 'steps' | None

    def finalize(recipe: dict | None) -> None:
        if recipe is not None:
            recipes.append(recipe)

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = _style(paragraph)

        if style == "heading1":
            finalize(current)
            current = {
                "slug": slugify(text),
                "name": text,
                "serves": "",
                "tools": "",
                "description": "",
                "ingredients": [],
                "steps": [],
                "notes": "",
            }
            section = None
            continue

        if current is None:
            # Title / intro paragraphs before the first recipe — ignore.
            continue

        if style == "heading3":
            low = text.lower()
            if "ingredient" in low:
                section = "ingredients"
            elif "step" in low:
                section = "steps"
            else:
                section = None
            continue

        # "Recipe Tip:" can appear after the steps section — handle first.
        if text.lower().startswith("recipe tip"):
            current["notes"] = text
            continue

        if _is_list_item(paragraph) and section in ("ingredients", "steps"):
            current[section].append(text)
            continue

        # Non-list metadata / description (before the first Heading 3).
        if text.lower().startswith("serves"):
            current["serves"] = text[len("serves"):].strip()
        elif text.lower().startswith("tools needed"):
            current["tools"] = text.split(":", 1)[-1].strip()
        elif section is None and not current["description"]:
            current["description"] = text

    finalize(current)
    return recipes


# The prep guide's table of contents. pypdf extracts the PDF as run-together
# text with no line breaks between a heading and its body, and heading titles
# can't be told apart from body prose by capitalization alone (titles contain
# lowercase words like "grind size"). Since this is a fixed reference document,
# we declare its section list here and slice each body out of the extracted
# text between consecutive headings — so the bodies are still read from the doc,
# only the short titles are declared. build() warns if a heading goes missing
# (i.e. the source PDF changed and this list needs updating).
GUIDE_HEADINGS: list[tuple[str, str]] = [
    ("1", "Coffee Selection"),
    ("1.1", "Choosing coffee for espresso"),
    ("1.2", "Identifying the roast degree"),
    ("1.3", "Checking the roast date (resting time)"),
    ("1.4", "Checking the processing method"),
    ("2", "Dialing In Espresso"),
    ("2.1", "Setting the dose"),
    ("2.2", "Setting the brew ratio (water to coffee)"),
    ("2.3", "Setting the grind size"),
    ("2.4", "Setting the water temperature"),
    ("3", "Pulling the Shot"),
    ("3.1", "Puck preparation"),
    ("3.2", "Tracking brew time"),
    ("3.3", "Tasting and adjusting"),
    ("", "Quick Reference: Parameters by Roast Degree"),
]


def _clean_pdf_text(raw: str) -> str:
    """Normalize whitespace and repair characters pypdf couldn't decode."""
    text = raw.replace("­", "")  # soft hyphen
    text = re.sub(r"�\s*C\b", "°C", text)  # replacement char before C -> degrees
    text = text.replace("�", "•")  # remaining replacement chars were bullets
    return re.sub(r"\s+", " ", text).strip()


def _heading_regex(section: str, title: str) -> re.Pattern:
    """Match 'N[.] Title' with flexible internal whitespace."""
    number = rf"{re.escape(section)}\.?\s+" if section else ""
    title_pat = r"\s+".join(re.escape(word) for word in title.split())
    return re.compile(number + title_pat)


def parse_guide(pdf_path: Path = PDF_PATH) -> list[dict]:
    """Extract the prep guide as a flat list of {section, heading, body} entries.

    Locates each declared heading in the cleaned PDF text and slices the body
    from the text between that heading and the next one.
    """
    reader = PdfReader(str(pdf_path))
    text = _clean_pdf_text("\n".join((page.extract_text() or "") for page in reader.pages))

    # Find the (start, end) span of every heading in document order.
    spans: list[tuple[int, int, str, str]] = []
    for section, title in GUIDE_HEADINGS:
        match = _heading_regex(section, title).search(text)
        if match is None:
            print(f"  WARNING: guide heading not found in PDF: {section} {title!r}")
            continue
        spans.append((match.start(), match.end(), section, title))
    spans.sort()

    entries: list[dict] = []
    for index, (_start, end, section, title) in enumerate(spans):
        next_start = spans[index + 1][0] if index + 1 < len(spans) else len(text)
        body = text[end:next_start].strip()
        entries.append({"section": section, "heading": title, "body": body})
    return entries


def build() -> None:
    recipes = parse_recipes()
    guide = parse_guide()
    RECIPES_JSON.write_text(json.dumps(recipes, indent=2, ensure_ascii=False), encoding="utf-8")
    GUIDE_JSON.write_text(json.dumps(guide, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(recipes)} recipes -> {RECIPES_JSON.name}")
    print(f"Wrote {len(guide)} guide sections -> {GUIDE_JSON.name}")


if __name__ == "__main__":
    build()
