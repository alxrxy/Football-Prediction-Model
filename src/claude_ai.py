"""Claude API calls for the dashboard: the one paid piece of the stack.

Used by the Q&A server (src/api_server.py) and the weekly prop explanations
(src/props.py). Every call goes through `ask`, so cost is controlled in one
place:

  - a daily spend cap (CLAUDE_DAILY_BUDGET_USD); calls past it are refused
  - every call's tokens and estimated cost appended to data/claude_usage.jsonl
  - low effort by default: the answers are short and grounded in numbers the
    caller supplies, so deep thinking buys little
  - callers send only the context a question needs, never whole exports

Model: CLAUDE_MODEL, claude-opus-5 by default, with the server-side refusal
fallback on, so a request a safety classifier declines is re-run on
Anthropic's recommended fallback model instead of coming back empty.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import anthropic

from . import config

# $ per million tokens (input, output), for the cost log and the daily cap.
PRICE_PER_MTOK = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5-1": (10.0, 50.0),
}
FALLBACK_MODELS = {"claude-opus-5", "claude-fable-5-1", "claude-fable-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
USAGE_LOG = config.DATA_DIR / "claude_usage.jsonl"


class ClaudeUnavailable(RuntimeError):
    """No key, a rejected key, the API unreachable or erroring."""


class BudgetExceeded(RuntimeError):
    """Today's spend has reached CLAUDE_DAILY_BUDGET_USD."""


_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not config.CLAUDE_API_KEY:
            raise ClaudeUnavailable("No Claude API key found. Set Claude_API_KEY in .env.")
        _client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
    return _client


def cost_usd(model: str, usage) -> float:
    inp, out = PRICE_PER_MTOK.get(model, PRICE_PER_MTOK["claude-opus-5"])
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (usage.input_tokens * inp + read * inp * 0.1 + write * inp * 1.25
            + usage.output_tokens * out) / 1e6


def spent_today() -> float:
    """Estimated spend so far today (UTC), from the usage log."""
    if not USAGE_LOG.exists():
        return 0.0
    today = datetime.now(timezone.utc).date().isoformat()
    total = 0.0
    for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("at", "")).startswith(today):
            total += float(row.get("cost_usd") or 0)
    return total


def _log(row: dict) -> None:
    config.ensure_dirs()
    with open(USAGE_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def ask(system: str, messages: list[dict], *, purpose: str, max_tokens: int = 3000,
        schema: dict | None = None) -> dict:
    """One Messages API call. Returns {text, stop_reason, model, tokens, cost_usd}.

    `text` is None when Claude declined (stop_reason "refusal" after any
    fallback). `schema` constrains the answer to JSON matching it.
    """
    spent = spent_today()
    if spent >= config.CLAUDE_DAILY_BUDGET_USD:
        raise BudgetExceeded(
            f"Today's Claude API budget (${config.CLAUDE_DAILY_BUDGET_USD:.2f}) is used up "
            f"(${spent:.2f} spent). Raise CLAUDE_DAILY_BUDGET_USD in .env to allow more."
        )
    output_config: dict = {"effort": config.CLAUDE_EFFORT}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    request = dict(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=system,
                   messages=messages, output_config=output_config)
    try:
        if config.CLAUDE_MODEL in FALLBACK_MODELS:
            response = client().beta.messages.create(**request, betas=[FALLBACK_BETA], fallbacks="default")
        else:
            response = client().messages.create(**request)
    except anthropic.AuthenticationError as exc:
        raise ClaudeUnavailable("The Claude API rejected the key in .env (Claude_API_KEY).") from exc
    except anthropic.PermissionDeniedError as exc:
        raise ClaudeUnavailable("The Claude API key lacks permission for this model.") from exc
    except anthropic.RateLimitError as exc:
        raise ClaudeUnavailable("The Claude API is rate limiting; try again in a minute.") from exc
    except anthropic.APIConnectionError as exc:
        raise ClaudeUnavailable("Couldn't reach the Claude API (network).") from exc
    except anthropic.APIStatusError as exc:
        raise ClaudeUnavailable(f"Claude API error {exc.status_code}: {exc.message}") from exc

    cost = cost_usd(response.model, response.usage)
    tokens = {"input": response.usage.input_tokens, "output": response.usage.output_tokens}
    _log({"at": datetime.now(timezone.utc).isoformat(), "purpose": purpose, "model": response.model,
          **tokens, "cost_usd": round(cost, 5), "stop_reason": response.stop_reason,
          "request_id": getattr(response, "_request_id", None)})

    text = None
    if response.stop_reason != "refusal":
        text = "".join(b.text for b in response.content if b.type == "text").strip() or None
    return {"text": text, "stop_reason": response.stop_reason, "model": response.model,
            "tokens": tokens, "cost_usd": round(cost, 4)}
