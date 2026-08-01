/* Minimal entity viewer. Cesium is loaded from its public distribution CDN. */
const statusNode = document.getElementById("status");
if (!window.Cesium) {
  statusNode.textContent = "Cesium failed to load (internet access is required for this MVP page).";
} else {
  const viewer = new Cesium.Viewer("map", { baseLayerPicker: false, animation: false, timeline: false });
  const aircraft = new Map();
  async function refresh() {
    try {
      const response = await fetch("/api/entities");
      const body = await response.json();
      const entities = Array.isArray(body) ? body : (body.entities || body.items || []);
      for (const item of entities) {
        const location = item.location || {};
        const lon = location.longitudeDegrees, lat = location.latitudeDegrees;
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
        const id = item.id || item.entityId || item.name;
        let marker = aircraft.get(id);
        if (!marker) {
          marker = viewer.entities.add({id, point:{pixelSize:10,color:Cesium.Color.CYAN}, label:{text:item.name || id, pixelOffset:new Cesium.Cartesian2(0,-18)}});
          aircraft.set(id, marker);
        }
        marker.position = Cesium.Cartesian3.fromDegrees(lon, lat, location.altitudeMeters || 0);
      }
      statusNode.textContent = `Entities: ${aircraft.size}`;
    } catch (error) { statusNode.textContent = `Lattice API error: ${error.message}`; }
  }
  refresh(); setInterval(refresh, 1000);
}
