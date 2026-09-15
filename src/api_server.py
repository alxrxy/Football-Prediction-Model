"""Local Q&A server for the dashboard's Claude sections.

    python -m src.api_server          # http://127.0.0.1:8787

The dashboard is static files, so it can't hold an API key; this holds it and
answers two routes, which the Vite dev server proxies under /api:

  GET  /api/health   key configured? model, today's spend and budget
  POST /api/ask      {game_id, question, history?} -> {answer, mode, cost_usd}

Each question sends Claude only that game's numbers (src/game_context.py):
the prediction, market and simulation before kickoff, or the live state and
live re-projection while the game is on. Guardrails for a metered API:
questions capped at 500 characters, the last 3 exchanges kept as history, 40
questions an hour, and the daily spend cap in src/claude_ai.py. It listens on
127.0.0.1 only.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import claude_ai, config, game_context

HOST = "127.0.0.1"
PORT = int(os.getenv("QA_PORT", "8787"))
MAX_QUESTION = 500
MAX_HISTORY = 3
MAX_ANSWER_ECHO = 1500       # a prior answer sent back as history is trimmed to this
PER_HOUR = 40

SYSTEM = (
    "You answer questions about one football game for the owner of a personal prediction dashboard. "
    "Use only the game data provided with the question; if the answer isn't in it, say what's missing "
    "rather than guessing. The numbers are a model's projections, not facts: its value flags are "
    "unvalidated, its player projections are lower confidence than its score projections, and the "
    "betting market is usually the better forecast. Describe what the numbers say; never tell the user "
    "to bet. Answer in plain English in two to five sentences, or a short list when comparing things. "
    "No preamble."
)

_recent: deque[float] = deque()
_lock = threading.Lock()


def _allowed() -> bool:
    now = time.time()
    with _lock:
        while _recent and now - _recent[0] > 3600:
            _recent.popleft()
        if len(_recent) >= PER_HOUR:
            return False
        _recent.append(now)
        return True


def answer(payload: dict) -> tuple[int, dict]:
    game_id = str(payload.get("game_id") or "").strip()[:60]
    question = str(payload.get("question") or "").strip()
    if not game_id or not question:
        return 400, {"error": "A game and a question are both needed."}
    if len(question) > MAX_QUESTION:
        return 400, {"error": f"Keep questions under {MAX_QUESTION} characters."}
    ctx = game_context.build(game_id)
    if ctx is None:
        return 404, {"error": "No data for this game. Re-export the dashboard: python -m src.export_dashboard"}
    if not _allowed():
        return 429, {"error": f"That's {PER_HOUR} questions in the last hour; the limit resets as the hour rolls on."}

    messages = []
    for turn in (payload.get("history") or [])[-MAX_HISTORY:]:
        q, a = str(turn.get("q") or "").strip()[:MAX_QUESTION], str(turn.get("a") or "").strip()[:MAX_ANSWER_ECHO]
        if q and a:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    messages.append({"role": "user", "content": f"Game data ({ctx['mode']}):\n{ctx['text']}\n\nQuestion: {question}"})

    try:
        r = claude_ai.ask(SYSTEM, messages, purpose=f"qa:{ctx['mode']}:{game_id}")
    except claude_ai.BudgetExceeded as exc:
        return 429, {"error": str(exc)}
    except claude_ai.ClaudeUnavailable as exc:
        return 503, {"error": str(exc)}
    print(f"  [qa] {game_id} ({ctx['mode']}): {r['tokens']['input']} in / {r['tokens']['output']} out, "
          f"~${r['cost_usd']:.4f}")
    if not r["text"]:
        reason = "Claude declined to answer that." if r["stop_reason"] == "refusal" else "No answer came back; try rephrasing."
        return 502, {"error": reason}
    return 200, {"answer": r["text"], "mode": ctx["mode"], "cost_usd": r["cost_usd"], "model": r["model"]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 - http.server naming
        if self.path.split("?")[0] == "/api/health":
            self._send(200, {"ok": True, "model": config.CLAUDE_MODEL, "effort": config.CLAUDE_EFFORT,
                             "key_configured": bool(config.CLAUDE_API_KEY),
                             "spent_today_usd": round(claude_ai.spent_today(), 4),
                             "daily_budget_usd": config.CLAUDE_DAILY_BUDGET_USD})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0] != "/api/ask":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 20_000:
            self._send(413, {"error": "request too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return
        status, body = answer(payload if isinstance(payload, dict) else {})
        self._send(status, body)

    def log_message(self, fmt, *args):  # the [qa] lines are the log
        pass


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[qa] Claude Q&A on http://{HOST}:{PORT}  model {config.CLAUDE_MODEL}, effort {config.CLAUDE_EFFORT}, "
          f"budget ${config.CLAUDE_DAILY_BUDGET_USD:.2f}/day, spent today ${claude_ai.spent_today():.3f}"
          + ("" if config.CLAUDE_API_KEY else "  [warn] no Claude_API_KEY in .env"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
