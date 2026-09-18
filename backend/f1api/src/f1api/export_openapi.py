"""Writes the FastAPI app's OpenAPI schema to a file, for `make types`
(docs/plan/phase-1.md T8: "OpenAPI -> TS types"). `openapi-typescript`
(run from web/, see the Makefile) turns that file into Angular's API types
— this script only produces the JSON; Pydantic models are the single
source of truth (docs/f1-strategy-foundation.md §7).

Usage: uv run python -m f1api.export_openapi <output_path>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from f1api.main import app


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m f1api.export_openapi <output_path>", file=sys.stderr)
        return 2

    output_path = Path(argv[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2))
    print(f"wrote OpenAPI schema to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
