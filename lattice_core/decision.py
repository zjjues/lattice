"""规则、向量知识库与可配置大模型组成的最小处置闭环。"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from lattice_core.llm.openai_compatible import OpenAICompatibleProvider


class RagRecommendationRetriever:
    """将 Embedding RAG 结果适配为现有 recommendation 引用格式。"""

    name = "embedding-rag+layered-fallback"

    def __init__(self, rag: Any, fallback: Any):
        self._rag = rag
        self._fallback = fallback

    def search(
        self, query: str, *, filters: dict[str, Any] | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        try:
            for hit in self._rag.search(query, limit):
                hits.append({
                    "docId": hit.get("documentId"),
                    "title": hit.get("documentName") or "知识库文档",
                    "docType": "EMBEDDING_RAG",
                    "summary": str(hit.get("content") or "")[:320],
                    "excerpt": str(hit.get("content") or "")[:600],
                    "score": float(hit.get("score") or 0),
                    "source": "embedding-rag",
                    "chunkId": hit.get("chunkId"),
                })
        except Exception:
            hits = []

        seen = {str(hit.get("docId")) for hit in hits}
        try:
            fallback_hits = self._fallback.search(query, filters=filters, limit=limit)
        except Exception:
            fallback_hits = []
        for hit in fallback_hits:
            key = str(hit.get("docId"))
            if key not in seen:
                hits.append(hit)
                seen.add(key)
        return hits[:limit]


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise ValueError("模型未返回 JSON 对象")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("模型输出必须是 JSON 对象")
    return value


class RuleRagLlmRecommendationProvider:
    """以规则为安全基线，以 RAG 为依据，以 LLM 生成可读处置建议。"""

    name = "rules+embedding-rag+configured-llm"
    _RISK_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

    def __init__(self, rule_provider: Any, load_model_config: Callable[[], dict[str, Any]]):
        self._rule_provider = rule_provider
        self._load_model_config = load_model_config

    def recommend(self, context: dict[str, Any]) -> dict[str, Any]:
        baseline = self._rule_provider.recommend(context)
        knowledge = [hit for hit in context.get("knowledge", []) if isinstance(hit, dict)]
        config = self._load_model_config()
        missing = [key for key in ("baseUrl", "apiKey", "chatModel") if not config.get(key)]
        if missing:
            return self._degraded(baseline, knowledge, "模型配置不完整")

        provider = OpenAICompatibleProvider(
            str(config["baseUrl"]), str(config["apiKey"]), str(config["chatModel"]), timeout=15
        )
        prompt_context = {
            "alert": context.get("alert", {}),
            "entity": context.get("entity", {}),
            "threat": context.get("threat", {}),
            "flightTelemetry": context.get("flightTelemetry", {}),
            "ruleBaseline": {
                "summary": baseline.get("summary"),
                "riskLevel": baseline.get("riskLevel"),
                "actions": baseline.get("actions", []),
            },
            "knowledge": [
                {
                    "docId": hit.get("docId"), "title": hit.get("title"),
                    "excerpt": hit.get("excerpt") or hit.get("summary"),
                    "score": hit.get("score"),
                }
                for hit in knowledge[:3]
            ],
        }
        prompt = (
            "根据以下仿真告警、遥测、规则基线和知识片段生成处置建议。"
            "只返回 JSON，字段为 summary、riskLevel、actions、confidence。"
            "actions 为 2 到 5 条中文动作；不得降低规则风险等级；不得声称已执行动作；"
            "涉及飞行控制的动作必须要求人工确认。\n"
            + json.dumps(prompt_context, ensure_ascii=False)
        )
        system = (
            "你是航空仿真监控台的辅助决策模块。知识片段仅作为依据，规则基线是安全下限。"
            "输出用于模拟验证，不替代真实飞行操作规程。"
        )
        try:
            parsed = _json_object(provider.generate(prompt, system=system))
            return self._merge(baseline, parsed, knowledge, str(config["chatModel"]))
        except Exception as error:
            return self._degraded(baseline, knowledge, f"模型调用失败: {type(error).__name__}")

    def _merge(
        self, baseline: dict[str, Any], generated: dict[str, Any],
        knowledge: list[dict[str, Any]], model: str,
    ) -> dict[str, Any]:
        baseline_risk = str(baseline.get("riskLevel") or "MEDIUM").upper()
        candidate_risk = str(generated.get("riskLevel") or baseline_risk).upper()
        risk = candidate_risk
        if self._RISK_RANK.get(candidate_risk, 0) < self._RISK_RANK.get(baseline_risk, 2):
            risk = baseline_risk
        actions = [str(item).strip() for item in generated.get("actions", []) if str(item).strip()]
        if not actions:
            actions = list(baseline.get("actions", []))
        references = [
            {"docId": hit.get("docId"), "title": hit.get("title"), "score": hit.get("score")}
            for hit in knowledge[:3]
        ]
        try:
            confidence = max(0.0, min(float(generated.get("confidence", 0.75)), 1.0))
        except (TypeError, ValueError):
            confidence = 0.75
        return {
            **baseline,
            "summary": str(generated.get("summary") or baseline.get("summary")),
            "riskLevel": risk,
            "actions": actions[:5],
            "confidence": confidence,
            "references": references,
            "provider": "规则 + RAG + 大模型",
            "providerMetadata": {
                "llmUsed": True, "model": model, "ragUsed": bool(knowledge),
                "knowledgeHits": len(knowledge), "humanConfirmationRequired": True,
                "degraded": False,
            },
        }

    @staticmethod
    def _degraded(
        baseline: dict[str, Any], knowledge: list[dict[str, Any]], reason: str
    ) -> dict[str, Any]:
        result = dict(baseline)
        result["references"] = [
            {"docId": hit.get("docId"), "title": hit.get("title"), "score": hit.get("score")}
            for hit in knowledge[:3]
        ]
        result["provider"] = "规则 + RAG（模型降级）"
        result["providerMetadata"] = {
            "llmUsed": False, "ragUsed": bool(knowledge), "knowledgeHits": len(knowledge),
            "humanConfirmationRequired": True, "degraded": True, "reason": reason,
        }
        return result
