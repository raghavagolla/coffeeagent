"""Command-line entry point.

    python -m agent.cli "how do I make a flat white"
"""
from __future__ import annotations

import sys

from .core import answer


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print('Usage: python -m agent.cli "how do I make a flat white"')
        return 1
    query = " ".join(args)
    print(answer(query)["answer"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
