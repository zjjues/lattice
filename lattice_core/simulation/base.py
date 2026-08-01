from __future__ import annotations

from typing import Protocol

from lattice_core.flight.models import FlightFrame


class SimulationSink(Protocol):
    """Boundary implemented later by Cesium, Omniverse, or another simulator."""

    def publish(self, frame: FlightFrame) -> None: ...
