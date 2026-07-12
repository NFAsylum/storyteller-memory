"""Backend-agnostic LLM smoke test — validates the LLM_BACKEND config switch end-to-end.

Reads LLM_BACKEND (fake | anthropic | local), sends one prompt through the real client,
and prints the response, token usage, cost, and latency.

Run:
  LLM_BACKEND=local    poetry run python scripts/smoke_llm.py "hello"
  LLM_BACKEND=anthropic ANTHROPIC_API_KEY=sk-ant-... poetry run python scripts/smoke_llm.py "hello"
  LLM_BACKEND=fake     poetry run python scripts/smoke_llm.py "hello"
"""

from __future__ import annotations

import sys
import time

from dotenv import load_dotenv

from core.llm_client import create_llm_client

load_dotenv()  # backend URLs/keys come from .env; inline env vars still win


def main(argv: list[str]) -> int:
    import os

    prompt = argv[1] if len(argv) > 1 else "hello"
    backend = os.environ.get("LLM_BACKEND", "fake")
    print(f"backend: {backend}")

    client = create_llm_client()
    started = time.monotonic()
    result = client.generate(
        system="You are a helpful assistant. Answer in one short sentence.",
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.monotonic() - started

    print(f"prompt: {prompt!r}")
    print(f"response: {result.content!r}")
    print(
        f"stop_reason: {result.stop_reason} | "
        f"tokens in/out: {result.usage.get('input_tokens')}/{result.usage.get('output_tokens')}"
    )
    print(f"cost_usd: ${result.cost_usd:.6f} | latency: {elapsed:.2f}s")

    return 0 if result.content.strip() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
