"""可重复运行的最小飞行验证场景。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from lattice_core.flight.adapters import AlfaAdapter
from lattice_core.flight.mapping import frame_to_ingest_event


DEMO_ENTITY_ID = "beijing-flight-demo"
DEMO_ORIGIN_LATITUDE = 39.9042
DEMO_ORIGIN_LONGITUDE = 116.4074


async def run_minimal_validation(
    *,
    project_root: Path,
    ingest_service: Any,
    recommendation_service: Any,
    load_alerts: Any,
) -> dict[str, Any]:
    """回放少量真实数据集格式样本并打通规则、知识和建议链路。"""
    sample = project_root / "fixtures/flight/alfa_engine_failure_sample.csv"
    frames = list(AlfaAdapter(sample, source_id=DEMO_ENTITY_ID).frames())
    if not frames:
        raise RuntimeError(f"验证样本为空: {sample}")

    first_latitude = frames[0].latitude_deg or 0.0
    first_longitude = frames[0].longitude_deg or 0.0
    ingest_results = []
    for frame in frames:
        shifted = replace(
            frame,
            latitude_deg=DEMO_ORIGIN_LATITUDE
            + ((frame.latitude_deg or first_latitude) - first_latitude),
            longitude_deg=DEMO_ORIGIN_LONGITUDE
            + ((frame.longitude_deg or first_longitude) - first_longitude),
        )
        ingest_results.append(
            await ingest_service.ingest(frame_to_ingest_event(shifted))
        )

    alerts = [
        item
        for item in load_alerts()["alerts"].values()
        if item.get("entityId") == DEMO_ENTITY_ID
        and item.get("status") != "RESOLVED"
        and item.get("alertType")
        in {"flight_low_airspeed", "dataset_fault_annotation", "flight_attitude_limit"}
    ]
    recommendations = []
    for alert in alerts:
        recommendations.append(
            await recommendation_service.create_for_alert(alert["alertId"])
        )

    referenced_documents = sorted(
        {
            reference.get("docId")
            for result in recommendations
            for reference in result["recommendation"].get("references", [])
            if reference.get("docId")
        }
    )
    rule_types = sorted({alert["alertType"] for alert in alerts})
    return {
        "ok": bool(frames and alerts and recommendations),
        "scenario": "北京固定翼发动机故障最小验证",
        "entityId": DEMO_ENTITY_ID,
        "dataset": "ALFA",
        "samplePath": str(sample.relative_to(project_root)),
        "monitorUrl": "/static/flight-monitor-3d-v3.html",
        "summary": {
            "framesIngested": len(ingest_results),
            "alertsObserved": len(alerts),
            "recommendationsAvailable": len(recommendations),
        },
        "checks": {
            "telemetryNormalized": all(result.get("ok") for result in ingest_results),
            "trackAvailable": len(ingest_results) == len(frames),
            "rulesTriggered": bool(rule_types),
            "knowledgeReferenced": bool(referenced_documents),
            "recommendationGenerated": bool(recommendations),
            "humanConfirmationRequired": all(
                result["recommendation"].get("providerMetadata", {}).get(
                    "humanConfirmationRequired"
                )
                is True
                for result in recommendations
            ),
        },
        "ruleTypes": rule_types,
        "knowledgeReferences": referenced_documents,
        "recommendationIds": [result["recommendationId"] for result in recommendations],
    }
