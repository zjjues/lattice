import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import app
from lattice_core.flight.adapters import AlfaAdapter
from lattice_core.flight.mapping import frame_to_ingest_event


class FlightHttpPipelineTests(unittest.TestCase):
    def test_fault_frame_reaches_entity_and_rules(self):
        path = Path(__file__).parents[1] / "fixtures/flight/alfa_engine_failure_sample.csv"
        frame = list(AlfaAdapter(path, source_id="flight-http-test").frames())[-1]
        client = TestClient(app)
        response = client.post("/api/v1/ingest/events", json=frame_to_ingest_event(frame))
        self.assertEqual(response.status_code, 200, response.text)
        entity = client.get("/api/v1/entities/flight-http-test").json()
        self.assertTrue(entity["flightTelemetry"]["fault"]["active"])
        alerts = client.get("/api/v1/alerts").json()
        items = alerts if isinstance(alerts, list) else alerts.get("items", alerts.get("alerts", []))
        kinds = {item["alertType"] for item in items if item.get("entityId") == "flight-http-test"}
        self.assertIn("flight_low_airspeed", kinds)
        self.assertIn("dataset_fault_annotation", kinds)


if __name__ == "__main__":
    unittest.main()
