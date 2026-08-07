from __future__ import annotations

import json
import os
import uuid
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from filelock import FileLock

from .errors import QlibxError

EVENT_SCHEMA = "qlibx.agent_action_event/v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _clean(item)) is not None
        }
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    scalar = getattr(value, "item", None)
    if callable(scalar):
        return _clean(scalar())
    return value


class ActionJournal:
    """Append-only action journal used by public qlibx operations."""

    def __init__(
        self,
        project_root: Path,
        *,
        actor_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.path = self.project_root / ".qlibx" / "events" / "events.jsonl"
        self.lock = FileLock(str(self.path) + ".lock")
        self.actor_id = actor_id or os.environ.get("QLIBX_AGENT_ID", "unknown-agent")
        self.session_id = session_id or os.environ.get(
            "QLIBX_SESSION_ID", str(uuid.uuid4())
        )
        self.project_id = uuid.uuid5(uuid.NAMESPACE_URL, self.project_root.as_uri()).hex

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            _clean(event), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        with self.lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(payload)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def operation(
        self,
        action: str,
        *,
        read_only: bool,
        inputs: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> JournalOperation:
        return JournalOperation(
            self,
            action=action,
            read_only=read_only,
            inputs=inputs or {},
            extra_context=context or {},
        )

    def query(
        self,
        *,
        operation_id: str | None = None,
        action: str | None = None,
        phase: str | None = None,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 10_000:
            raise ValueError("limit must be between 1 and 10000")
        if not self.path.is_file():
            return []
        matches: list[dict[str, Any]] = []
        with self.lock, self.path.open(encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                if operation_id and event.get("operation_id") != operation_id:
                    continue
                if action and event.get("action") != action:
                    continue
                if phase and event.get("phase") != phase:
                    continue
                if actor_id and event.get("actor", {}).get("id") != actor_id:
                    continue
                matches.append(event)
        return matches[-limit:]


class JournalOperation(AbstractContextManager["JournalOperation"]):
    def __init__(
        self,
        journal: ActionJournal,
        *,
        action: str,
        read_only: bool,
        inputs: dict[str, Any],
        extra_context: dict[str, Any],
    ) -> None:
        self.journal = journal
        self.action = action
        self.read_only = read_only
        self.inputs = inputs
        self.operation_id = str(uuid.uuid4())
        self.sequence = 0
        self.outputs: dict[str, Any] = {}
        self.side_effects: dict[str, Any] = {}
        self.warnings: list[dict[str, Any] | str] = []
        self.accepted_limitations: list[str] = []
        self.context = {
            "project_id": journal.project_id,
            "session_id": journal.session_id,
            **extra_context,
        }
        self._finished = False
        self._emit("requested")

    def _emit(self, phase: str, *, error: dict[str, Any] | None = None) -> None:
        event = {
            "schema": EVENT_SCHEMA,
            "event_id": str(uuid.uuid4()),
            "operation_id": self.operation_id,
            "occurred_at": _utc_now(),
            "sequence": self.sequence,
            "actor": {"type": "agent", "id": self.journal.actor_id},
            "context": self.context,
            "action": self.action,
            "phase": phase,
            "read_only": self.read_only,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "side_effects": self.side_effects,
            "warnings": self.warnings,
            "accepted_limitations": self.accepted_limitations,
            "error": error,
        }
        self.journal.append(event)
        self.sequence += 1

    def __enter__(self) -> Self:
        self._emit("started")
        return self

    def succeed(
        self,
        *,
        outputs: dict[str, Any] | None = None,
        side_effects: dict[str, Any] | None = None,
        warnings: list[dict[str, Any] | str] | None = None,
        accepted_limitations: list[str] | None = None,
    ) -> None:
        if outputs:
            self.outputs.update(outputs)
        if side_effects:
            self.side_effects.update(side_effects)
        if warnings:
            self.warnings.extend(warnings)
        if accepted_limitations:
            self.accepted_limitations.extend(accepted_limitations)

    def block(self, *, code: str, message: str) -> None:
        self._emit(
            "blocked", error={"code": code, "message": message, "retryable": False}
        )
        self._finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._finished:
            return False
        if exc is None:
            self._emit("succeeded")
        else:
            code = exc.code if isinstance(exc, QlibxError) else "unexpected_error"
            self._emit(
                "failed",
                error={"code": code, "message": str(exc), "retryable": False},
            )
        self._finished = True
        return False
