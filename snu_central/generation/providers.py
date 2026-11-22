"""LLMProvider interface; GroqProvider (OpenAI-compatible), optional OllamaProvider (NFR-4.3).

Model names change on Groq without notice, so the model is never hard-wired:
  config.yaml `llm.model` is tried first, then each of `llm.fallback_models`, filtered by what the
  provider's /models endpoint says is currently available. If a call still fails with "model not found",
  the next candidate is tried.
"""

import os
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator

from ..config import PROJECT_ROOT


class LLMUnavailable(Exception):
    """No answer could be generated (no key, network, rate limit, timeout, no usable model)."""


def load_dotenv() -> None:
    """Read KEY=VALUE lines from .env into os.environ (without overriding real env vars)."""
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


class LLMProvider(ABC):
    @abstractmethod
    def stream(self, messages: list[dict]) -> Iterator[str]:
        """Yield answer text pieces. Raises LLMUnavailable on failure."""


class OpenAICompatProvider(LLMProvider):
    def __init__(self, cfg: dict, require_key: bool = True):
        from openai import OpenAI
        load_dotenv()
        self.cfg = cfg
        # Primary key first, then backups. A backup is used only when a key is rejected (HTTP 401):
        # keys of one Groq organization share its rate limits, so switching keys never adds quota.
        names = [cfg["api_key_env"], *cfg.get("backup_key_envs", [])]
        self._keys = [(n, os.environ[n]) for n in names if os.environ.get(n)]
        if require_key and not self._keys:
            raise LLMUnavailable(f"{cfg['api_key_env']} is not set (put it in .env or the environment)")
        self._key_i = 0
        self._openai = OpenAI
        self.client = self._make_client()
        self._candidates: list[str] | None = None
        self.model_used: str | None = None
        self.notice: str | None = None     # set when a model was chosen automatically

    def _make_client(self):
        key = self._keys[self._key_i][1] if self._keys else "none"
        return self._openai(base_url=self.cfg["base_url"], api_key=key,
                            timeout=self.cfg["timeout_seconds"], max_retries=0)

    @property
    def key_name(self) -> str | None:
        """Name of the environment variable whose key is in use (never the key itself)."""
        return self._keys[self._key_i][0] if self._keys else None

    def _use_next_key(self) -> bool:
        if self._key_i + 1 >= len(self._keys):
            return False
        self._key_i += 1
        self.client = self._make_client()
        self._candidates = None                        # re-check the model list with the new key
        return True

    # ---- model resolution -------------------------------------------------------------------
    def available_models(self) -> list[str]:
        try:
            return [m.id for m in self.client.models.list().data]
        except Exception:   # noqa: BLE001 - listing is best-effort; fall back to config order
            return []

    def candidates(self) -> list[str]:
        if self._candidates is None:
            wanted = [self.cfg["model"], *self.cfg.get("fallback_models", [])]
            have = set(self.available_models())
            usable = [m for m in wanted if m in have] if have else wanted
            if not usable:                                  # last resort: discover a chat model (clearly flagged)
                usable = self.discover(have)
                if not usable:
                    raise LLMUnavailable(f"none of {wanted} is offered by the provider; update llm.model in config.yaml")
                self._auto_selected = True
                self.notice = (f"Configured models {wanted} are no longer offered. Using '{usable[0]}' "
                               "chosen automatically; answer quality is unchecked. Update llm.model in config.yaml.")
            self._candidates = usable
        return self._candidates

    _NOT_CHAT = ("whisper", "orpheus", "guard", "safeguard", "tts", "embed", "playai", "distil-whisper")
    _PREFER = ("gpt-oss", "llama", "qwen", "kimi", "deepseek")

    def discover(self, available: list[str]) -> list[str]:
        """Chat-capable models from the live list (audio, guard and embedding models removed), best families first."""
        chat = [m for m in available if not any(x in m.lower() for x in self._NOT_CHAT)]
        rank = lambda m: next((i for i, f in enumerate(self._PREFER) if f in m.lower()), len(self._PREFER))  # noqa: E731
        return sorted(chat, key=lambda m: (rank(m), -len(m)))[:3]

    # ---- generation -------------------------------------------------------------------------
    def _request(self, model: str, messages: list[dict]):
        kwargs = dict(model=model, messages=messages, temperature=self.cfg["temperature"], stream=True)
        if "gpt-oss" in model and self.cfg.get("reasoning_effort"):
            kwargs["extra_body"] = {"reasoning_effort": self.cfg["reasoning_effort"]}
        return self.client.chat.completions.create(**kwargs)

    def stream(self, messages):
        from openai import AuthenticationError
        try:
            yield from self._stream(messages)
        except AuthenticationError as e:               # nothing was streamed: a 401 comes before any text
            rejected = self.key_name
            if not self._use_next_key():
                raise LLMUnavailable(f"API key in {rejected} was rejected (401); no backup key left") from e
            yield from self.stream(messages)
            note = f"The API key in {rejected} was rejected, so the backup key in {self.key_name} was used."
            self.notice = f"{note} {self.notice}" if self.notice else note

    def _stream(self, messages):
        from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, RateLimitError
        last: Exception | None = None
        for model in self.candidates():
            for attempt in (1, 2):
                started = False
                try:
                    for chunk in self._request(model, messages):
                        if chunk.choices and chunk.choices[0].delta.content:
                            started = True
                            yield chunk.choices[0].delta.content
                    self.model_used = model
                    if model != self.cfg["model"] and not self.notice:
                        self.notice = (f"Answered by the fallback model '{model}' because '{self.cfg['model']}' "
                                       f"was unavailable ({type(last).__name__ if last else 'not offered'}). "
                                       "Fallback models follow the citation rules less reliably.")
                    return
                except RateLimitError as e:
                    last = e
                    if started:                                # partial answer already shown: do not splice another
                        raise LLMUnavailable("rate limited mid-answer") from e
                    if attempt == 1:           # retry once after Retry-After (design §8)
                        wait = float(getattr(e.response, "headers", {}).get("retry-after", 2) or 2)
                        time.sleep(min(wait, 10))
                        continue
                    break
                except AuthenticationError:
                    raise                                      # handled in stream(): try the backup key
                except APIStatusError as e:
                    last = e
                    if started:
                        raise LLMUnavailable(f"{e.status_code} mid-answer") from e
                    if e.status_code in (400, 404):   # model retired / not allowed -> next candidate
                        break
                    raise LLMUnavailable(f"{e.status_code}: {e.message}") from e
                except (APITimeoutError, APIConnectionError) as e:
                    raise LLMUnavailable(f"network/timeout: {e}") from e
        raise LLMUnavailable(f"no model produced an answer ({last})")


class GroqProvider(OpenAICompatProvider):
    pass


class OllamaProvider(OpenAICompatProvider):
    def __init__(self, cfg: dict):
        super().__init__({**cfg, "base_url": cfg.get("ollama_url", "http://localhost:11434/v1")}, require_key=False)


def get_provider(cfg: dict) -> LLMProvider:
    llm = cfg["llm"]
    return OllamaProvider(llm) if llm["provider"] == "ollama" else GroqProvider(llm)
