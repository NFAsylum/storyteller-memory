"""Smoke test for the local LLM backend (llama-server).

Checks the /v1/models endpoint, does a trivial completion, and prints latency + tokens
+ observed tokens/s. Requires LOCAL_LLM_URL (and LLM_BACKEND=local).

Run: LLM_BACKEND=local poetry run python scripts/smoke_local.py
"""

from __future__ import annotations

import os
import sys
import time

import httpx
from dotenv import load_dotenv

from core.llm_client import create_llm_client

load_dotenv()  # LOCAL_LLM_URL / LOCAL_LLM_MODEL come from .env; inline env vars still win


def main() -> int:
    url = os.environ.get("LOCAL_LLM_URL")
    if not url:
        print("LOCAL_LLM_URL is not set", file=sys.stderr)
        return 2

    models_url = f"{url.rstrip('/')}/models"
    try:
        response = httpx.get(models_url, timeout=10)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - smoke script, surface any failure
        print(f"models endpoint unreachable ({models_url}): {exc}", file=sys.stderr)
        return 1
    print(f"models endpoint OK: {models_url}")

    client = create_llm_client("local")
    started = time.monotonic()
    result = client.generate(
        system="You are a terse assistant. Reply with exactly what is asked, nothing else.",
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )
    elapsed = time.monotonic() - started

    out_tokens = result.usage.get("output_tokens", 0)
    tps = out_tokens / elapsed if elapsed > 0 else 0.0
    print(f"content: {result.content!r}")
    print(f"stop_reason: {result.stop_reason} | cost_usd: {result.cost_usd}")
    print(f"latency: {elapsed:.2f}s | output_tokens: {out_tokens} | tps: {tps:.1f}")

    ok = "OK" in result.content.upper()
    print("SMOKE OK" if ok else "SMOKE FAILED (no 'OK' in reply)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
