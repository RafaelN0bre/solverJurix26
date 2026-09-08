"""Gemini client for the formalization stages: structured output, on-disk
response cache, retries and a full trace of every call.

Deliberately thin, and deliberately not DSPy. The pipeline's value is in the
prompts (`prompts/formalize/`) and in the deterministic checks around the
calls, so the model layer only has to do four things well:

* **Structured output.** Every stage declares a pydantic model, sent as
  `response_schema`, so the contract is enforced by the API rather than by
  regex over prose. A tolerant JSON fallback still exists for the rare
  response that arrives as text.
* **Cache.** Keyed on the rendered prompt plus the model configuration plus the
  response schema, so iterating on stage 4's prompt does not re-pay for stages
  1-3, and a re-run with an unchanged prompt is free and deterministic.
* **Retries.** Rate limits and 5xx are transient; a schema violation is not.
* **Trace.** One JSON line per call in `runs/<run_id>/trace.jsonl`, holding the
  exact prompt sent, the raw response, the parsed object and the token usage --
  the record the article needs to show what produced each formalization.

The network call itself sits behind `Transport`, so tests drive the whole
pipeline with a fake and never touch the API.
"""
import ast
import hashlib
import json
import logging
import os
import time

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

from .prompts import PromptSpec

logger = logging.getLogger("formalize.gemini")

DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_CACHE_DIR = Path(".cache/formalize")

#: HTTP statuses worth retrying: rate limiting and transient server failures.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """A model call that failed in a way retrying will not fix."""


# ----------------------------------------------------------------------
# Tolerant JSON parsing (fallback when `response.parsed` is unavailable)
# ----------------------------------------------------------------------
def _extract_braces(text: str) -> str:
    first, last = text.find("{"), text.rfind("}")
    return text[first:last + 1] if first != -1 and last > first else text


def _fix_truncated(text: str) -> Any:
    text = " ".join(_extract_braces(text).split())
    text += "}" * max(0, text.count("{") - text.count("}"))
    return json.loads(text)


def try_parse_json(text: str) -> Optional[dict]:
    """Parse `text` as a JSON object, tolerating fences, prose around it and a
    truncated tail. Returns None when nothing object-shaped can be recovered."""
    if isinstance(text, dict):
        return text
    if not isinstance(text, str) or not text.strip():
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```", 2)[1]
        stripped = stripped[4:] if stripped.startswith("json") else stripped
    for parser in (
        lambda: json.loads(stripped),
        lambda: json.loads(_extract_braces(stripped)),
        lambda: ast.literal_eval(_extract_braces(stripped)),
        lambda: _fix_truncated(stripped),
    ):
        try:
            result = parser()
        except Exception:
            continue
        if isinstance(result, dict):
            return result
    return None


# ----------------------------------------------------------------------
# Transport
# ----------------------------------------------------------------------
@dataclass
class RawResponse:
    """What a transport returns, independent of the SDK's own types."""
    text: str
    parsed: Optional[dict] = None
    usage: Dict[str, int] = field(default_factory=dict)
    model_version: str = ""
    response_id: str = ""


class Transport:
    """Minimal interface between the client and whatever performs the call."""

    def generate(self, *, model: str, prompt: str, schema: Type[BaseModel],
                 config: Dict[str, Any]) -> RawResponse:  # pragma: no cover - interface
        raise NotImplementedError


class GeminiTransport(Transport):
    """The real thing: `google-genai` with a pydantic `response_schema`."""

    def __init__(self, api_key: Optional[str] = None):
        from google import genai  # imported lazily so tests need no key

        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise LLMError(
                "GEMINI_API_KEY não definida. Copie .env.example para .env e "
                "preencha a chave (https://aistudio.google.com/apikey)."
            )
        self._client = genai.Client(api_key=key)

    def generate(self, *, model: str, prompt: str, schema: Type[BaseModel],
                 config: Dict[str, Any]) -> RawResponse:
        from google.genai import types

        generate_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=config.get("temperature", 0),
        )
        if config.get("max_output_tokens"):
            generate_config.max_output_tokens = int(config["max_output_tokens"])
        if config.get("thinking_budget") is not None:
            generate_config.thinking_config = types.ThinkingConfig(
                thinking_budget=int(config["thinking_budget"])
            )

        response = self._client.models.generate_content(
            model=model, contents=prompt, config=generate_config,
        )
        usage = response.usage_metadata
        parsed = response.parsed
        if isinstance(parsed, BaseModel):
            parsed = parsed.model_dump()
        return RawResponse(
            text=response.text or "",
            parsed=parsed if isinstance(parsed, dict) else None,
            usage={
                "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                "candidates_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                "thoughts_tokens": getattr(usage, "thoughts_token_count", 0) or 0,
                "total_tokens": getattr(usage, "total_token_count", 0) or 0,
            } if usage else {},
            model_version=response.model_version or "",
            response_id=response.response_id or "",
        )


# ----------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------
def _status_of(exc: Exception) -> Optional[int]:
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


#: Exception class names that mark a transient transport failure.
_RETRYABLE_TYPES = ("timeout", "deadline", "connection", "server", "protocol")

#: Message fragments for the transports that raise a *generic* class when the
#: connection drops mid-response. `httpx.RemoteProtocolError` is the one that
#: matters here: its class name says "protocol" and its message says "Server
#: disconnected without sending a response", and a dropped response is the
#: textbook retryable failure. Matched on the message rather than widening the
#: class-name list, so that a genuine protocol *error* is not retried forever.
_RETRYABLE_MESSAGES = ("disconnected", "incomplete read", "connection reset",
                       "connection aborted", "broken pipe")


def _is_retryable(exc: Exception) -> bool:
    status = _status_of(exc)
    if status is not None:
        return status in RETRYABLE_STATUS
    name = type(exc).__name__.lower()
    if any(token in name for token in _RETRYABLE_TYPES):
        return True
    message = str(exc).lower()
    return any(token in message for token in _RETRYABLE_MESSAGES)


class GeminiClient:
    """Runs a `PromptSpec` against a `Transport` and returns a validated model."""

    def __init__(self, *, transport: Optional[Transport] = None,
                 default_model: Optional[str] = None,
                 model_override: Optional[str] = None,
                 cache_dir: Optional[Path] = None,
                 use_cache: bool = True,
                 max_retries: int = 3,
                 sleep: Callable[[float], None] = time.sleep):
        self._transport = transport
        self.default_model = default_model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        # Set only when the caller asked for one model explicitly (`--model`);
        # it then wins over the per-stage `model:` in the prompt front matter,
        # which otherwise decides. Precedence, highest first:
        # override -> prompt front matter -> GEMINI_MODEL -> DEFAULT_MODEL.
        self.model_override = model_override
        self.cache_dir = Path(cache_dir or os.environ.get("FORMALIZE_CACHE_DIR") or DEFAULT_CACHE_DIR)
        self.use_cache = use_cache
        self.max_retries = max_retries
        self._sleep = sleep
        self.calls: List[dict] = []
        self._trace_path: Optional[Path] = None

    # -- wiring --------------------------------------------------------
    @property
    def transport(self) -> Transport:
        if self._transport is None:
            self._transport = GeminiTransport()
        return self._transport

    def set_trace_path(self, path: Optional[Path]) -> None:
        """Where to append one JSON line per call. Created on first write."""
        self._trace_path = Path(path) if path else None
        if self._trace_path:
            self._trace_path.parent.mkdir(parents=True, exist_ok=True)

    # -- cache ---------------------------------------------------------
    def _cache_key(self, prompt: PromptSpec, model: str, config: Dict[str, Any],
                   schema: Type[BaseModel]) -> str:
        payload = json.dumps(
            {
                "prompt": prompt.rendered_sha256,
                "model": model,
                "config": {k: config[k] for k in sorted(config)},
                "schema": schema.__name__,
                "schema_json": schema.model_json_schema(),
            },
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_read(self, key: str) -> Optional[RawResponse]:
        path = self.cache_dir / f"{key}.json"
        if not (self.use_cache and path.is_file()):
            return None
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return RawResponse(
            text=stored.get("text", ""),
            parsed=stored.get("parsed"),
            usage=stored.get("usage", {}),
            model_version=stored.get("model_version", ""),
            response_id=stored.get("response_id", ""),
        )

    def _cache_write(self, key: str, response: RawResponse) -> None:
        if not self.use_cache:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / f"{key}.json").write_text(
            json.dumps({
                "text": response.text, "parsed": response.parsed,
                "usage": response.usage, "model_version": response.model_version,
                "response_id": response.response_id,
            }, ensure_ascii=False),
            encoding="utf-8",
        )

    # -- main entry point ----------------------------------------------
    def generate(self, prompt: PromptSpec, schema: Type[BaseModel], *,
                 stage: Optional[str] = None, attempt: int = 0) -> BaseModel:
        """Send `prompt`, validate the response against `schema`, trace it."""
        stage = stage or prompt.stage
        config = dict(prompt.config)
        model = str(self.model_override or config.pop("model", None) or self.default_model)
        config.pop("model", None)

        key = self._cache_key(prompt, model, config, schema)
        cached = self._cache_read(key)
        started = time.time()

        if cached is not None:
            response, cache_hit = cached, True
        else:
            response, cache_hit = self._call_with_retries(model, prompt, schema, config), False
            self._cache_write(key, response)

        payload = response.parsed if isinstance(response.parsed, dict) else try_parse_json(response.text)
        if payload is None:
            self._trace(stage, attempt, prompt, model, config, response,
                        time.time() - started, cache_hit, error="resposta não é JSON")
            raise LLMError(
                f"Estágio {stage}: a resposta do modelo não pôde ser lida como JSON "
                f"({len(response.text)} caracteres)."
            )

        try:
            parsed = schema.model_validate(payload)
        except ValidationError as exc:
            self._trace(stage, attempt, prompt, model, config, response,
                        time.time() - started, cache_hit, error=str(exc))
            raise LLMError(f"Estágio {stage}: resposta fora do schema {schema.__name__}: {exc}") from exc

        self._trace(stage, attempt, prompt, model, config, response,
                    time.time() - started, cache_hit, parsed=parsed.model_dump())
        return parsed

    def _call_with_retries(self, model: str, prompt: PromptSpec,
                           schema: Type[BaseModel], config: Dict[str, Any]) -> RawResponse:
        last: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return self.transport.generate(
                    model=model, prompt=prompt.text, schema=schema, config=config,
                )
            except Exception as exc:  # noqa: BLE001 - re-raised below when fatal
                last = exc
                if not _is_retryable(exc) or attempt == self.max_retries - 1:
                    break
                delay = 2.0 * (2 ** attempt)
                logger.warning(
                    "%s falhou (%s); nova tentativa em %.0fs (%d/%d)",
                    prompt.stage, exc, delay, attempt + 2, self.max_retries,
                )
                self._sleep(delay)
        raise LLMError(f"Chamada ao modelo falhou no estágio {prompt.stage}: {last}") from last

    # -- trace ---------------------------------------------------------
    def _trace(self, stage: str, attempt: int, prompt: PromptSpec, model: str,
               config: Dict[str, Any], response: RawResponse, latency: float,
               cache_hit: bool, parsed: Optional[dict] = None,
               error: Optional[str] = None) -> None:
        record = {
            "stage": stage,
            "attempt": attempt,
            "prompt_path": prompt.relative_path,
            "prompt_version": prompt.version,
            "prompt_template_sha256": prompt.template_sha256,
            "prompt_rendered_sha256": prompt.rendered_sha256,
            "model": model,
            "model_version": response.model_version,
            "config": config,
            "cache_hit": cache_hit,
            "latency_s": round(latency, 3),
            "usage": response.usage,
            "prompt_text": prompt.text,
            "raw_response": response.text,
            "parsed": parsed,
            "error": error,
        }
        self.calls.append(record)
        if self._trace_path:
            with self._trace_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def usage_total(self) -> Dict[str, int]:
        totals: Dict[str, int] = {}
        for call in self.calls:
            if call.get("cache_hit"):
                continue
            for key, value in (call.get("usage") or {}).items():
                totals[key] = totals.get(key, 0) + int(value or 0)
        return totals
