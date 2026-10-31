"""Replay of recorded model calls, keyed on the full request.

The key is SHA-256 of the model, system prompt, schema and messages, so editing
a prompt misses loudly instead of replaying a stale answer. A miss raises
`RecordingMiss`, which the protocol logs as a fault before taking the fallback.

Writing needs an explicit `record=True`. Only an allow-list of response fields
is stored: the API key, headers and thinking blocks never reach a file.
"""

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Self

DEFAULT_RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "recordings"

_SECRET_SHAPE = re.compile(r"sk-ant-[A-Za-z0-9_-]+")
_SECRET_VARIABLES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class RecordingMiss(LookupError):
    """No recording exists for this exact request."""


class RecordingSecretError(ValueError):
    """A recording would have contained something shaped like a credential."""


def request_key(
    model: str,
    system: str,
    schema: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
) -> str:
    canonical = json.dumps(
        {"model": model, "system": system, "schema": schema, "messages": messages},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def key_for_call(kwargs: Mapping[str, Any]) -> str:
    """The recording key for keyword arguments to `messages.create`."""
    return request_key(
        kwargs["model"],
        kwargs["system"],
        kwargs["output_config"]["format"]["schema"],
        kwargs["messages"],
    )


@dataclass(frozen=True, slots=True)
class RecordedBlock:
    type: str
    text: str


@dataclass(frozen=True, slots=True)
class RecordedUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class RecordedMessage:
    """Duck-types the fields of an SDK message that the agents read."""

    model: str
    stop_reason: str | None
    content: tuple[RecordedBlock, ...]
    usage: RecordedUsage
    recorded_latency_ms: int


def _load(path: Path) -> RecordedMessage:
    data = json.loads(path.read_text(encoding="utf-8"))
    response = data["response"]
    return RecordedMessage(
        model=response["model"],
        stop_reason=response["stop_reason"],
        content=tuple(
            RecordedBlock(type=block["type"], text=block["text"])
            for block in response["content"]
        ),
        usage=RecordedUsage(
            input_tokens=response["usage"]["input_tokens"],
            output_tokens=response["usage"]["output_tokens"],
        ),
        recorded_latency_ms=response["latency_ms"],
    )


def _serialise(key: str, kwargs: Mapping[str, Any], response: Any, ms: int) -> str:
    usage = response.usage
    document = {
        "key": key,
        "request": {
            "model": kwargs["model"],
            "system": kwargs["system"],
            "schema": kwargs["output_config"]["format"]["schema"],
            "messages": kwargs["messages"],
        },
        "response": {
            "model": response.model,
            "stop_reason": response.stop_reason,
            "content": [
                {"type": "text", "text": block.text}
                for block in response.content
                if block.type == "text"
            ],
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            },
            "latency_ms": ms,
        },
    }
    text = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False)
    secrets = [os.environ.get(name) for name in _SECRET_VARIABLES]
    if _SECRET_SHAPE.search(text) or any(s and s in text for s in secrets):
        raise RecordingSecretError("refusing to write a credential to a recording")
    return text + "\n"


class RecordingClient:
    """Stands in for `anthropic.Anthropic` as `client.beta.messages.create`.

    With `record=False`, the default, it only replays and needs no key. With
    `record=True` it calls `inner` and stores what comes back.
    """

    def __init__(
        self,
        inner: Any = None,
        directory: Path = DEFAULT_RECORDINGS_DIR,
        *,
        record: bool = False,
    ) -> None:
        if record and inner is None:
            raise ValueError("record=True needs an inner client to call")
        self._inner = inner
        self._directory = directory
        self._record = record

    @property
    def beta(self) -> Self:
        return self

    @property
    def messages(self) -> Self:
        return self

    def with_options(self, **options: Any) -> "RecordingClient":
        inner = self._inner.with_options(**options) if self._record else self._inner
        return RecordingClient(inner, self._directory, record=self._record)

    def _path(self, key: str) -> Path:
        return self._directory / f"{key}.json"

    def create(self, **kwargs: Any) -> Any:
        key = key_for_call(kwargs)
        if not self._record:
            path = self._path(key)
            if not path.is_file():
                raise RecordingMiss(f"no recording for request {key[:12]}")
            return _load(path)
        return self._call_and_store(key, kwargs)

    def _call_and_store(self, key: str, kwargs: Mapping[str, Any]) -> Any:
        started = perf_counter()
        response = self._inner.beta.messages.create(**kwargs)
        latency_ms = round((perf_counter() - started) * 1000)
        text = _serialise(key, kwargs, response, latency_ms)
        self._directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=self._directory, delete=False, encoding="utf-8"
        ) as handle:
            handle.write(text)
        os.replace(handle.name, self._path(key))
        return response
