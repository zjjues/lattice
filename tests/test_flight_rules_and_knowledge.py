from pathlib import Path

from lattice_core.flight.adapters import AlfaAdapter
from lattice_core.flight.rules import evaluate_flight_frame
from lattice_core.knowledge import LocalKnowledgeRetriever


ROOT = Path(__file__).parents[1]


def test_fault_sample_produces_rule_findings():
    frames = AlfaAdapter(ROOT / "fixtures/flight/alfa_engine_failure_sample.csv").frames()
    findings = evaluate_flight_frame(list(frames)[-1])
    assert {finding.rule_id for finding in findings} == {"flight.low-airspeed", "dataset.fault-annotation"}


def test_local_layered_knowledge_search():
    hits = LocalKnowledgeRetriever(ROOT / "knowledge/sops").search("engine failure")
    assert hits[0]["id"] == "engine_failure"
    assert hits[0]["layer"] == "flight"
