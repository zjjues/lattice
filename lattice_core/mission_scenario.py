"""Deterministic multi-domain demo scenario and integration boundary contracts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Protocol


class DeviceRegistry(Protocol):
    """Compatible boundary for a Kubernetes-backed device management service."""

    def list_devices(self) -> list[dict[str, Any]]: ...


class EventTransport(Protocol):
    """Transport boundary implementable by in-process events or Fast DDS."""

    def publish(self, topic: str, payload: dict[str, Any]) -> None: ...


@dataclass
class ScenarioRuntime:
    step: int = -1
    trigger_type: str = "unknown_air_target"
    stage_started_at: float = 0.0
    plan_execution: dict[str, Any] | None = field(default=None)
    execution_started_at: float = 0.0

    def reset(self) -> dict[str, Any]:
        self.step = -1
        self.stage_started_at = monotonic()
        self.plan_execution = None
        self.execution_started_at = 0.0
        return self.snapshot()

    def trigger(self, trigger_type: str) -> dict[str, Any]:
        self.trigger_type = trigger_type if trigger_type in _TRIGGERS else "unknown_air_target"
        self.step = 0
        self.stage_started_at = monotonic()
        self.plan_execution = None
        return self.snapshot()

    def back(self) -> dict[str, Any]:
        if self.step > 0:
            self.step -= 1
            self.stage_started_at = monotonic()
        self.plan_execution = None
        return self.snapshot()

    def execute_plan(self, plan_id: str, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("执行方案必须由人类明确确认")
        if self.step != len(_STAGES) - 1:
            raise ValueError("仅可在模型辅助研判完成后执行方案")
        plan = next((item for item in _DECISION["plans"] if item["planId"] == plan_id), None)
        if plan is None:
            raise ValueError("未知方案")
        self.plan_execution = {
            "planId": plan_id, "title": plan["title"], "status": "SIMULATED",
            "message": "演示执行已记录；未向真实设备或外部系统下发命令。",
            "humanConfirmed": True,
            "platformIds": _PLAN_PLATFORMS[plan_id],
            "effect": deepcopy(_PLAN_EFFECTS[plan_id]),
        }
        self.execution_started_at = monotonic()
        return self.snapshot()
    def advance(self) -> dict[str, Any]:
        if self.step < 0:
            return self.snapshot()
        self.step = min(self.step + 1, len(_STAGES) - 1)
        self.stage_started_at = monotonic()
        self.plan_execution = None
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        stages = deepcopy(_STAGES)
        elapsed_ms = max(0, int((monotonic() - self.stage_started_at) * 1000)) if self.step >= 0 else 0
        for index, stage in enumerate(stages):
            stage.update(deepcopy(_STAGE_DETAILS[stage["stageId"]]))
            stage["status"] = "completed" if index < self.step else "active" if index == self.step else "pending"
            skills = stage.get("skillCalls", [])
            knowledge = stage.get("knowledgeHits", [])
            if index < self.step:
                stage["skillExecutions"] = _execution_records(skills, 999999, 450, "skill")
                stage["knowledgeExecutions"] = _execution_records(knowledge, 999999, 350, "knowledge", len(skills) * 450)
            elif index == self.step:
                stage["skillExecutions"] = _execution_records(skills, elapsed_ms, 450, "skill")
                stage["knowledgeExecutions"] = _execution_records(knowledge, elapsed_ms, 350, "knowledge", len(skills) * 450)
            else:
                stage["skillExecutions"] = []
                stage["knowledgeExecutions"] = []
        platforms = deepcopy(_PLATFORMS)
        monitoring = self.step < 0
        active_stage = ({
            "stageId": "monitoring", "name": "持续监控", "actor": "Fake Lattice",
            "skill": "多域态势守望", "summary": "装备保持巡航，各传感器持续上报，等待外部事件触发任务。",
            "confidence": 0.0, "evidence": ["8 个平台在线", "24 路传感器持续更新"],
            "platformIds": [], "skillCalls": [], "knowledgeHits": [], "status": "monitoring",
        } if monitoring else stages[self.step])
        if not monitoring:
            active_stage.update(deepcopy(_STAGE_DETAILS[active_stage["stageId"]]))
        assigned = set(active_stage.get("platformIds", []))
        for platform in platforms:
            platform["missionStatus"] = "tasked" if platform["platformId"] in assigned else "monitoring"
            platform["telemetry"] = _platform_telemetry(platform, self.step)
            for sensor_index, sensor in enumerate(platform["sensors"]):
                quality = int(float(sensor["quality"]) * 100)
                sensor["trend"] = [max(35, min(100, quality + offset)) for offset in (-5, -2, 1, -1, 2, 0)]
                sensor["channel"] = f"sensor.observation/{platform['platformId']}/{sensor_index + 1}"
        plan_execution = deepcopy(self.plan_execution)
        if plan_execution:
            simulation_elapsed_ms = max(0, int((monotonic() - self.execution_started_at) * 1000))
            plan_execution["elapsedMs"] = simulation_elapsed_ms
            plan_execution["progress"] = min(100, int(simulation_elapsed_ms / 72))
            plan_execution["phase"] = min(3, simulation_elapsed_ms // 1800)
            if plan_execution["progress"] >= 100:
                plan_execution["message"] = plan_execution["effect"]["summary"]
        return {
            "scenarioId": "joint-air-sea-demo-01",
            "name": "空海协同感知与决策演示",
            "domain": "AIR_SEA",
            "step": self.step,
            "stageElapsedMs": elapsed_ms,
            "mode": "MONITORING" if monitoring else "MISSION",
            "complete": self.step == len(stages) - 1,
            "trigger": deepcopy(_TRIGGERS[self.trigger_type]) if not monitoring else None,
            "triggerOptions": [
                {"triggerType": key, "name": value["name"], "description": value["description"]}
                for key, value in _TRIGGERS.items()
            ],
            "integration": {
                "deviceRegistry": "in-memory",
                "deviceRegistryContract": "KubernetesDeviceRegistry/v1",
                "eventTransport": "in-process",
                "eventTransportContract": "FastDDS MissionEvent/v1",
            },
            "platforms": platforms,
            "threat": deepcopy(_TRIGGERS[self.trigger_type]["target"]),
            "stages": stages,
            "activeStage": active_stage,
            "decision": deepcopy(_DECISION) if self.step == len(stages) - 1 else None,
            "planExecution": plan_execution,
        }


def _execution_records(names: list[str], elapsed_ms: int, interval_ms: int, kind: str, offset_ms: int = 0) -> list[dict[str, Any]]:
    records = []
    for index, name in enumerate(names):
        start = offset_ms + index * interval_ms
        end = start + interval_ms
        status = "SUCCESS" if elapsed_ms >= end else "RUNNING" if elapsed_ms >= start else "QUEUED"
        records.append({
            "name": name, "displayName": _SKILL_DISPLAY_NAMES.get(name, name),
            "status": status, "kind": kind,
            "durationMs": interval_ms - 70 + (sum(ord(ch) for ch in name) % 120) if status == "SUCCESS" else None,
            "result": (f"返回 {2 + index} 个相关片段" if kind == "knowledge" else "调用完成") if status == "SUCCESS" else None,
        })
    return records

def _platform_telemetry(platform: dict[str, Any], step: int) -> dict[str, Any]:
    seed = sum(ord(character) for character in platform["platformId"])
    air = platform["domain"] == "AIR"
    return {
        "speed": round((28 + seed % 34 if air else 6 + seed % 8) + step * .4, 1),
        "speedUnit": "m/s", "altitude": platform["position"]["altitudeM"],
        "heading": (platform["heading"] + step * 3) % 360,
        "battery": 92 - seed % 13 - step, "linkQuality": 96 - seed % 9,
        "latencyMs": 24 + seed % 31, "computeLoad": 31 + seed % 39,
        "temperatureC": 38 + seed % 18,
        "positionAccuracyM": round(0.8 + (seed % 17) / 10, 1),
    }

def _sensor(sensor_id: str, sensor_type: str, value: str, quality: int, source: str) -> dict[str, Any]:
    return {
        "sensorId": sensor_id, "type": sensor_type, "status": "NOMINAL",
        "displayValue": value, "quality": quality / 100,
        "freshnessMs": 80 + (100 - quality) * 7,
        "provenance": {"source": source, "license": "open-data/sample"},
    }


_PLATFORMS = [
    {"platformId": "uav-rq01", "name": "远程侦察无人机 01", "kind": "HALE_UAV", "domain": "AIR", "symbol": "△", "color": "#46d5ef", "position": {"x": 28, "y": 25, "altitudeM": 8200}, "heading": 72, "sensors": [_sensor("eo-01", "光电/红外", "目标热斑 3 个", 72, "VisDrone/合成样本"), _sensor("sar-01", "合成孔径雷达", "条带模式 18 km", 91, "OpenSARShip/合成样本"), _sensor("imu-01", "惯导", "R 1.4° / P -0.8°", 97, "PX4 ULog")]},
    {"platformId": "uav-ea02", "name": "电子侦察无人机 02", "kind": "ELINT_UAV", "domain": "AIR", "symbol": "◇", "color": "#62b5ff", "position": {"x": 42, "y": 17, "altitudeM": 6400}, "heading": 118, "sensors": [_sensor("esm-02", "电子支援", "未知辐射源 9.7 GHz", 64, "RadioML/合成样本"), _sensor("gnss-02", "卫星定位", "定位精度 1.8 m", 95, "PX4 ULog"), _sensor("imu-02", "惯导", "R -2.1° / P 0.4°", 96, "PX4 ULog")]},
    {"platformId": "uav-lo03", "name": "低空侦察无人机 03", "kind": "VTOL_UAV", "domain": "AIR", "symbol": "✦", "color": "#73e1bd", "position": {"x": 36, "y": 47, "altitudeM": 1200}, "heading": 41, "sensors": [_sensor("eo-03", "可见光相机", "4K / 30 fps", 94, "VisDrone"), _sensor("lidar-03", "激光雷达", "有效距离 5.2 km", 88, "SemanticKITTI/合成样本"), _sensor("baro-03", "气压计", "101.2 kPa", 96, "PX4 ULog")]},
    {"platformId": "uav-relay04", "name": "通信中继无人机 04", "kind": "RELAY_UAV", "domain": "AIR", "symbol": "⬡", "color": "#8ea9ff", "position": {"x": 18, "y": 52, "altitudeM": 5100}, "heading": 95, "sensors": [_sensor("link-04", "数据链", "吞吐 82 Mbps", 93, "ns-3/合成样本"), _sensor("spectrum-04", "频谱监测", "链路余量 18 dB", 89, "RadioML/合成样本"), _sensor("gnss-04", "卫星定位", "定位精度 2.1 m", 95, "PX4 ULog")]},
    {"platformId": "fighter-05", "name": "有人侦察机 05", "kind": "MANNED_ISR", "domain": "AIR", "symbol": "▲", "color": "#b4d6ff", "position": {"x": 61, "y": 22, "altitudeM": 9300}, "heading": 226, "sensors": [_sensor("radar-05", "机载雷达", "跟踪目标 12", 96, "OpenSky/合成样本"), _sensor("iff-05", "敌我识别", "询问响应正常", 98, "合成样本"), _sensor("rwr-05", "雷达告警", "无直接照射", 92, "RadioML/合成样本")]},
    {"platformId": "usv-06", "name": "无人水面艇 06", "kind": "USV", "domain": "SEA", "symbol": "◆", "color": "#38cfa4", "position": {"x": 54, "y": 73, "altitudeM": 0}, "heading": 330, "sensors": [_sensor("surface-radar-06", "海面搜索雷达", "海杂波中等", 86, "OpenSARShip/合成样本"), _sensor("ais-06", "AIS", "邻近船舶 7", 95, "AIS 开放样本"), _sensor("sonar-06", "被动声呐", "未识别低频特征", 69, "ShipsEar/合成样本")]},
    {"platformId": "usv-07", "name": "无人水面艇 07", "kind": "USV", "domain": "SEA", "symbol": "◆", "color": "#54d6bd", "position": {"x": 72, "y": 66, "altitudeM": 0}, "heading": 278, "sensors": [_sensor("eo-07", "桅杆光电", "能见度 16 km", 90, "SeaShips/合成样本"), _sensor("ais-07", "AIS", "目标无 AIS 响应", 88, "AIS 开放样本"), _sensor("weather-07", "气象", "风速 8.4 m/s", 97, "NOAA 开放数据") ]},
    {"platformId": "uuv-08", "name": "无人潜航器 08", "kind": "UUV", "domain": "UNDERSEA", "symbol": "●", "color": "#69a7ce", "position": {"x": 65, "y": 84, "altitudeM": -80}, "heading": 302, "sensors": [_sensor("sonar-08", "侧扫声呐", "疑似航迹方位 312°", 78, "Marine Debris/合成样本"), _sensor("depth-08", "深度计", "80.4 m", 98, "WHOI/合成样本"), _sensor("ins-08", "水下惯导", "漂移估计 0.7%", 91, "PX4/合成样本")]},
]

_TRIGGERS = {
    "unknown_air_target": {"name": "发现未知空中目标", "description": "远程侦察平台报告弱雷达回波和间歇辐射信号。", "target": {"targetId": "unknown-air-t01", "name": "未知空中目标 T-01", "position": {"x": 69, "y": 48}, "classification": "待确认", "confidence": 0.38, "evidence": ["弱雷达回波", "间歇性未知辐射源"]}},
    "unidentified_surface_vessel": {"name": "发现无 AIS 海面目标", "description": "无人水面艇发现高速航迹，但未收到有效 AIS 应答。", "target": {"targetId": "unknown-sea-t02", "name": "未知海面目标 T-02", "position": {"x": 73, "y": 68}, "classification": "无 AIS 响应", "confidence": 0.42, "evidence": ["海面雷达高速航迹", "无 AIS 应答"]}},
    "spectrum_anomaly": {"name": "发现异常电磁辐射", "description": "电子侦察无人机发现间歇性宽带辐射，位置和属性尚不完整。", "target": {"targetId": "spectrum-t03", "name": "异常辐射源 T-03", "position": {"x": 56, "y": 39}, "classification": "未知辐射源", "confidence": 0.31, "evidence": ["宽带突发信号", "测向交汇区域较大"]}},
}
_THREAT = {"targetId": "unknown-t01", "name": "未知空海目标 T-01", "position": {"x": 69, "y": 48}, "classification": "待确认", "confidence": 0.38, "evidence": ["弱雷达回波", "间歇性未知辐射源"]}
_DECISION = {
    "provider": "已配置大模型 / 规则约束降级可用", "title": "保持多源跟踪并实施分级核验",
    "summary": "融合结果支持将 T-01 标记为高关注未知目标，但证据尚不足以自动升级处置。建议维持安全距离，继续由光电、电子侦察和海面雷达交叉验证，并提交人工指挥席确认。",
    "actions": [
        "远程侦察无人机保持广域 SAR 跟踪，更新周期调整为 5 秒。",
        "电子侦察无人机持续采集 9.7 GHz 辐射特征并执行指纹比对。",
        "低空侦察无人机在安全距离外获取两组不同方位的光电证据。",
        "无人水面艇保持伴随监视并核验 AIS、海面雷达与光电结果。",
        "融合置信度达到 95% 前不得执行自动处置，最终方案必须人工批准。",
    ],
    "citations": ["目标识别规则库 / 弱目标多源确认", "空海协同预案库 / 分级监视", "治理规范库 / 人工审批约束"],
    "plans": [
        {"planId": "plan-monitor", "priority": 1, "title": "持续多源监视并人工核验", "risk": "低", "recommended": True, "summary": "维持安全距离，继续融合雷达、光电和电子侦察证据。", "actions": ["保持广域跟踪", "增加两组交叉观测", "提交人工指挥席复核"]},
        {"planId": "plan-reposition", "priority": 2, "title": "调整传感器编组扩大探测", "risk": "中", "recommended": False, "summary": "重新分配空中与海面传感器位置，提高几何交汇精度。", "actions": ["调整侦察平台站位", "启用备用数据链", "重新执行多源融合"]},
        {"planId": "plan-handover", "priority": 3, "title": "保持距离并转交上级研判", "risk": "低", "recommended": False, "summary": "保持当前监控态势，将完整证据包转交外部人工研判。", "actions": ["冻结当前证据快照", "生成可追溯情报包", "等待上级人工指令"]},
    ],
}

_PLAN_PLATFORMS = {"plan-monitor": ["uav-rq01", "uav-ea02", "uav-lo03", "usv-07"], "plan-reposition": ["uav-ea02", "uav-lo03", "usv-06"], "plan-handover": ["uav-rq01", "uav-relay04"]}
_PLAN_EFFECTS = {
    "plan-monitor": {"label": "monitoring-loop", "summary": "Simulation complete: target continuously tracked; identification confidence reached 97%; no physical strike performed.", "targetStatus": "TRACKED", "confidence": 0.97},
    "plan-reposition": {"label": "precision-improved", "summary": "Simulation complete: localization error reduced to 0.8 km; intelligence completeness reached 96%.", "targetStatus": "LOCATED", "confidence": 0.96},
    "plan-handover": {"label": "command-handover", "summary": "Simulation complete: evidence package handed over; local platforms remain in shadow tracking.", "targetStatus": "SHADOWED", "confidence": 0.93},
}
_STAGES = [
    {"stageId": "detect", "name": "初始发现", "actor": "远程侦察无人机 01", "platformIds": ["uav-rq01"], "skill": "多源弱目标检测", "summary": "SAR 在海空交界区域发现弱回波，仅获得粗略方位与速度。", "confidence": 0.38, "evidence": ["弱雷达回波", "位置误差 ±12 km"]},
    {"stageId": "task", "name": "协同任务编排", "actor": "Fake Lattice", "platformIds": ["uav-ea02", "uav-lo03", "usv-07"], "skill": "传感器能力匹配", "summary": "根据距离、覆盖范围和传感器质量，分配电子侦察、光电和海面观测资源。", "confidence": 0.48, "evidence": ["能力目录匹配", "链路可用率 93%"]},
    {"stageId": "refine", "name": "多源精确探测", "actor": "无人装备集群", "platformIds": ["uav-ea02", "uav-lo03", "usv-06", "usv-07"], "skill": "航迹关联与证据融合", "summary": "电子特征、光电图像与海面雷达航迹完成时空关联。", "confidence": 0.82, "evidence": ["9.7 GHz 辐射特征", "光电轮廓匹配", "无 AIS 响应"]},
    {"stageId": "rag", "name": "知识检索增强", "actor": "RAG 知识服务", "platformIds": [], "skill": "分层知识库检索", "summary": "检索识别规则、空海协同预案和人工确认约束，形成可追溯依据。", "confidence": 0.88, "evidence": ["目标识别规则库", "协同处置预案库", "人工审批规范"]},
    {"stageId": "decision", "name": "模型辅助研判", "actor": "大模型决策服务", "platformIds": [], "skill": "规则约束生成", "summary": "建议保持监视、扩大传感器交叉验证并请求人工确认；演示系统不执行自主处置。", "confidence": 0.91, "evidence": ["规则校验通过", "引用 3 条知识片段", "必须人工确认"]},
]
_SKILL_DISPLAY_NAMES = {
    "sar_weak_target_detector": "多源弱目标检测",
    "track_seed_builder": "初始航迹生成",
    "capability_matcher": "装备能力匹配",
    "coverage_optimizer": "传感器覆盖优化",
    "route_deconfliction": "航路冲突消解",
    "elint_fingerprint_match": "电磁指纹匹配",
    "eo_target_classifier": "光电目标分类",
    "multi_sensor_track_fusion": "多传感器航迹融合",
    "embedding_search": "向量知识检索",
    "evidence_reranker": "证据相关性重排",
    "citation_builder": "引用依据构建",
    "rag_context_builder": "检索上下文构建",
    "rule_guardrail": "规则约束校验",
    "llm_recommendation_generator": "大模型建议生成",
}
_STAGE_DETAILS = {
    "detect": {"skillCalls": ["sar_weak_target_detector", "track_seed_builder"], "knowledgeHits": ["传感器规则库 / SAR 弱回波判定"]},
    "task": {"skillCalls": ["capability_matcher", "coverage_optimizer", "route_deconfliction"], "knowledgeHits": ["装备能力库 / 传感器覆盖范围", "协同规则库 / 多平台任务分配"]},
    "refine": {"skillCalls": ["elint_fingerprint_match", "eo_target_classifier", "multi_sensor_track_fusion"], "knowledgeHits": ["目标特征库 / 辐射源指纹", "识别规则库 / 无 AIS 目标核验"]},
    "rag": {"skillCalls": ["embedding_search", "evidence_reranker", "citation_builder"], "knowledgeHits": ["目标识别规则库 / 弱目标多源确认", "空海协同预案库 / 分级监视", "治理规范库 / 人工审批约束"]},
    "decision": {"skillCalls": ["rag_context_builder", "rule_guardrail", "llm_recommendation_generator"], "knowledgeHits": ["空海协同预案库 / 分级监视", "治理规范库 / 人工审批约束"]},
}
