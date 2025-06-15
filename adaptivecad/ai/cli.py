"""CLI entrypoint for AI-powered geometry generation."""

from __future__ import annotations

import argparse

from adaptivecad.ai.openai_bridge import call_openai
from adaptivecad.ai.translator import build_geometry


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate geometry via OpenAI")
    parser.add_argument("prompt", help="Prompt or equation")
    args = parser.parse_args(argv)

    spec = call_openai(args.prompt)
    geom = build_geometry(spec)
    print(geom)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
