import os
import json
import logging
import time
from typing import Any, Dict, Optional

try:
    import openai  # type: ignore
except Exception as exc:  # pragma: no cover - optional dependency
    openai = None

_MODEL = os.getenv("ADCAD_OPENAI_MODEL", "gpt-4.1-mini")
_MAX_TOKENS = 2048

_SYSTEM_PROMPT = """\
You are an expert CAD kernel assistant.
When you receive:
  • an explicit equation (e.g. "z = sin(x)*cos(y)")
  • or a natural-language instruction
you MUST reply ONLY with valid JSON matching this schema:
{
  "kind": "curve" | "surface" | "solid",
  "primitive": "bspline" | "extrude" | "revolve" | "implicit" | ...,
  "parameters": { ... }
}
No extra keys, no comments.
If the request is ambiguous, ask for clarification in JSON:
{ "need_clarification": "...question..." }
"""

def call_openai(user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Call the OpenAI chat completion endpoint and return parsed JSON."""
    if openai is None:  # pragma: no cover - environment missing openai
        raise RuntimeError("openai package is not installed")

    model = model or _MODEL
    client = openai.OpenAI()
    t0 = time.time()

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=_MAX_TOKENS,
    )

    msg = completion.choices[0].message.content
    cost = completion.usage.total_tokens
    logging.info("OpenAI call %.2fs – %s tokens", time.time() - t0, cost)
    try:
        return json.loads(msg)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Bad JSON from OpenAI: {exc}\n---\n{msg}\n---")
