from pathlib import Path

from lattice_core.flight.adapters import AlfaAdapter, IdfDsAdapter
from lattice_core.flight.mapping import frame_to_ingest_event


FIXTURES = Path(__file__).parents[1] / "fixtures" / "flight"


def test_idf_ds_adapter_and_ingest_mapping():
    frames = list(IdfDsAdapter(FIXTURES / "idf_ds_normal_sample.csv").frames())
    assert len(frames) == 3
    assert frames[0].dataset == "IDF_DS"
    event = frame_to_ingest_event(frames[0])
    assert event["track"]["platformType"] == "UAV"
    assert event["track"]["location"]["latitudeDegrees"] == frames[0].latitude_deg
    assert event["flightTelemetry"]["attitude"]["yawDegrees"] is not None


def test_alfa_fault_annotation_is_preserved():
    frames = list(AlfaAdapter(FIXTURES / "alfa_engine_failure_sample.csv").frames())
    assert frames[0].fault_active is False
    assert frames[1].fault_active is True
    event = frame_to_ingest_event(frames[1])
    assert event["flightTelemetry"]["fault"] == {"active": True, "type": "engine_failure"}
