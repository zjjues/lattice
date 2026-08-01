"""统一领域事件信封，并兼容原有 WebSocket 顶层字段。"""

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    event_type: str
    timestamp: str
    source: str
    subject: Mapping[str, str]
    data: Mapping[str, Any]
    schema_version: str = "1.0"

    def to_dict(self, *, legacy_fields: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """输出标准信封；legacy_fields 保证当前前端无需同步升级。"""
        payload: dict[str, Any] = {
            "eventId": self.event_id,
            "schemaVersion": self.schema_version,
            "type": self.event_type,
            "timestamp": self.timestamp,
            "source": self.source,
            "subject": dict(self.subject),
            "data": dict(self.data),
        }
        if legacy_fields:
            payload.update(legacy_fields)
        return payload


class EventFactory:
    def __init__(self, now: Callable[[], str], source: str = "fake-lattice-core") -> None:
        self._now = now
        self._source = source

    def create(
        self,
        event_type: str,
        *,
        subject: Mapping[str, str],
        data: Mapping[str, Any],
        legacy_fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = DomainEvent(
            event_id=f"EVT_{uuid4().hex.upper()}",
            event_type=event_type,
            timestamp=self._now(),
            source=self._source,
            subject=subject,
            data=data,
        )
        return event.to_dict(legacy_fields=legacy_fields)
