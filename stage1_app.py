#!/usr/bin/env python3
"""阶段 1 完整入口：ingest、事件信封和 recommendation Provider 均已接线。"""

from typing import Any

from fastapi import HTTPException

import app as ingest_entry
import mock_server as legacy
from lattice_core.legacy_adapters import CallableKnowledgeRetriever, CallableRecommendationProvider
from lattice_core.recommendations import RecommendationNotFoundError, RecommendationService, RecommendationServiceDependencies


app = ingest_entry.app
recommendation_service = RecommendationService(
    RecommendationServiceDependencies(
        load_alerts=legacy.load_alerts_store,
        save_alerts=legacy.save_alerts_store,
        load_entities=legacy.read_store,
        load_recommendations=legacy.load_recommendations_store,
        save_recommendations=legacy.save_recommendations_store,
        build_context=legacy.build_recommendation_context,
        build_signature=legacy.build_recommendation_state_signature,
        build_record=legacy.build_recommendation_record,
        timestamp_key=legacy.timestamp_sort_key,
        broadcast_recommendation=legacy.broadcast_recommendation_created,
        broadcast_alert=legacy.broadcast_alert_updated,
        now=legacy.utc_now_iso,
    ),
    retriever=CallableKnowledgeRetriever(legacy.search_local_knowledge_base),
    provider=CallableRecommendationProvider(legacy.call_dify_recommendation),
)

app.router.routes = [
    route for route in app.router.routes
    if not (
        getattr(route, "path", None) == "/api/v1/alerts/{alert_id}/recommendation"
        and "POST" in getattr(route, "methods", set())
    )
]


@app.post("/api/v1/alerts/{alert_id}/recommendation")
async def create_recommendation_for_alert(alert_id: str) -> dict[str, Any]:
    try:
        return await recommendation_service.create_for_alert(alert_id)
    except RecommendationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
