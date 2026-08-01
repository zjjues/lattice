from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from lattice_core.knowledge import LocalKnowledgeRetriever


class LayeredFlightKnowledgeRetriever:
    """Merge legacy JSON KB results with lightweight layered Markdown SOPs."""

    name = "legacy+layered-local"

    def __init__(self, legacy_search: Callable[..., list[dict]], sop_root: str | Path):
        self._legacy_search = legacy_search
        self._local = LocalKnowledgeRetriever(sop_root)

    def search(
        self, query: str, *, filters: dict[str, Any] | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        legacy_hits = self._legacy_search(query, limit=limit)
        local_hits = [
            {
                "docId": hit["id"], "title": hit["title"], "docType": "SOP",
                "tags": [hit["layer"]], "summary": hit["text"][:240],
                "excerpt": hit["text"][:240], "score": hit["score"],
                "source": hit["source"], "layer": hit["layer"],
            }
            for hit in self._local.search(query, limit=limit)
        ]
        merged: dict[str, dict[str, Any]] = {}
        for hit in [*local_hits, *legacy_hits]:
            key = str(hit.get("docId") or hit.get("title"))
            merged.setdefault(key, hit)
        return list(merged.values())[:limit]


class FlightRuleRecommendationProvider:
    """Deterministic flight advice first; delegate unrelated alerts to Dify/legacy."""

    name = "flight-rules+configured-provider"

    def __init__(self, fallback: Callable[[dict[str, Any]], dict[str, Any]]):
        self._fallback = fallback

    def recommend(self, context: dict[str, Any]) -> dict[str, Any]:
        alert = context.get("alert", {})
        alert_type = alert.get("alertType")
        templates = {
            "flight_low_airspeed": (
                "建议核验空速数据，并在飞行器限制范围内稳定能量状态。",
                ["交叉核对空速、地速与姿态数据", "避免急转并持续监测高度趋势", "变更任务前必须由操作员确认"],
                ["OPERATOR", "FLIGHT_CONTROLLER"],
            ),
            "flight_attitude_limit": (
                "建议核验姿态测量，并使飞行器回到设定的安全包线。",
                ["交叉核对四元数与欧拉角姿态", "检查控制指令与风扰动", "若持续越界，立即提交操作员处置"],
                ["OPERATOR", "FLIGHT_CONTROLLER"],
            ),
            "dataset_fault_annotation": (
                "数据集已标注故障处于活动状态；该信息用于验证处理链路，不代表模型推断结果。",
                ["确认故障类型和标注开始时间", "关联分析油门、空速、高度和姿态趋势", "创建任务前向操作员展示匹配的处置预案"],
                ["OPERATOR", "ANALYTICS"],
            ),
        }
        template = templates.get(alert_type)
        if template is None:
            return self._fallback(context)
        summary, actions, assets = template
        references = [
            {"docId": hit.get("docId"), "title": hit.get("title")}
            for hit in context.get("knowledge", [])[:3]
            if isinstance(hit, dict)
        ]
        return {
            "summary": summary,
            "riskLevel": alert.get("riskLevel", "MEDIUM"),
            "actions": actions,
            "recommendedAssetTypes": assets,
            "confidence": 0.8 if alert_type != "dataset_fault_annotation" else 1.0,
            "references": references,
            "provider": "飞行规则与处置预案",
            "providerMetadata": {"llmUsed": False, "humanConfirmationRequired": True},
        }
