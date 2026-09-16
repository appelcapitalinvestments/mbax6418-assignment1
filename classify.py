"""
MBAX 6418 - Assignment 1, Step 1
One review in, one validated ReviewAnalysis out.

Endpoint details come from `class-endpoints.txt` on Canvas (Dobolyi, 2026/09/09),
with one correction found by testing:

    # Hermes Primary Model
    Base URL: http://dobolyi.com:9000/v1
    API Key:  see .env.example - NOT stored in this repo
    Model:    deepseek-ai/DeepSeek-V4-Flash-0731   <-- as documented
              DeepSeek-V4-Flash-0731               <-- as actually served

The documented name is the upstream HuggingFace repo id. vLLM on port 9000
serves the model under the bare name, and requesting the prefixed form returns
HTTP 404 "The model ... does not exist." Port 9001 behaves the opposite way:
its /v1/models really does return the prefixed `cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit`.

Lesson worth keeping: the /v1/models endpoint is the source of truth, not the
handout. Run `python check_endpoint.py` to ask it.

Two settings are deliberate, not defaults:

  temperature=0 - matches the curl Dobolyi shows in the Week 4 slide notes,
  and the assignment's standing considerations require repeatable results:
  "any number you publish should come from a fixed choice of which reviews
  were used (a fixed seed) and fixed settings."

  max_tokens is generous. The 9001 endpoint is a reasoning model that spent
  98 reasoning tokens on a 1-token answer; 9000 did not show that behavior in
  testing, but a tight budget is the kind of thing that silently truncates a
  whole scoring run, so there is no reason to be stingy here.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from prompt import ReviewAnalysis, build_messages

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def _from_dotenv(key: str) -> str | None:
    """Read one KEY=value from a local .env, if present.

    Avoids a python-dotenv dependency for the handful of settings this needs.
    `.env` is gitignored, so nothing read here can reach the public repo.
    """
    path = Path(__file__).parent / ".env"
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip().strip("'\"")
    return None


def _require(key: str, default: str | None = None) -> str:
    value = os.getenv(key) or _from_dotenv(key) or default
    if not value:
        raise RuntimeError(
            f"{key} is not set.\n\n"
            f"Copy .env.example to .env and fill in the value from the course\n"
            f"materials on Canvas, or export it:  export {key}='...'\n\n"
            f".env is gitignored, so it will not be committed."
        )
    return value


BASE_URL = _require("CLASS_BASE_URL", "http://dobolyi.com:9000/v1")
MODEL = _require("CLASS_MODEL", "DeepSeek-V4-Flash-0731")

# No default. The class token is Dobolyi's to distribute, not ours to publish
# in a public repository, so it has to come from the environment or a
# gitignored .env. The assignment says as much: "think about whether the data
# file ... or any credentials/tokens belong in the repo - generally they don't."
API_KEY = _require("CLASS_API_KEY")

# Note this endpoint is plain HTTP. Nothing confidential should travel over it.

TEMPERATURE = 0.0
SEED = 6418

# 512 was too small and the failure it caused was not random. This endpoint
# serves a reasoning model: it emits chain-of-thought into a separate field
# before writing `content`, and that thinking is billed against the same
# max_tokens budget. When the budget ran out mid-thought the reply came back
# with empty content and the row was recorded as a failure.
#
# The Sep 13 balanced run lost 13 of 150 rows that way, and 7 of those 13 were
# 3-star reviews - the class the model already finds hardest and therefore
# thinks longest about. Dropping the hardest cases from the denominator
# inflates every accuracy figure computed from what survives. That is a
# non-random missingness problem, not a nuisance.
#
# max_tokens is a ceiling, not a target: raising it costs nothing on calls that
# already answered, and only buys headroom on the ones that were truncated.
MAX_TOKENS = 2048

# Timeout and retries are set explicitly. The library's default is 600 seconds
# per request with 2 automatic retries, which means one unresponsive call can
# sit there for half an hour looking exactly like a frozen terminal. On a
# 150-review loop against an endpoint that has already had an outage this week,
# that is not a theoretical problem. 60 seconds is generous for a single short
# classification; anything slower is a stall, not slowness.
REQUEST_TIMEOUT = 60.0
MAX_RETRIES = 2

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    timeout=REQUEST_TIMEOUT,
    max_retries=MAX_RETRIES,
)


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _extract_json(raw: str) -> dict:
    """Pull a JSON object out of the model's reply.

    The prompt forbids code fences and surrounding prose. Models ignore that
    sometimes, which is precisely Dobolyi's slide 22 point about prompting not
    guaranteeing adherence. This strips fences and, failing that, grabs the
    first {...} block. Anything still unparseable raises, so the caller can
    record a failure rather than silently scoring a wrong answer.
    """
    cleaned = _FENCE.sub("", raw.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"No JSON object found in model reply: {raw!r}")


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------

def available_models() -> list[str]:
    """Ask the endpoint what it actually serves.

    The authoritative answer to "what do I put in `model`". Use this rather
    than trusting any handout, which is how the 404 above happened.
    """
    return [m.id for m in client.models.list().data]


def classify_review(title: str, text: str) -> ReviewAnalysis:
    """Classify one review. Raises on an unusable reply."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=build_messages(title, text),
            temperature=TEMPERATURE,
            seed=SEED,
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised with a useful hint
        if "does not exist" in str(exc) or "404" in str(exc):
            try:
                served = ", ".join(available_models()) or "(none reported)"
            except Exception:  # noqa: BLE001
                served = "(could not query /v1/models)"
            raise ValueError(
                f"Endpoint {BASE_URL} rejected model {MODEL!r}. "
                f"It serves: {served}. "
                f"Set CLASS_MODEL to one of those, or edit MODEL in classify.py."
            ) from exc
        raise

    message = response.choices[0].message

    # Read .content only. Reasoning models put chain-of-thought in a separate
    # .reasoning field, and serializing the whole message object would
    # contaminate the predictions with it.
    raw = (message.content or "").strip()
    if not raw:
        # Say *why* rather than guessing. finish_reason="length" is proof the
        # budget ran out; anything else means something different went wrong.
        finish = getattr(response.choices[0], "finish_reason", "unknown")
        usage = getattr(response, "usage", None)
        used = getattr(usage, "completion_tokens", "?") if usage else "?"
        raise ValueError(
            f"Model returned empty content (finish_reason={finish}, "
            f"completion_tokens={used}/{MAX_TOKENS}). "
            + ("The token budget was spent on reasoning before any answer was "
               "written. Raise MAX_TOKENS." if finish == "length"
               else "Budget was not exhausted, so this is not a max_tokens problem.")
        )

    try:
        return ReviewAnalysis.model_validate(_extract_json(raw))
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not validate reply {raw!r}: {exc}") from exc


def classify_review_safe(title: str, text: str) -> ReviewAnalysis | None:
    """Same call, but returns None instead of raising.

    Step 2 scores 100 rows in a loop. One malformed reply should not kill the
    run; it should be counted as a failure and reported honestly.
    """
    try:
        return classify_review(title, text)
    except Exception as exc:  # noqa: BLE001 - deliberate: log and continue
        print(f"  [classification failed] {exc}")
        return None
