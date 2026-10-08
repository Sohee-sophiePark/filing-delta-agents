"""Gemini JSON calls over REST with a free-tier fallback chain, plus record/replay cassettes."""

import hashlib
import json
import os
import pathlib
import re
import threading
import time

import httpx

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
FALLBACK_STATUS = {404, 429, 500, 503}
ROUNDS = 3  # passes over the whole chain before giving up
MAX_WAIT = 60.0


class CassetteMiss(KeyError):
    pass


class LLM:
    """`live` calls Gemini; `record` also appends to the cassette; `replay` serves it only."""

    def __init__(
        self,
        mode: str,
        cassette: pathlib.Path,
        models: list[str],
        max_tokens: int,
        http: httpx.Client | None = None,
    ) -> None:
        self.mode, self.cassette, self.models, self.max_tokens = mode, cassette, models, max_tokens
        self.http = http or httpx.Client(timeout=120)
        self.calls: list[dict] = []
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(2)  # free-tier rate limits: at most two calls in flight
        self._entries: dict[str, list[dict]] = {}
        self._served: dict[str, int] = {}
        if cassette.exists():
            for line in cassette.read_text(encoding="utf-8").splitlines():
                e = json.loads(line)
                self._entries.setdefault(e["key"], []).append(e)

    def json(self, purpose: str, system: str, user: str, temperature: float) -> dict:
        """One structured call; returns the parsed JSON object."""
        req = {"system": system, "user": user, "temperature": temperature, "max": self.max_tokens}
        key = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()
        if self.mode == "replay":
            with self._lock:
                if key not in self._entries:
                    raise CassetteMiss(f"no recording for {purpose}; run in record mode")
                n = self._served.get(key, 0)
                self._served[key] = n + 1
                e = self._entries[key][min(n, len(self._entries[key]) - 1)]
            self.calls.append({**e["meta"], "purpose": purpose, "source": "replay"})
            return e["response"]
        response, meta = self._live(req)
        self.calls.append({**meta, "purpose": purpose, "source": "live"})
        if self.mode == "record":
            with self._lock:
                self.cassette.parent.mkdir(parents=True, exist_ok=True)
                with self.cassette.open("a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {"key": key, "purpose": purpose, "meta": meta, "response": response}
                        )
                        + "\n"
                    )
        return response

    def _live(self, req: dict) -> tuple[dict, dict]:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set (load .env into the shell first)")
        body = {
            "systemInstruction": {"parts": [{"text": req["system"]}]},
            "contents": [{"role": "user", "parts": [{"text": req["user"]}]}],
            "generationConfig": {
                "temperature": req["temperature"],
                "maxOutputTokens": req["max"],
                "responseMimeType": "application/json",
            },
        }
        errors: list[str] = []
        for _ in range(ROUNDS):
            wait = 20.0
            for model in self.models:
                t0 = time.monotonic()
                try:
                    with self._slots:
                        r = self.http.post(
                            URL.format(model=model), json=body, headers={"x-goog-api-key": key}
                        )
                except httpx.TimeoutException:
                    errors.append(f"{model}: timeout")
                    continue
                if r.status_code in FALLBACK_STATUS:
                    errors.append(f"{model}: {r.status_code}")
                    if m := re.search(r'"retryDelay":\s*"(\d+)', r.text):
                        wait = min(wait, float(m.group(1)))
                    continue
                r.raise_for_status()
                data = r.json()
                parts = data["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                try:
                    parsed = json.loads(text.strip().removeprefix("```json").removesuffix("```"))
                except json.JSONDecodeError:
                    errors.append(f"{model}: invalid JSON")
                    continue
                usage = data.get("usageMetadata", {})
                return parsed, {
                    "model": model,
                    "tokens_in": usage.get("promptTokenCount", 0),
                    "tokens_out": usage.get("candidatesTokenCount", 0),
                    "latency_ms": int((time.monotonic() - t0) * 1000),
                }
            time.sleep(min(wait, MAX_WAIT))
        raise RuntimeError(f"every free-tier model failed: {errors[-len(self.models) :]}")
