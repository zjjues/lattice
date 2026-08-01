#!/usr/bin/env python3
"""阶段 1 应用入口：复用旧 API，并接入可替换的核心服务。"""

import json
from typing import Any

from fastapi import HTTPException, Request

import mock_server as legacy
from lattice_core.events import EventFactory
from lattice_core.services import IngestService, IngestServiceDependencies


app = legacy.app
event_factory = EventFactory(legacy.utc_now_iso)
_legacy_broadcast = legacy.connection_manager.broadcast


async def broadcast_with_envelope(message: dict[str, Any]) -> None:
    """在唯一广播出口增加标准信封，同时完整保留旧字段。"""
    if "eventId" in message and "schemaVersion" in message:
        await _legacy_broadcast(message)
        return
    event_type = str(message.get("type") or "system.event")
    subject = {
        key: str(message[key])
        for key in ("entityId", "alertId", "recommendationId", "taskId", "objectId")
        if message.get(key) is not None
    }
    data = {
        key: value for key, value in message.items()
        if key not in {"type", "timestamp", *subject.keys()}
    }
    await _legacy_broadcast(event_factory.create(
        event_type, subject=subject, data=data, legacy_fields=message,
    ))


legacy.connection_manager.broadcast = broadcast_with_envelope


async def broadcast_entity(entity: dict[str, Any]) -> None:
    await legacy.connection_manager.broadcast({
        "type": "entity.upserted", "entityId": entity["entityId"],
        "entity": entity, "timestamp": legacy.utc_now_iso(),
    })


def build_entity_with_flight_telemetry(event: dict[str, Any]) -> dict[str, Any]:
    entity = legacy.build_entity_from_ingest_event(event)
    raw = event.get("raw", {})
    telemetry = raw.get("flightTelemetry") if isinstance(raw, dict) else None
    if isinstance(telemetry, dict):
        entity["flightTelemetry"] = telemetry
    return entity


def evaluate_rules_with_flight_telemetry(
    event: dict[str, Any], entity: dict[str, Any]
) -> list[dict[str, Any]]:
    rules = legacy.evaluate_rules(event, entity)
    raw = event.get("raw", {})
    telemetry = raw.get("flightTelemetry") if isinstance(raw, dict) else None
    if not isinstance(telemetry, dict):
        return rules
    attitude = telemetry.get("attitude", {})
    velocity = telemetry.get("velocity", {})
    fault = telemetry.get("fault", {})
    roll = attitude.get("rollDegrees") if isinstance(attitude, dict) else None
    pitch = attitude.get("pitchDegrees") if isinstance(attitude, dict) else None
    airspeed = velocity.get("airSpeedMetersPerSecond") if isinstance(velocity, dict) else None
    evidence = [f"dataset={telemetry.get('dataset', 'unknown')}"]
    if any(isinstance(value, (int, float)) and abs(value) >= 45 for value in (roll, pitch)):
        rules.append({
            "alertType": "flight_attitude_limit", "riskLevel": "HIGH",
            "title": "飞行姿态超出安全包线",
            "summary": "横滚角或俯仰角超过验证阈值，请核验遥测并在飞行器限制范围内恢复稳定。",
            "evidence": evidence + [f"横滚角={roll}，俯仰角={pitch}，阈值=45度"],
        })
    if isinstance(airspeed, (int, float)) and airspeed < 17:
        rules.append({
            "alertType": "flight_low_airspeed", "riskLevel": "MEDIUM",
            "title": "固定翼飞行器空速偏低",
            "summary": "空速低于验证阈值，请核验传感器有效性并检查飞行器能量状态。",
            "evidence": evidence + [f"空速={airspeed:.1f}米/秒，阈值=17.0米/秒"],
        })
    if isinstance(fault, dict) and fault.get("active"):
        fault_name = {"engine_failure": "发动机故障"}.get(fault.get("type"), fault.get("type") or "未知")
        rules.append({
            "alertType": "dataset_fault_annotation", "riskLevel": "HIGH",
            "title": f"数据集故障标注：{fault_name}",
            "summary": "源数据集将当前帧标记为故障状态；这是样本真值，并非模型检测结果。",
            "evidence": evidence + ["样本真值=是", f"故障类型={fault_name}"],
        })
    return rules


ingest_service = IngestService(IngestServiceDependencies(
    parse_event=legacy.parse_ingest_event,
    build_entity=build_entity_with_flight_telemetry,
    evaluate_rules=evaluate_rules_with_flight_telemetry,
    apply_threat=legacy.update_entity_threat_from_alerts,
    build_alert=legacy.build_alert_from_rule,
    find_active_alert=legacy.find_active_alert,
    load_events=legacy.load_ingest_events_store,
    save_events=legacy.save_ingest_events_store,
    load_entities=legacy.read_store,
    save_entities=legacy.write_store,
    load_alerts=legacy.load_alerts_store,
    save_alerts=legacy.save_alerts_store,
    broadcast_entity=broadcast_entity,
    broadcast_alert_created=legacy.broadcast_alert_created,
    broadcast_alert_updated=legacy.broadcast_alert_updated,
    now=legacy.utc_now_iso,
))


app.router.routes = [
    route for route in app.router.routes
    if not (
        getattr(route, "path", None) == "/api/v1/ingest/events"
        and "POST" in getattr(route, "methods", set())
    )
]


@app.post("/api/v1/ingest/events")
async def ingest_event(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from error
    return await ingest_service.ingest(payload)


from pathlib import Path

from lattice_core.flight.recommendations import (
    FlightRuleRecommendationProvider,
    LayeredFlightKnowledgeRetriever,
)
from lattice_core.recommendations import (
    RecommendationNotFoundError,
    RecommendationService,
    RecommendationServiceDependencies,
)


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
    retriever=LayeredFlightKnowledgeRetriever(
        legacy.search_local_knowledge_base, Path("knowledge/sops")
    ),
    provider=FlightRuleRecommendationProvider(legacy.call_dify_recommendation),
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


from fastapi.responses import HTMLResponse


@app.get("/monitor", response_class=HTMLResponse)
def flight_monitor_console() -> HTMLResponse:
    html = Path("static/unified-console.html").read_text(encoding="utf-8")
    html = html.replace("北京低空飞行态势", "飞行态势监控台")
    html = html.replace("Fake Lattice · 飞行态势监控台", "飞行态势监控台")
    html = html.replace(
        "const esc=v=>String(v??'-')",
        "const zh={HIGH:'高风险',MEDIUM:'中风险',LOW:'低风险',engine_failure:'发动机故障',dataset_fault_annotation:'数据集故障标注',flight_low_airspeed:'低空速告警',flight_attitude_limit:'姿态越界告警','flight-rule-sop':'飞行规则与处置预案'};const esc=v=>String(zh[String(v)]??v??'-')",
    )
    html = html.replace(
        "risk.textContent=highest",
        "risk.textContent=({HIGH:'高风险',MEDIUM:'中风险',LOW:'低风险'})[highest]||highest",
    )
    html = html.replace(
        "${threat?'· HIGH':''}",
        "${threat?'· 高风险':''}",
    )
    return HTMLResponse(html)


from lattice_core.demo import run_minimal_validation


@app.post("/api/v1/demo/minimal-validation")
async def minimal_validation_demo() -> dict[str, Any]:
    return await run_minimal_validation(
        project_root=Path(__file__).resolve().parent,
        ingest_service=ingest_service,
        recommendation_service=recommendation_service,
        load_alerts=legacy.load_alerts_store,
    )


import os

from fastapi import File, Form, UploadFile

from lattice_core.rag import RagKnowledgeBase, embedding_from_env


rag_data_dir = Path(os.getenv("RAG_DATA_DIR", Path(__file__).resolve().parent / "data/rag"))
rag_knowledge_base = RagKnowledgeBase(rag_data_dir / "rag.sqlite3", embedding_from_env())
from lattice_core.knowledge.catalog import KnowledgeBaseCatalog
knowledge_base_catalog = KnowledgeBaseCatalog(Path("knowledge/sops"), rag_data_dir / "knowledge_bases.json")
knowledge_base_catalog.sync(rag_knowledge_base.list_documents())



@app.get("/api/v1/rag/documents")
def list_rag_documents() -> dict[str, Any]:
    return {
        "embeddingProvider": rag_knowledge_base.embedding.name,
        "embeddingDimension": rag_knowledge_base.embedding.dimension,
        "documents": rag_knowledge_base.list_documents(),
    }


@app.post("/api/v1/rag/documents")
async def upload_rag_document(
    file: UploadFile = File(...),
    chunk_size: int = Form(600),
    overlap: int = Form(100),
) -> dict[str, Any]:
    suffix = Path(file.filename or "document.txt").suffix.lower()
    if suffix not in {".txt", ".md", ".json", ".csv"}:
        raise HTTPException(status_code=400, detail="当前支持 TXT、Markdown、JSON 和 CSV")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="单个文档不能超过 10MB")
    try:
        return rag_knowledge_base.add_document(
            Path(file.filename or "document.txt").name,
            content, file.content_type, chunk_size, overlap,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/v1/rag/documents/{document_id}/chunks")
def list_rag_chunks(document_id: str) -> dict[str, Any]:
    try:
        document = rag_knowledge_base.get_document(document_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="文档不存在") from error
    return {"document": document, "chunks": rag_knowledge_base.chunks(document_id)}


@app.get("/api/v1/rag/search")
def search_rag(q: str, limit: int = 5) -> dict[str, Any]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="检索问题不能为空")
    return {"query": q, "results": rag_knowledge_base.search(q, limit)}


import asyncio

from lattice_core.model_config import ModelProviderConfigStore, OpenAICompatibleModelClient
from lattice_core.rag import FastEmbedEmbedding, LOCAL_BGE_MODEL, OpenAICompatibleEmbedding


model_config_store = ModelProviderConfigStore(
    Path(os.getenv("MODEL_CONFIG_PATH", Path(__file__).resolve().parent / "data/model_provider.json"))
)

BGE_CACHE_DIR = Path(os.getenv("BGE_CACHE_DIR", "/mnt/d/lattice-data/models/fastembed"))


def _embedding_provider(private: dict[str, Any]):
    if private.get("embeddingModel") == LOCAL_BGE_MODEL:
        return FastEmbedEmbedding(BGE_CACHE_DIR)
    return OpenAICompatibleEmbedding(
        private["baseUrl"], private.get("apiKey", ""), private["embeddingModel"],
        int(private.get("embeddingDimension") or 0),
    )


def _apply_saved_embedding_provider() -> None:
    private = model_config_store.load_private()
    if private.get("embeddingModel") and (private.get("baseUrl") or private.get("embeddingModel") == LOCAL_BGE_MODEL):
        rag_knowledge_base.embedding = _embedding_provider(private)


_apply_saved_embedding_provider()

# 保持现有 recommendation API、广播与前端格式，仅替换检索和生成实现。
from lattice_core.decision import RagRecommendationRetriever, RuleRagLlmRecommendationProvider

_layered_retriever = recommendation_service._retriever
_rule_provider = recommendation_service._provider
recommendation_service._retriever = RagRecommendationRetriever(
    rag_knowledge_base, _layered_retriever
)
recommendation_service._provider = RuleRagLlmRecommendationProvider(
    _rule_provider, model_config_store.load_private
)


def _model_client(payload: dict[str, Any]) -> OpenAICompatibleModelClient:
    saved = model_config_store.load_private()
    return OpenAICompatibleModelClient(
        str(payload.get("baseUrl") or saved.get("baseUrl") or ""),
        str(payload.get("apiKey") or saved.get("apiKey") or ""),
    )


@app.get("/api/v1/model-provider/config")
def get_model_provider_config() -> dict[str, Any]:
    return model_config_store.public()


@app.put("/api/v1/model-provider/config")
async def save_model_provider_config(request: Request) -> dict[str, Any]:
    payload = await request.json()
    try:
        public = model_config_store.save(payload)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    private = model_config_store.load_private()
    if private.get("embeddingModel"):
        rag_knowledge_base.embedding = _embedding_provider(private)
    return public


@app.post("/api/v1/model-provider/discover")
async def discover_models(request: Request) -> dict[str, Any]:
    payload = await request.json()
    try:
        models = await asyncio.to_thread(_model_client(payload).discover)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if LOCAL_BGE_MODEL not in models["embedding"]:
        models["embedding"].insert(0, LOCAL_BGE_MODEL)
    return {"ok": True, "models": models}


@app.post("/api/v1/model-provider/test")
async def test_model_capability(request: Request) -> dict[str, Any]:
    payload = await request.json()
    capability = str(payload.get("capability") or "")
    model = str(payload.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="请选择要测试的模型")
    if capability == "embedding" and model == LOCAL_BGE_MODEL:
        provider = FastEmbedEmbedding(BGE_CACHE_DIR)
        vector = (await asyncio.to_thread(provider.embed, ["飞行安全知识库连接测试"]))[0]
        return {"ok": True, "capability": "embedding", "model": model, "dimension": len(vector), "provider": provider.name}
    try:
        client = _model_client(payload)



        if capability == "chat":
            return await asyncio.to_thread(client.test_chat, model)
        if capability == "embedding":
            return await asyncio.to_thread(client.test_embedding, model)
        raise ValueError("未知的模型能力类型")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


# 态势传感器数据保留在 D 盘；接口按需返回小型快照。
from lattice_core.flight.sensors import Px4UlogSensorAdapter, build_situation_snapshot

SENSOR_DATA_ROOT = Path(os.getenv("SENSOR_DATA_ROOT", "/mnt/d/lattice-data/datasets"))
PX4_SAMPLE_PATH = Path(os.getenv("PX4_SAMPLE_PATH", SENSOR_DATA_ROOT / "px4/sample.ulg"))
OPENSKY_SAMPLE_PATH = Path(
    os.getenv("OPENSKY_SAMPLE_PATH", SENSOR_DATA_ROOT / "opensky/beijing-states.json")
)


@app.get("/api/v1/situation/{entity_id}")
def get_situation_snapshot(entity_id: str) -> dict[str, Any]:
    entity = legacy.read_store().get("entities", {}).get(entity_id)
    if not isinstance(entity, dict):
        raise HTTPException(status_code=404, detail=f"飞行目标不存在: {entity_id}")
    return build_situation_snapshot(entity, OPENSKY_SAMPLE_PATH)


@app.get("/api/v1/situation-samples")
async def get_situation_samples() -> dict[str, Any]:
    px4 = await asyncio.to_thread(Px4UlogSensorAdapter(PX4_SAMPLE_PATH).snapshot)
    return {
        "storageRoot": str(SENSOR_DATA_ROOT),
        "px4": px4,
        "openSky": {
            "available": OPENSKY_SAMPLE_PATH.is_file(),
            "fileName": OPENSKY_SAMPLE_PATH.name,
        },
    }


@app.get("/api/v1/knowledge-bases")
def list_knowledge_bases() -> dict[str, Any]:
    return {
        "embeddingProvider": rag_knowledge_base.embedding.name,
        "knowledgeBases": knowledge_base_catalog.list(rag_knowledge_base.list_documents()),
    }


@app.post("/api/v1/knowledge-bases")
async def create_knowledge_base(request: Request) -> dict[str, Any]:
    payload = await request.json()
    try:
        return knowledge_base_catalog.create(
            str(payload.get("name") or ""), str(payload.get("description") or "")
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/v1/knowledge-bases/{knowledge_base_id}")
def get_knowledge_base(knowledge_base_id: str) -> dict[str, Any]:
    try:
        return knowledge_base_catalog.get(knowledge_base_id, rag_knowledge_base.list_documents())
    except KeyError as error:
        raise HTTPException(status_code=404, detail="知识库不存在") from error


@app.post("/api/v1/knowledge-bases/{knowledge_base_id}/documents")
async def upload_knowledge_base_document(
    knowledge_base_id: str,
    file: UploadFile = File(...),
    chunk_size: int = Form(600),
    overlap: int = Form(100),
) -> dict[str, Any]:
    suffix = Path(file.filename or "document.txt").suffix.lower()
    if suffix not in {".txt", ".md", ".json", ".csv"}:
        raise HTTPException(status_code=400, detail="当前支持 TXT、Markdown、JSON 和 CSV")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="单个文档不能超过 10MB")
    try:
        target = knowledge_base_catalog.store_file(
            knowledge_base_id, Path(file.filename or "document.txt").name, content
        )
        document = await asyncio.to_thread(
            rag_knowledge_base.add_document, target.name, content, file.content_type, chunk_size, overlap
        )
        knowledge_base_catalog.register_document(document["id"], knowledge_base_id)
        return {**document, "knowledgeBaseId": knowledge_base_id}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="知识库不存在") from error
    except (UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/v1/knowledge-bases/{knowledge_base_id}/search")
def search_knowledge_base(knowledge_base_id: str, q: str, limit: int = 5) -> dict[str, Any]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="检索问题不能为空")
    try:
        document_ids = knowledge_base_catalog.document_ids(knowledge_base_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="知识库不存在") from error
    results = [item for item in rag_knowledge_base.search(q, 20) if item["documentId"] in document_ids]
    return {"query": q, "results": results[:max(1, min(limit, 20))]}
