"""建议生成应用服务。"""

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .providers import KnowledgeRetriever, RecommendationProvider


Broadcast = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class RecommendationServiceDependencies:
    load_alerts: Callable[[], dict[str, Any]]
    save_alerts: Callable[[dict[str, Any]], None]
    load_entities: Callable[[], dict[str, Any]]
    load_recommendations: Callable[[], dict[str, Any]]
    save_recommendations: Callable[[dict[str, Any]], None]
    build_context: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
    build_signature: Callable[[dict[str, Any], dict[str, Any]], str]
    build_record: Callable[..., dict[str, Any]]
    timestamp_key: Callable[[dict[str, Any], str], str]
    broadcast_recommendation: Broadcast
    broadcast_alert: Broadcast
    now: Callable[[], str]


class RecommendationNotFoundError(LookupError):
    pass


class RecommendationService:
    def __init__(
        self,
        dependencies: RecommendationServiceDependencies,
        retriever: KnowledgeRetriever,
        provider: RecommendationProvider,
    ) -> None:
        self._deps = dependencies
        self._retriever = retriever
        self._provider = provider

    async def create_for_alert(self, alert_id: str) -> dict[str, Any]:
        deps = self._deps
        alerts_store = deps.load_alerts()
        alert = alerts_store["alerts"].get(alert_id)
        if alert is None:
            raise RecommendationNotFoundError(f"alert 不存在: {alert_id}")
        entity = deps.load_entities()["entities"].get(alert.get("entityId"))
        if entity is None:
            raise RecommendationNotFoundError(f"关联 entity 不存在: {alert.get('entityId')}")

        context = deps.build_context(alert, entity)
        signature = deps.build_signature(alert, entity)
        store = deps.load_recommendations()
        matches = [item for item in store["recommendations"].values() if isinstance(item, dict) and item.get("alertId") == alert_id]
        existing = next((item for item in sorted(matches, key=lambda item: deps.timestamp_key(item, "updatedAt"), reverse=True) if item.get("stateSignature") == signature), None)
        if existing is not None:
            await self._link_alert(alerts_store, alert, existing["recommendationId"])
            return {"recommendationId": existing["recommendationId"], "recommendation": existing, "reused": True}

        query = " ".join([
            str(alert.get("alertType") or ""), str(alert.get("title") or ""),
            str(entity.get("ontology", {}).get("specificType") or ""),
            str(entity.get("milView", {}).get("environment") or ""),
            " ".join(str(item) for item in alert.get("evidence", []) if isinstance(item, str)),
        ]).strip()
        context["knowledge"] = await asyncio.to_thread(self._retriever.search, query, filters={"alertType": alert.get("alertType")}, limit=3)
        generated = await asyncio.to_thread(self._provider.recommend, context)
        recommendation = deps.build_record(alert, entity, generated, state_signature=signature)
        store["recommendations"][recommendation["recommendationId"]] = recommendation
        deps.save_recommendations(store)
        await self._link_alert(alerts_store, alert, recommendation["recommendationId"], force_update=True)
        await deps.broadcast_recommendation(recommendation)
        return {"recommendationId": recommendation["recommendationId"], "recommendation": recommendation, "reused": False}

    async def _link_alert(self, store: dict[str, Any], alert: dict[str, Any], recommendation_id: str, *, force_update: bool = False) -> None:
        metadata = alert.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            alert["metadata"] = metadata
        if not force_update and metadata.get("latestRecommendationId") == recommendation_id:
            return
        metadata["latestRecommendationId"] = recommendation_id
        alert["updatedAt"] = self._deps.now()
        self._deps.save_alerts(store)
        await self._deps.broadcast_alert(alert)
