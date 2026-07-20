"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EXAMPLES = ["flat white", "iced latte", "what grind size for a dark roast?"];

export default function Home() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    setAnswer("");
    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmed }),
      });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      setAnswer(data.answer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>☕ Coffee Recipe Lookup</h1>
      <p className="subtitle">
        Ask for a classic espresso drink, or an espresso prep tip.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(query);
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. how do I make a flat white"
          aria-label="Your question"
        />
        <button type="submit" disabled={loading}>
          {loading ? "…" : "Ask"}
        </button>
      </form>

      <p className="hint">
        Try:{" "}
        {EXAMPLES.map((ex, i) => (
          <span key={ex}>
            {i > 0 && " · "}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                setQuery(ex);
                ask(ex);
              }}
            >
              {ex}
            </a>
          </span>
        ))}
      </p>

      {error && <p style={{ color: "#b3402b" }}>{error}</p>}
      {answer && (
        <div className="answer">
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      )}
    </main>
  );
}
