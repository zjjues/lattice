import asyncio
import unittest

from lattice_core.events import DomainEvent, EventFactory
from lattice_core.services import IngestService, IngestServiceDependencies


class EventEnvelopeTests(unittest.TestCase):
    def test_standard_envelope_keeps_legacy_fields(self) -> None:
        payload = DomainEvent(
            event_id="EVT_1",
            event_type="entity.upserted",
            timestamp="2026-01-01T00:00:00Z",
            source="test",
            subject={"entityId": "E1"},
            data={"entity": {"entityId": "E1"}},
        ).to_dict(legacy_fields={"entityId": "E1"})
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["subject"], {"entityId": "E1"})
        self.assertEqual(payload["entityId"], "E1")

    def test_factory_creates_unique_event_ids(self) -> None:
        factory = EventFactory(lambda: "2026-01-01T00:00:00Z")
        first = factory.create("test", subject={}, data={})
        second = factory.create("test", subject={}, data={})
        self.assertNotEqual(first["eventId"], second["eventId"])


class IngestServiceTests(unittest.TestCase):
    def test_ingest_orchestrates_storage_rules_and_broadcasts(self) -> None:
        stores = {
            "events": {"events": {}},
            "entities": {"entities": {}},
            "alerts": {"alerts": {}},
        }
        broadcasts = []

        async def broadcast(value):
            broadcasts.append(value)

        event = {
            "eventId": "I1", "sourceType": "sim", "sourceId": "S1",
            "sensorContext": {}, "track": {"trackId": "E1"},
        }
        entity = {
            "entityId": "E1", "location": {"position": {
                "latitudeDegrees": 1.0, "longitudeDegrees": 2.0,
            }}, "metadata": {"track": {"speedMps": 3.0}},
        }
        rule = {"alertType": "intrusion", "riskLevel": "HIGH", "title": "t", "summary": "s", "evidence": []}
        alert = {"alertId": "A1", "entityId": "E1", "metadata": {}}

        deps = IngestServiceDependencies(
            parse_event=lambda payload: event,
            build_entity=lambda value: entity,
            evaluate_rules=lambda value, built: [rule],
            apply_threat=lambda built, rules: built,
            build_alert=lambda value, built, matched: alert,
            find_active_alert=lambda values, entity_id, alert_type: None,
            load_events=lambda: stores["events"], save_events=lambda value: None,
            load_entities=lambda: stores["entities"], save_entities=lambda value: None,
            load_alerts=lambda: stores["alerts"], save_alerts=lambda value: None,
            broadcast_entity=broadcast, broadcast_alert_created=broadcast,
            broadcast_alert_updated=broadcast, now=lambda: "now",
        )
        result = asyncio.run(IngestService(deps).ingest({"input": True}))
        self.assertEqual(result, {"ok": True, "eventId": "I1", "entityId": "E1", "alertsCreated": ["A1"]})
        self.assertIn("I1", stores["events"]["events"])
        self.assertIn("E1", stores["entities"]["entities"])
        self.assertIn("A1", stores["alerts"]["alerts"])
        self.assertEqual(broadcasts, [entity, alert])


if __name__ == "__main__":
    unittest.main()
