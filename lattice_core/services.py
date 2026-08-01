"""与 HTTP、文件格式和具体仿真平台无关的应用服务。"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, MutableMapping


LoadStore = Callable[[], dict[str, Any]]
SaveStore = Callable[[dict[str, Any]], None]
Broadcast = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class IngestServiceDependencies:
    parse_event: Callable[[Any], dict[str, Any]]
    build_entity: Callable[[dict[str, Any]], dict[str, Any]]
    evaluate_rules: Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]]
    apply_threat: Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]]
    build_alert: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]
    find_active_alert: Callable[[MutableMapping[str, Any], str, str], dict[str, Any] | None]
    load_events: LoadStore
    save_events: SaveStore
    load_entities: LoadStore
    save_entities: SaveStore
    load_alerts: LoadStore
    save_alerts: SaveStore
    broadcast_entity: Callable[[dict[str, Any]], Awaitable[None]]
    broadcast_alert_created: Broadcast
    broadcast_alert_updated: Broadcast
    now: Callable[[], str]


class IngestService:
    """编排遥测事件入库、实体更新、规则求值和告警发布。"""

    def __init__(self, dependencies: IngestServiceDependencies) -> None:
        self._deps = dependencies

    async def ingest(self, payload: Any) -> dict[str, Any]:
        deps = self._deps
        event = deps.parse_event(payload)

        event_store = deps.load_events()
        event_store["events"][event["eventId"]] = event
        deps.save_events(event_store)

        entity = deps.build_entity(event)
        candidates = deps.evaluate_rules(event, entity)
        entity = deps.apply_threat(entity, candidates)

        entity_store = deps.load_entities()
        entity_store["entities"][entity["entityId"]] = entity
        deps.save_entities(entity_store)
        await deps.broadcast_entity(entity)

        affected_alert_ids: list[str] = []
        alerts_store = deps.load_alerts()
        for rule in candidates:
            alert = deps.find_active_alert(
                alerts_store["alerts"], entity["entityId"], rule["alertType"]
            )
            if alert is None:
                alert = deps.build_alert(event, entity, rule)
                alerts_store["alerts"][alert["alertId"]] = alert
                affected_alert_ids.append(alert["alertId"])
                await deps.broadcast_alert_created(alert)
                continue

            self._refresh_alert(alert, event, entity, rule)
            affected_alert_ids.append(alert["alertId"])
            await deps.broadcast_alert_updated(alert)

        deps.save_alerts(alerts_store)
        return {
            "ok": True,
            "eventId": event["eventId"],
            "entityId": entity["entityId"],
            # 兼容既有 API 名称；其中也包含更新的 alert。
            "alertsCreated": affected_alert_ids,
        }

    def _refresh_alert(
        self,
        alert: dict[str, Any],
        event: dict[str, Any],
        entity: dict[str, Any],
        rule: dict[str, Any],
    ) -> None:
        alert.update(
            {
                "riskLevel": rule["riskLevel"],
                "title": rule["title"],
                "summary": rule["summary"],
                "location": {
                    "latitudeDegrees": entity["location"]["position"]["latitudeDegrees"],
                    "longitudeDegrees": entity["location"]["position"]["longitudeDegrees"],
                },
                "evidence": rule["evidence"],
                "updatedAt": self._deps.now(),
            }
        )
        old_metadata = alert.get("metadata")
        alert["metadata"] = {
            **(old_metadata if isinstance(old_metadata, dict) else {}),
            "eventId": event["eventId"],
            "zone": event["sensorContext"].get("zone"),
            "speedMps": entity.get("metadata", {}).get("track", {}).get("speedMps"),
            "tags": event["sensorContext"].get("tags", []),
        }
