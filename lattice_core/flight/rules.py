from __future__ import annotations

from dataclasses import dataclass

from .models import FlightFrame


@dataclass(frozen=True)
class FlightFinding:
    rule_id: str
    severity: str
    title: str
    evidence: dict
    sop_tags: tuple[str, ...]


def evaluate_flight_frame(frame: FlightFrame) -> list[FlightFinding]:
    """Small, deterministic rule layer; dataset labels remain explicitly labelled."""
    findings: list[FlightFinding] = []
    if max(abs(frame.roll_deg or 0), abs(frame.pitch_deg or 0)) >= 45:
        findings.append(FlightFinding(
            "flight.attitude-limit", "high", "Aircraft attitude exceeds safe envelope",
            {"rollDegrees": frame.roll_deg, "pitchDegrees": frame.pitch_deg},
            ("flight", "attitude", "stabilize"),
        ))
    if frame.airspeed_mps is not None and frame.airspeed_mps < 17:
        findings.append(FlightFinding(
            "flight.low-airspeed", "medium", "Fixed-wing airspeed is low",
            {"airSpeedMetersPerSecond": frame.airspeed_mps},
            ("flight", "airspeed", "stall"),
        ))
    if frame.fault_active:
        findings.append(FlightFinding(
            "dataset.fault-annotation", "high", f"Dataset fault is active: {frame.fault_type or 'unknown'}",
            {"groundTruth": True, "faultType": frame.fault_type},
            ("flight", "failure", frame.fault_type or "unknown"),
        ))
    return findings
