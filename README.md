# coffeeagent

1. Problem Statement
Baristas and home users often need quick, accurate access to a specific drink recipe (ingredients, ratios, steps) without manually searching through a document or binder. The goal is a lightweight agent that takes a plain-language request (e.g. "how do I make a flat white") and returns the correct recipe pulled directly from a source document — nothing more.
This is intentionally scoped small: one document, one function (recipe lookup and retrieval), no write actions, no external integrations. It exists to demonstrate an end-to-end agent build — from scoping through deployment — using a real, bounded use case.

3. Objective
•	Given a user's request naming a drink, the agent finds the matching recipe in the source document and returns it clearly formatted.
•	If the drink isn't in the document, the agent says so rather than inventing a recipe.
•	No memory, no state, no external APIs — a single-turn lookup-and-respond tool.

5. Scope
In Scope
•	Ingesting one static recipe document (Word/PDF/Markdown) as the single source of truth.
•	Parsing the document into structured recipe records (drink name, ingredients, ratios, steps, notes).
•	Matching a user's natural-language request to the closest recipe name (handles casual phrasing, e.g. "iced latte" → "Iced Caffè Latte").
•	Returning the recipe in a clean, readable format (ingredients list + numbered steps).
•	Basic fallback response when no matching recipe exists.
