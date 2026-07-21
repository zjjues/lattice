const DEFAULT_CENTER = [33.69447852698943, -117.9173785693163];
const DEFAULT_ZOOM = 11;

const entities = new Map();
const markers = new Map();
const trackHistories = new Map();
const alerts = new Map();
const recommendations = new Map();
let mapOverlays = null;
const tasks = new Map();
const objects = new Map();
const TASK_STATUSES = ["ASSIGNED", "ACCEPTED", "IN_PROGRESS", "SUCCEEDED", "FAILED", "CANCELED"];
const ALERT_STATUSES = ["OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"];
let map;
let overlayLayerEl;
let markerLayerEl;
let trackLayerEl;
let mapPopupEl;
let mapCenterLabelEl;
let selectedEntityId = null;
let emphasizedEntityId = null;
let emphasizeTimer = null;
let streamSocket;
let reconnectTimer;

const wsStatusEl = document.getElementById("ws-status");
const systemStatusEl = document.getElementById("system-status");
const situationStatusEl = document.getElementById("situation-status");
const entityCountEl = document.getElementById("entity-count");
const lastEventEl = document.getElementById("last-event");
const alertCountEl = document.getElementById("alert-count");
const alertListEl = document.getElementById("alert-list");
const recommendationCountEl = document.getElementById("recommendation-count");
const recommendationListEl = document.getElementById("recommendation-list");
const taskCountEl = document.getElementById("task-count");
const taskActiveCountEl = document.getElementById("task-active-count");
const taskListEl = document.getElementById("task-list");
const refreshTasksButton = document.getElementById("refresh-tasks");
const entityListCountEl = document.getElementById("entity-list-count");
const entityListEl = document.getElementById("entity-list");
const summaryEntitiesEl = document.getElementById("summary-entities");
const summaryOpenAlertsEl = document.getElementById("summary-open-alerts");
const summaryHighAlertsEl = document.getElementById("summary-high-alerts");
const summaryRecommendationsEl = document.getElementById("summary-recommendations");
const summaryTotalTasksEl = document.getElementById("summary-total-tasks");
const summaryActiveTasksEl = document.getElementById("summary-active-tasks");
const panelResizerEl = document.getElementById("panel-resizer");
const currentEventCardEl = document.getElementById("current-event-card");

const PANEL_WIDTH_STORAGE_KEY = "fake-lattice-task-panel-width";
const PANEL_COLLAPSE_STORAGE_KEY = "fake-lattice-collapsed-panels";
const PANEL_ORDER_STORAGE_KEY = "fake-lattice-panel-order";

function updateSummaryStrip() {
  if (summaryEntitiesEl) {
    summaryEntitiesEl.textContent = String(entities.size);
  }

  if (summaryOpenAlertsEl) {
    const openAlerts = [...alerts.values()].filter((alert) => alert?.status === "OPEN").length;
    summaryOpenAlertsEl.textContent = String(openAlerts);
  }

  if (summaryHighAlertsEl) {
    const highRiskAlerts = [...alerts.values()].filter((alert) => alert?.riskLevel === "HIGH").length;
    summaryHighAlertsEl.textContent = String(highRiskAlerts);
  }

  if (summaryRecommendationsEl) {
    summaryRecommendationsEl.textContent = String(recommendations.size);
  }

  if (summaryTotalTasksEl) {
    summaryTotalTasksEl.textContent = String(tasks.size);
  }

  if (summaryActiveTasksEl) {
    const activeTasks = getActiveTaskCount();
    summaryActiveTasksEl.textContent = String(activeTasks);
  }
}

function updateTopStatusSummary() {
  if (systemStatusEl) {
    const activeTasks = getActiveTaskCount();
    const openAlerts = [...alerts.values()].filter((alert) => alert?.status === "OPEN").length;
    if (activeTasks > 0) {
      systemStatusEl.textContent = `任务执行中（${activeTasks}）`;
    } else if (openAlerts > 0) {
      systemStatusEl.textContent = `告警待处置（${openAlerts}）`;
    } else if (entities.size > 0) {
      systemStatusEl.textContent = "态势监控中";
    } else {
      systemStatusEl.textContent = "空闲";
    }
  }

  if (situationStatusEl) {
    const highRiskAlerts = [...alerts.values()].filter((alert) => alert?.riskLevel === "HIGH").length;
    const recommendationCount = recommendations.size;
    if (entities.size === 0) {
      situationStatusEl.textContent = "暂无目标";
    } else if (highRiskAlerts > 0) {
      situationStatusEl.textContent = `${entities.size} 个目标 / ${highRiskAlerts} 个高风险告警`;
    } else if (recommendationCount > 0) {
      situationStatusEl.textContent = `${entities.size} 个目标 / ${recommendationCount} 条建议`;
    } else {
      situationStatusEl.textContent = `${entities.size} 个目标 / 监控正常`;
    }
  }
}

function getActiveTaskCount() {
  return [...tasks.values()].filter((task) => {
    return task?.status === "ASSIGNED" || task?.status === "ACCEPTED" || task?.status === "IN_PROGRESS";
  }).length;
}

function setWebSocketStatus(status) {
  wsStatusEl.textContent = status;
}

function setLastEvent(message) {
  lastEventEl.textContent = message;
}

function updateEntityCount() {
  entityCountEl.textContent = String(markers.size);
  if (entityListCountEl) {
    entityListCountEl.textContent = String(entities.size);
  }
  updateSummaryStrip();
  updateTopStatusSummary();
  renderCurrentEventPanel();
}

function updateTaskCount() {
  taskCountEl.textContent = String(tasks.size);
  if (taskActiveCountEl) {
    taskActiveCountEl.textContent = String(getActiveTaskCount());
  }
  updateSummaryStrip();
  updateTopStatusSummary();
  renderCurrentEventPanel();
}

function updateAlertCount() {
  if (alertCountEl) {
    alertCountEl.textContent = String(alerts.size);
  }
  updateSummaryStrip();
  updateTopStatusSummary();
  renderCurrentEventPanel();
}

function updateRecommendationCount() {
  if (recommendationCountEl) {
    recommendationCountEl.textContent = String(recommendations.size);
  }
  updateSummaryStrip();
  updateTopStatusSummary();
  renderCurrentEventPanel();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function valueOrDash(value) {
  if (value === undefined || value === null || value === "") {
    return "-";
  }
  return value;
}

function normalizeForSignature(value) {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeForSignature(item));
  }

  if (value && typeof value === "object") {
    return Object.keys(value)
      .filter((key) => value[key] !== undefined)
      .sort()
      .reduce((accumulator, key) => {
        accumulator[key] = normalizeForSignature(value[key]);
        return accumulator;
      }, {});
  }

  return value;
}

function stableStringify(value) {
  return JSON.stringify(normalizeForSignature(value));
}

async function sha256Hex(value) {
  if (!window.crypto?.subtle) {
    throw new Error("浏览器不支持 crypto.subtle");
  }

  const buffer = await window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function buildRecommendationStateSnapshot(alert, entity) {
  const alertMetadata = alert?.metadata && typeof alert.metadata === "object" ? alert.metadata : {};
  const entityMetadata = entity?.metadata && typeof entity.metadata === "object" ? entity.metadata : {};
  const track = entityMetadata.track && typeof entityMetadata.track === "object" ? entityMetadata.track : {};
  const threat = entityMetadata.threat && typeof entityMetadata.threat === "object" ? entityMetadata.threat : {};
  const position = entity?.location?.position && typeof entity.location.position === "object" ? entity.location.position : {};

  return {
    alert: {
      alertId: alert?.alertId,
      alertType: alert?.alertType,
      riskLevel: alert?.riskLevel,
      title: alert?.title,
      summary: alert?.summary,
      status: alert?.status,
      evidence: Array.isArray(alert?.evidence) ? alert.evidence : [],
      zone: alertMetadata.zone,
      speedMps: alertMetadata.speedMps,
      tags: Array.isArray(alertMetadata.tags) ? alertMetadata.tags : [],
      operatorNote: alertMetadata.operatorNote,
    },
    entity: {
      entityId: entity?.entityId,
      specificType: entity?.ontology?.specificType,
      environment: entity?.milView?.environment,
      location: {
        latitudeDegrees: position.latitudeDegrees,
        longitudeDegrees: position.longitudeDegrees,
        altitudeMeters: position.altitudeMeters,
      },
      track: {
        speedMps: track.speedMps,
        headingDegrees: track.headingDegrees,
        identity: track.identity,
      },
      threat: {
        threatLevel: threat.threatLevel,
        anomalyType: threat.anomalyType,
        recommendation: threat.recommendation,
        zone: threat.zone,
        tags: Array.isArray(threat.tags) ? threat.tags : [],
      },
    },
  };
}

async function computeRecommendationStateSignature(alert, entity) {
  return sha256Hex(stableStringify(buildRecommendationStateSnapshot(alert, entity)));
}

function getInitialMapView() {
  const params = new URLSearchParams(window.location.search);
  const latitude = Number(params.get("lat"));
  const longitude = Number(params.get("lon"));
  const zoom = Number(params.get("zoom"));

  if (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
  ) {
    return {
      center: [latitude, longitude],
      zoom: Number.isFinite(zoom) ? zoom : DEFAULT_ZOOM,
    };
  }

  return {
    center: DEFAULT_CENTER,
    zoom: DEFAULT_ZOOM,
  };
}

function domIdFor(prefix, value) {
  return `${prefix}-${String(value ?? "")
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")}`;
}

function sortObjectsByCreatedAtDesc(objectList) {
  return [...objectList].sort((left, right) => {
    const leftTime = Date.parse(left?.createdAt || "") || 0;
    const rightTime = Date.parse(right?.createdAt || "") || 0;
    return rightTime - leftTime;
  });
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "-";
  }

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getAisValue(entity, key) {
  // 兼容几种本地 mock 可能出现的 AIS 扩展字段位置。
  return (
    entity?.metadata?.ais?.[key] ??
    entity?.metadata?.[key] ??
    entity?.extensions?.ais?.[key] ??
    entity?.extensions?.[key]
  );
}

function getThreatValue(entity, key) {
  return entity?.metadata?.threat?.[key];
}

function getEntityName(entity) {
  return entity?.aliases?.name || entity?.entityId || "未命名目标";
}

function formatSensorSources(entity) {
  const sensorSources = getThreatValue(entity, "sensorSources");
  if (Array.isArray(sensorSources)) {
    return sensorSources.join(" / ");
  }
  return sensorSources;
}

function getLatLng(entity) {
  const position = entity?.location?.position;
  const latitude = Number(position?.latitudeDegrees);
  const longitude = Number(position?.longitudeDegrees);

  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    latitude < -90 ||
    latitude > 90 ||
    longitude < -180 ||
    longitude > 180
  ) {
    console.warn("entity 缺少合法经纬度，已跳过", entity);
    return null;
  }

  return [latitude, longitude];
}

function getObjectsForEntity(entityId) {
  return sortObjectsByCreatedAtDesc(
    [...objects.values()].filter((objectMetadata) => {
      return objectMetadata?.relatedEntityId === entityId;
    }),
  );
}

function getObjectsForTask(taskId) {
  return sortObjectsByCreatedAtDesc(
    [...objects.values()].filter((objectMetadata) => {
      return objectMetadata?.relatedTaskId === taskId;
    }),
  );
}

function getAlertsForEntity(entityId) {
  return [...alerts.values()]
    .filter((alert) => alert?.entityId === entityId)
    .sort((left, right) => {
      const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
      return rightTime - leftTime;
    });
}

function getAlertRiskBadge(riskLevel) {
  return String(riskLevel || "UNKNOWN").toLowerCase();
}

function getRecommendationsForAlert(alertId) {
  return [...recommendations.values()]
    .filter((recommendation) => recommendation?.alertId === alertId)
    .sort((left, right) => {
      const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
      return rightTime - leftTime;
    });
}

function getLatestRecommendationForAlert(alertId) {
  return getRecommendationsForAlert(alertId)[0] || null;
}

function getLatestRecommendation() {
  return [...recommendations.values()].sort((left, right) => {
    const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
    const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
    return rightTime - leftTime;
  })[0] || null;
}

function getAlertByEntityId(entityId) {
  return [...alerts.values()]
    .filter((alert) => alert?.entityId === entityId)
    .sort((left, right) => {
      const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
      return rightTime - leftTime;
    })[0] || null;
}

function getPriorityOpenAlert() {
  return [...alerts.values()]
    .filter((alert) => alert?.status === "OPEN")
    .sort((left, right) => {
      const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };
      const riskDelta = (rank[right?.riskLevel] || 0) - (rank[left?.riskLevel] || 0);
      if (riskDelta !== 0) {
        return riskDelta;
      }
      const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
      return rightTime - leftTime;
    })[0] || null;
}

function getLatestTask() {
  return [...tasks.values()].sort((left, right) => {
    const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
    const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
    return rightTime - leftTime;
  })[0] || null;
}

function scrollElementIntoView(element) {
  if (!element) {
    return;
  }
  element.scrollIntoView({ behavior: "smooth", block: "center" });
  element.classList.add("flash-highlight");
  window.setTimeout(() => {
    element.classList.remove("flash-highlight");
  }, 1600);
}

function ensurePanelExpanded(targetId) {
  const button = document.querySelector(`.panel-toggle-button[data-panel-target="${CSS.escape(targetId)}"]`);
  if (!button) {
    return;
  }
  if (button.getAttribute("aria-expanded") === "false") {
    button.click();
  }
}

function scrollPanelSection(panelSelector, targetId) {
  const section = document.querySelector(panelSelector);
  if (!section) {
    return;
  }
  ensurePanelExpanded(targetId);
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function handleSummaryAction(action) {
  if (action === "current-target") {
    const entityId = getPrimaryEntityId();
    if (!entityId) {
      return;
    }
    ensurePanelExpanded("entities");
    const card = entityListEl?.querySelector(`[data-entity-id="${CSS.escape(entityId)}"]`);
    if (card) {
      scrollElementIntoView(card);
    }
    focusEntity(entityId);
    return;
  }

  if (action === "open-alerts" || action === "high-alerts") {
    ensurePanelExpanded("alerts");
    const alert = action === "high-alerts"
      ? [...alerts.values()].filter((item) => item?.status === "OPEN" && item?.riskLevel === "HIGH")
          .sort((left, right) => {
            const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
            const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
            return rightTime - leftTime;
          })[0] || getPriorityOpenAlert()
      : getPriorityOpenAlert();
    scrollPanelSection(".alert-panel", "alerts");
    if (alert?.alertId) {
      scrollAlertIntoView(alert.alertId, alert.entityId);
    }
    return;
  }

  if (action === "recommendations") {
    ensurePanelExpanded("recommendations");
    const recommendation = getLatestRecommendation();
    scrollPanelSection(".recommendation-panel", "recommendations");
    if (recommendation?.recommendationId) {
      scrollRecommendationIntoView(recommendation.recommendationId, recommendation.entityId);
    }
    return;
  }

  if (action === "tasks" || action === "active-tasks") {
    ensurePanelExpanded("tasks");
    const task = action === "active-tasks"
      ? [...tasks.values()].filter((item) => item?.status === "ASSIGNED" || item?.status === "ACCEPTED" || item?.status === "IN_PROGRESS")
          .sort((left, right) => {
            const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
            const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
            return rightTime - leftTime;
          })[0] || getLatestTask()
      : getLatestTask();
    scrollPanelSection(".task-workflow-panel", "tasks");
    if (task?.taskId) {
      const card = taskListEl?.querySelector(`[data-task-id="${CSS.escape(task.taskId)}"]`);
      if (card) {
        scrollElementIntoView(card);
      }
      if (task.relatedEntityId) {
        focusEntity(task.relatedEntityId);
      }
    }
    return;
  }
}

function renderLocalMapShell() {
  const mapEl = document.getElementById("map");
  mapEl.innerHTML = `
    <div class="local-map-grid" aria-hidden="true">
      <span></span><span></span><span></span><span></span>
    </div>
    <div class="local-map-overlay">
      <div class="map-title">
        <strong>本地态势图</strong>
        <span id="map-center-label"></span>
      </div>
      <div class="map-note">离线渲染，不依赖外部地图瓦片</div>
    </div>
    <div class="map-legend" aria-label="地图图例">
      <div class="map-legend-title">图例</div>
      <div class="map-legend-items">
        <div class="map-legend-item">
          <span class="legend-swatch legend-area"></span>
          <span>警戒区</span>
        </div>
        <div class="map-legend-item">
          <span class="legend-swatch legend-track-high"></span>
          <span>高风险轨迹</span>
        </div>
        <div class="map-legend-item">
          <span class="legend-swatch legend-track-medium"></span>
          <span>中风险轨迹</span>
        </div>
        <div class="map-legend-item">
          <span class="legend-dot legend-marker-high"></span>
          <span>高风险目标</span>
        </div>
        <div class="map-legend-item">
          <span class="legend-dot legend-marker-normal"></span>
          <span>一般目标</span>
        </div>
      </div>
    </div>
    <svg class="local-overlay-layer" aria-hidden="true"></svg>
    <svg class="local-track-layer" aria-hidden="true"></svg>
    <div class="local-marker-layer"></div>
    <div class="local-map-popup" hidden></div>
  `;
  overlayLayerEl = mapEl.querySelector(".local-overlay-layer");
  trackLayerEl = mapEl.querySelector(".local-track-layer");
  markerLayerEl = mapEl.querySelector(".local-marker-layer");
  mapPopupEl = mapEl.querySelector(".local-map-popup");
  mapCenterLabelEl = mapEl.querySelector("#map-center-label");
}

function updateMapCenterLabel() {
  if (!mapCenterLabelEl || !map?.center) {
    return;
  }
  mapCenterLabelEl.textContent = `${map.center[0].toFixed(4)}, ${map.center[1].toFixed(4)} / zoom ${map.zoom}`;
}

function getMapDegreeSpan() {
  const zoom = Number(map?.zoom) || DEFAULT_ZOOM;
  const baseSpan = 0.42;
  const span = baseSpan / Math.pow(2, Math.max(0, zoom - DEFAULT_ZOOM));
  return Math.max(span, 0.018);
}

function projectLatLng(latLng) {
  const [latitude, longitude] = latLng;
  const [centerLat, centerLon] = map.center;
  const latSpan = getMapDegreeSpan();
  const lonSpan = latSpan * 1.35;
  const x = 50 + ((longitude - centerLon) / lonSpan) * 100;
  const y = 50 - ((latitude - centerLat) / latSpan) * 100;
  return {
    x: Math.min(96, Math.max(4, x)),
    y: Math.min(94, Math.max(6, y)),
    clipped: x < 4 || x > 96 || y < 6 || y > 94,
  };
}

function updateMarkerPosition(marker) {
  const projection = projectLatLng(marker.latLng);
  marker.element.style.left = `${projection.x}%`;
  marker.element.style.top = `${projection.y}%`;
  marker.element.classList.toggle("is-clipped", projection.clipped);
}

function updateAllMarkerPositions() {
  renderOverlayLayer();
  renderTrackLayer();
  markers.forEach(updateMarkerPosition);
  updateMapCenterLabel();
}

function renderOverlayLayer() {
  if (!overlayLayerEl) {
    return;
  }

  const restrictedArea = mapOverlays?.restrictedArea;
  if (!restrictedArea) {
    overlayLayerEl.innerHTML = "";
    return;
  }

  const topLeft = projectLatLng([restrictedArea.maxLat, restrictedArea.minLon]);
  const bottomRight = projectLatLng([restrictedArea.minLat, restrictedArea.maxLon]);
  const x = Math.min(topLeft.x, bottomRight.x);
  const y = Math.min(topLeft.y, bottomRight.y);
  const width = Math.max(0.6, Math.abs(bottomRight.x - topLeft.x));
  const height = Math.max(0.6, Math.abs(bottomRight.y - topLeft.y));

  overlayLayerEl.innerHTML = `
    <rect class="restricted-area-rect" x="${x}" y="${y}" width="${width}" height="${height}"></rect>
    <rect class="restricted-area-badge-bg" x="${x + 0.8}" y="${Math.max(0.6, y - 2.2)}" rx="0.6" ry="0.6" width="9.2" height="2.4"></rect>
    <text class="restricted-area-label" x="${x + 1.2}" y="${Math.max(2, y - 0.75)}">预设警戒区</text>
  `;
}

function projectHistoryPoint(point) {
  return projectLatLng([point.latitudeDegrees, point.longitudeDegrees]);
}

function renderTrackLayer() {
  if (!trackLayerEl) {
    return;
  }

  const polylines = [];
  const pointsMarkup = [];
  const arrowMarkup = [];

  trackHistories.forEach((history, entityId) => {
    if (!Array.isArray(history) || history.length < 2) {
      return;
    }
    const entity = entities.get(entityId);
    const threatLevel = String(getThreatValue(entity, "threatLevel") || "unknown").toLowerCase();
    const projected = history.map(projectHistoryPoint);
    const points = projected.map((point) => `${point.x},${point.y}`).join(" ");
    polylines.push(
      `<polyline class="track-line threat-${escapeHtml(threatLevel)} ${selectedEntityId === entityId ? "is-selected" : ""} ${emphasizedEntityId === entityId ? "is-emphasized" : ""}" points="${escapeHtml(points)}"></polyline>`,
    );
    projected.forEach((point) => {
      pointsMarkup.push(
        `<circle class="track-point threat-${escapeHtml(threatLevel)}" cx="${point.x}" cy="${point.y}" r="0.55"></circle>`,
      );
    });

    const end = projected[projected.length - 1];
    const prev = projected[projected.length - 2];
    const dx = end.x - prev.x;
    const dy = end.y - prev.y;
    const length = Math.hypot(dx, dy) || 1;
    const ux = dx / length;
    const uy = dy / length;
    const baseX = end.x - ux * 1.5;
    const baseY = end.y - uy * 1.5;
    const leftX = baseX + uy * 0.8;
    const leftY = baseY - ux * 0.8;
    const rightX = baseX - uy * 0.8;
    const rightY = baseY + ux * 0.8;
    arrowMarkup.push(
      `<polygon class="track-arrow threat-${escapeHtml(threatLevel)} ${selectedEntityId === entityId ? "is-selected" : ""}" points="${end.x},${end.y} ${leftX},${leftY} ${rightX},${rightY}"></polygon>`,
    );
  });

  trackLayerEl.innerHTML = `${polylines.join("")}${pointsMarkup.join("")}${arrowMarkup.join("")}`;
}

function formatReference(reference) {
  if (!reference) {
    return { title: "无", excerpt: "" };
  }
  if (typeof reference === "string") {
    return { title: reference, excerpt: "" };
  }
  return {
    title: reference.title || reference.docId || "未命名依据",
    excerpt: reference.excerpt || reference.summary || "",
  };
}

function formatConfidence(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return `${Math.round(numeric * 100)}%`;
}

function formatLatLng(latLng) {
  if (!latLng) {
    return "-";
  }
  return `${latLng[0].toFixed(4)}, ${latLng[1].toFixed(4)}`;
}

function compactText(value, maxLength = 70) {
  const text = String(valueOrDash(value));
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}...`;
}

function getPrimaryEntityId() {
  if (selectedEntityId && entities.has(selectedEntityId)) {
    return selectedEntityId;
  }

  const priorityAlert = [...alerts.values()]
    .filter((alert) => alert?.status === "OPEN")
    .sort((left, right) => {
      const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };
      const riskDelta = (rank[right?.riskLevel] || 0) - (rank[left?.riskLevel] || 0);
      if (riskDelta !== 0) {
        return riskDelta;
      }
      const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
      return rightTime - leftTime;
    })[0];

  if (priorityAlert?.entityId && entities.has(priorityAlert.entityId)) {
    return priorityAlert.entityId;
  }

  return [...entities.keys()][0] || null;
}

function renderCurrentEventPanel() {
  if (!currentEventCardEl) {
    return;
  }

  const entityId = getPrimaryEntityId();
  if (!entityId) {
    currentEventCardEl.innerHTML = '<div class="current-event-empty">当前没有正在跟踪的目标或事件。</div>';
    return;
  }

  const entity = entities.get(entityId);
  const alert = getAlertByEntityId(entityId);
  const recommendation = alert ? getLatestRecommendationForAlert(alert.alertId) : null;
  const task = getSelectedEntityTaskSummary(entityId);
  const threatLevel = String(getThreatValue(entity, "threatLevel") || alert?.riskLevel || "LOW").toUpperCase();
  const latLng = getLatLng(entity);

  currentEventCardEl.innerHTML = `
    <div class="current-event-body">
      <div class="current-event-top">
        <div>
          <h3>${escapeHtml(getEntityName(entity))}</h3>
          <p class="current-event-subtitle">${escapeHtml(compactText(alert?.summary || recommendation?.summary || "当前目标正在持续监控中。", 92))}</p>
        </div>
        <div class="current-event-badges">
          <span class="current-event-badge risk-${escapeHtml(threatLevel.toLowerCase())}">${escapeHtml(threatLevel)}</span>
          ${task ? `<span class="current-event-badge">${escapeHtml(valueOrDash(task.status))}</span>` : ""}
        </div>
      </div>
      <div class="current-event-actions">
        <button type="button" class="current-event-button" data-action="focus-entity">定位目标</button>
        <button type="button" class="current-event-button primary" data-action="generate-recommendation" ${alert ? "" : "disabled"}>生成建议</button>
        <button type="button" class="current-event-button" data-action="create-task" ${recommendation ? "" : "disabled"}>创建任务</button>
      </div>
      <details class="current-event-details">
        <summary>展开详情</summary>
        <dl class="current-event-summary-grid">
          <div class="current-event-info">
            <dt>当前告警</dt>
            <dd>${escapeHtml(compactText(alert?.title || "无", 42))}</dd>
          </div>
          <div class="current-event-info">
            <dt>当前位置</dt>
            <dd>${escapeHtml(formatLatLng(latLng))}</dd>
          </div>
          <div class="current-event-info">
            <dt>当前建议</dt>
            <dd>${escapeHtml(compactText(recommendation?.summary || "未生成建议", 58))}</dd>
          </div>
          <div class="current-event-info">
            <dt>当前任务</dt>
            <dd>${escapeHtml(compactText(task?.description || task?.title || "未创建任务", 58))}</dd>
          </div>
        </dl>
      </details>
    </div>
  `;

  currentEventCardEl.querySelector('[data-action="focus-entity"]')?.addEventListener("click", () => {
    focusEntity(entityId);
  });
  currentEventCardEl.querySelector('[data-action="generate-recommendation"]')?.addEventListener("click", () => {
    emphasizeEntity(entityId);
    if (alert?.alertId) {
      generateRecommendationForAlert(alert.alertId);
    }
  });
  currentEventCardEl.querySelector('[data-action="create-task"]')?.addEventListener("click", () => {
    emphasizeEntity(entityId);
    if (recommendation?.recommendationId) {
      createTaskFromRecommendation(recommendation.recommendationId);
    }
  });
}

function buildRecommendationRationale(recommendation, alert, references) {
  const rationale = [];
  const riskLevel = String(recommendation?.riskLevel || alert?.riskLevel || "").toUpperCase();
  const confidence = formatConfidence(recommendation?.confidence);

  if (alert?.summary) {
    rationale.push(`当前事件研判为“${alert.summary}”`);
  }

  if (riskLevel === "HIGH") {
    rationale.push("当前风险等级较高，优先建议持续跟踪并快速复核目标身份");
  } else if (riskLevel === "MEDIUM") {
    rationale.push("当前风险等级为中等，建议持续观察并补充更多识别信息");
  }

  if (confidence !== "-") {
    rationale.push(`当前建议置信度约为 ${confidence}`);
  }

  if (references.length > 0) {
    rationale.push(`已匹配 ${references.length} 条预案或案例，可作为当前处置依据`);
  }

  return rationale;
}

function getSelectedEntityTaskSummary(entityId) {
  const relatedTasks = [...tasks.values()]
    .filter((task) => task?.relatedEntityId === entityId)
    .sort((left, right) => {
      const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
      return rightTime - leftTime;
    });

  if (relatedTasks.length === 0) {
    return null;
  }

  const activeTask = relatedTasks.find((task) => task?.status === "IN_PROGRESS" || task?.status === "ASSIGNED");
  return activeTask || relatedTasks[0];
}

function buildSelectedMarkerStatusHtml(entityId) {
  const entity = entities.get(entityId);
  if (!entity) {
    return "";
  }

  const threatLevel = String(getThreatValue(entity, "threatLevel") || "LOW").toUpperCase();
  const latestAlert = getAlertByEntityId(entityId);
  const latestRecommendation = latestAlert ? getLatestRecommendationForAlert(latestAlert.alertId) : null;
  const latestTask = getSelectedEntityTaskSummary(entityId);
  const badges = [`<span class="marker-status-badge risk-${escapeHtml(threatLevel.toLowerCase())}">${escapeHtml(threatLevel)}</span>`];

  if (latestRecommendation) {
    badges.push('<span class="marker-status-badge recommendation">已生成建议</span>');
  }
  if (latestTask) {
    badges.push(`<span class="marker-status-badge task">${escapeHtml(valueOrDash(latestTask.status))}</span>`);
  }

  const lines = [];
  if (latestAlert?.title) {
    lines.push(`<p>${escapeHtml(latestAlert.title)}</p>`);
  }
  if (latestRecommendation?.summary) {
    lines.push(`<p>${escapeHtml(latestRecommendation.summary)}</p>`);
  }
  if (latestTask?.metadata?.selectedAction || latestTask?.description) {
    lines.push(
      `<p>任务动作：${escapeHtml(valueOrDash(latestTask.metadata?.selectedAction || latestTask.description))}</p>`,
    );
  }

  return `
    <div class="marker-status-content">
      <div class="marker-status-badges">${badges.join("")}</div>
      ${lines.join("")}
    </div>
  `;
}

function updateSelectedMarkerStatus() {
  markers.forEach((marker, entityId) => {
    const statusEl = marker.element.querySelector(".marker-status");
    if (!statusEl) {
      return;
    }
    if (selectedEntityId !== entityId) {
      statusEl.hidden = true;
      statusEl.innerHTML = "";
      return;
    }
    statusEl.hidden = false;
    statusEl.innerHTML = buildSelectedMarkerStatusHtml(entityId);
  });
}

function emphasizeEntity(entityId) {
  if (!entityId || !markers.has(entityId)) {
    return;
  }

  emphasizedEntityId = entityId;
  markers.forEach((marker, nextEntityId) => {
    marker.element.classList.toggle("is-emphasized", nextEntityId === entityId);
  });
  renderTrackLayer();

  if (emphasizeTimer) {
    window.clearTimeout(emphasizeTimer);
  }

  emphasizeTimer = window.setTimeout(() => {
    emphasizedEntityId = null;
    markers.forEach((marker) => marker.element.classList.remove("is-emphasized"));
    renderTrackLayer();
    emphasizeTimer = null;
  }, 2200);
}

function showEntityPopup(entityId) {
  const marker = markers.get(entityId);
  const entity = entities.get(entityId);
  if (!marker || !entity || !mapPopupEl) {
    setLastEvent(`找不到对应 entity ${entityId}`);
    return;
  }

  selectedEntityId = entityId;
  markers.forEach((nextMarker, nextEntityId) => {
    nextMarker.element.classList.toggle("is-selected", nextEntityId === entityId);
  });
  renderTrackLayer();
  updateSelectedMarkerStatus();
  renderCurrentEventPanel();

  const projection = projectLatLng(marker.latLng);
  mapPopupEl.innerHTML = buildPopupHtml(entity);
  mapPopupEl.hidden = false;
  mapPopupEl.style.left = `${projection.x}%`;
  mapPopupEl.style.top = `${projection.y}%`;

  mapPopupEl.querySelector(".create-task-button")?.addEventListener("click", () => {
    createTaskForEntity(entityId);
  });
  const uploadButton = mapPopupEl.querySelector('.object-upload-button[data-upload-context="entity"]');
  uploadButton?.addEventListener("click", () => {
    uploadObjectForEntity(
      entityId,
      uploadButton.dataset.fileInputId,
      uploadButton.dataset.descriptionInputId,
    );
  });
  bindObjectActions(mapPopupEl);
}

function hideEntityPopup() {
  selectedEntityId = null;
  markers.forEach((marker) => {
    marker.element.classList.remove("is-selected");
  });
  renderTrackLayer();
  updateSelectedMarkerStatus();
  renderCurrentEventPanel();
  if (mapPopupEl) {
    mapPopupEl.hidden = true;
    mapPopupEl.innerHTML = "";
  }
}

function renderObjectList(objectList) {
  if (objectList.length === 0) {
    return '<p class="object-empty">暂无附件</p>';
  }

  return `
    <div class="object-list">
      ${objectList
        .map((objectMetadata) => {
          const objectId = valueOrDash(objectMetadata.objectId);
          return `
            <article class="object-item">
              <div class="object-item-title">${escapeHtml(valueOrDash(objectMetadata.filename))}</div>
              <dl class="object-fields">
                <div>
                  <dt>objectId</dt>
                  <dd>${escapeHtml(objectId)}</dd>
                </div>
                <div>
                  <dt>contentType</dt>
                  <dd>${escapeHtml(valueOrDash(objectMetadata.contentType))}</dd>
                </div>
                <div>
                  <dt>sizeBytes</dt>
                  <dd>${escapeHtml(formatBytes(objectMetadata.sizeBytes))}</dd>
                </div>
                <div>
                  <dt>description</dt>
                  <dd>${escapeHtml(valueOrDash(objectMetadata.description))}</dd>
                </div>
                <div>
                  <dt>createdAt</dt>
                  <dd>${escapeHtml(valueOrDash(objectMetadata.createdAt))}</dd>
                </div>
              </dl>
              <div class="object-actions">
                <button type="button" class="object-download-button" data-object-id="${escapeHtml(objectId)}">下载</button>
                <button type="button" class="object-delete-button" data-object-id="${escapeHtml(objectId)}">删除</button>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderObjectUploadForm(context, relatedId) {
  const fileInputId = domIdFor(`${context}-object-file`, relatedId);
  const descriptionInputId = domIdFor(`${context}-object-description`, relatedId);

  return `
    <div class="object-upload">
      <input id="${escapeHtml(fileInputId)}" class="object-file-input" type="file" />
      <input
        id="${escapeHtml(descriptionInputId)}"
        class="object-description-input"
        type="text"
        placeholder="附件描述"
      />
      <button
        type="button"
        class="object-upload-button"
        data-upload-context="${escapeHtml(context)}"
        data-related-id="${escapeHtml(relatedId)}"
        data-file-input-id="${escapeHtml(fileInputId)}"
        data-description-input-id="${escapeHtml(descriptionInputId)}"
      >上传附件</button>
    </div>
  `;
}

function buildPopupHtml(entity) {
  const entityId = valueOrDash(entity?.entityId);
  const relatedAlerts = getAlertsForEntity(entityId);
  const latestAlert = relatedAlerts[0] || null;
  const latestRecommendation = latestAlert ? getLatestRecommendationForAlert(latestAlert.alertId) : null;
  const sensorSources = getThreatValue(entity, "sensorSources");
  const rows = [
    ["entityId", entityId],
    ["名称", entity?.aliases?.name],
    ["MMSI", getAisValue(entity, "mmsi")],
    ["速度", getAisValue(entity, "speedKnots")],
    ["航向", getAisValue(entity, "courseDegrees")],
    ["威胁等级", getThreatValue(entity, "threatLevel")],
    ["异常类型", getThreatValue(entity, "anomalyType")],
    ["最新告警", latestAlert?.title],
    ["传感器", Array.isArray(sensorSources) ? sensorSources.join(" / ") : sensorSources],
    ["处置建议", latestRecommendation?.summary || getThreatValue(entity, "recommendation")],
    ["更新时间", entity?.provenance?.sourceUpdateTime],
  ];

  const rowHtml = rows
    .map(([label, value]) => {
      return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(valueOrDash(value))}</dd></div>`;
    })
    .join("");
  const relatedObjects = getObjectsForEntity(entityId);

  return `
    <section class="entity-popup">
      <h2>${escapeHtml(valueOrDash(entity?.aliases?.name || entity?.entityId))}</h2>
      <dl>${rowHtml}</dl>
      <button class="create-task-button" type="button" data-entity-id="${escapeHtml(entityId)}">
        创建处置任务
      </button>
      <section class="popup-alerts">
        <h3>关联告警</h3>
        ${
          relatedAlerts.length === 0
            ? '<p class="object-empty">暂无告警</p>'
            : `
        <div class="inline-alert-list">
          ${relatedAlerts
            .slice(0, 3)
            .map((alert) => {
              return `
            <article class="inline-alert-item risk-${escapeHtml(getAlertRiskBadge(alert.riskLevel))}">
              <strong>${escapeHtml(valueOrDash(alert.title))}</strong>
              <span>${escapeHtml(valueOrDash(alert.status))}</span>
            </article>
          `;
            })
            .join("")}
        </div>`
        }
      </section>
      <section class="popup-objects">
        <h3>关联附件</h3>
        ${renderObjectUploadForm("entity", entityId)}
        ${renderObjectList(relatedObjects)}
      </section>
    </section>
  `;
}

function bindObjectActions(container) {
  container.querySelectorAll(".object-download-button").forEach((button) => {
    button.addEventListener("click", () => {
      downloadObject(button.dataset.objectId);
    });
  });

  container.querySelectorAll(".object-delete-button").forEach((button) => {
    button.addEventListener("click", () => {
      deleteObjectById(button.dataset.objectId);
    });
  });
}

function bindPopupActions(marker, entityId) {
  marker.element.addEventListener("click", () => {
    showEntityPopup(entityId);
  });
}

function upsertMarker(entity) {
  const entityId = entity?.entityId;
  if (!entityId) {
    console.warn("entity 缺少 entityId，已跳过", entity);
    return;
  }

  entities.set(entityId, entity);

  const latLng = getLatLng(entity);
  if (!latLng) {
    return;
  }

  let marker = markers.get(entityId);
  if (!marker) {
    const markerElement = document.createElement("button");
    markerElement.type = "button";
    markerElement.className = `local-marker threat-${String(getThreatValue(entity, "threatLevel") || "unknown").toLowerCase()}`;
    markerElement.title = getEntityName(entity);
    markerElement.innerHTML = `
      <span class="marker-dot"></span>
      <span class="marker-label">${escapeHtml(getEntityName(entity))}</span>
      <div class="marker-status" hidden></div>
    `;
    markerLayerEl.appendChild(markerElement);
    marker = {
      element: markerElement,
      latLng,
      entityId,
    };
    markers.set(entityId, marker);
    bindPopupActions(marker, entityId);
  } else {
    marker.latLng = latLng;
    marker.element.className = `local-marker threat-${String(getThreatValue(entity, "threatLevel") || "unknown").toLowerCase()}`;
    marker.element.title = getEntityName(entity);
    marker.element.querySelector(".marker-label").textContent = getEntityName(entity);
  }

  updateMarkerPosition(marker);
  updateSelectedMarkerStatus();
  updateEntityCount();
  renderEntityPanel();
  if (selectedEntityId === entityId) {
    showEntityPopup(entityId);
  }
}

function deleteMarker(entityId) {
  const marker = markers.get(entityId);
  if (!marker) {
    console.warn("收到删除事件，但地图上没有对应 marker", entityId);
    entities.delete(entityId);
    updateEntityCount();
    renderEntityPanel();
    return;
  }

  marker.element.remove();
  markers.delete(entityId);
  entities.delete(entityId);
  trackHistories.delete(entityId);
  if (selectedEntityId === entityId) {
    hideEntityPopup();
  }
  updateSelectedMarkerStatus();
  updateEntityCount();
  renderEntityPanel();
  renderTrackLayer();
}

function refreshEntityPopups() {
  renderEntityPanel();
  if (selectedEntityId) {
    showEntityPopup(selectedEntityId);
  }
}

function fitMapToMarkers() {
  if (markers.size === 0) {
    return;
  }

  const latLngs = [...markers.values()].map((marker) => marker.latLng);
  const averageLat = latLngs.reduce((sum, latLng) => sum + latLng[0], 0) / latLngs.length;
  const averageLon = latLngs.reduce((sum, latLng) => sum + latLng[1], 0) / latLngs.length;
  map.center = [averageLat, averageLon];
  updateAllMarkerPositions();
}

async function loadEntities() {
  try {
    const response = await fetch("/api/v1/entities");
    if (!response.ok) {
      throw new Error(`GET /api/v1/entities 返回 ${response.status}`);
    }

    const payload = await response.json();
    const nextEntities = Array.isArray(payload.entities) ? payload.entities : [];
    nextEntities.forEach(upsertMarker);
    await Promise.all(nextEntities.map((entity) => loadTrackHistory(entity?.entityId)));
    renderEntityPanel();
    fitMapToMarkers();
    setLastEvent(`初始加载 ${nextEntities.length} 个 entities`);
  } catch (error) {
    console.error("初始 entities 加载失败", error);
    setLastEvent("初始 entities 加载失败");
  }
}

async function loadMapOverlays() {
  try {
    const response = await fetch("/api/v1/config/map-overlays");
    if (!response.ok) {
      throw new Error(`GET /api/v1/config/map-overlays 返回 ${response.status}`);
    }

    mapOverlays = await response.json();
    renderOverlayLayer();
  } catch (error) {
    console.error("加载地图覆盖层失败", error);
  }
}

async function loadTrackHistory(entityId) {
  if (!entityId) {
    return;
  }

  try {
    const response = await fetch(`/api/v1/tracks/${encodeURIComponent(entityId)}/history?limit=20`);
    if (!response.ok) {
      throw new Error(`GET /api/v1/tracks/${entityId}/history 返回 ${response.status}`);
    }

    const payload = await response.json();
    const history = Array.isArray(payload.history) ? payload.history : [];
    trackHistories.set(entityId, history);
    renderTrackLayer();
  } catch (error) {
    console.error("加载轨迹历史失败", error);
  }
}

async function loadTasks() {
  try {
    const response = await fetch("/api/v1/tasks");
    if (!response.ok) {
      throw new Error(`GET /api/v1/tasks 返回 ${response.status}`);
    }

    const payload = await response.json();
    const nextTasks = Array.isArray(payload.tasks) ? payload.tasks : [];
    tasks.clear();
    nextTasks.forEach((task) => {
      if (task?.taskId) {
        tasks.set(task.taskId, task);
      }
    });
    renderTaskPanel();
    setLastEvent(`初始加载 ${nextTasks.length} 个 tasks`);
  } catch (error) {
    console.error("初始 tasks 加载失败", error);
    setLastEvent("初始 tasks 加载失败");
  }
}

async function loadAlerts() {
  try {
    const response = await fetch("/api/v1/alerts");
    if (!response.ok) {
      throw new Error(`GET /api/v1/alerts 返回 ${response.status}`);
    }

    const payload = await response.json();
    const nextAlerts = Array.isArray(payload.alerts) ? payload.alerts : [];
    alerts.clear();
    nextAlerts.forEach((alert) => {
      if (alert?.alertId) {
        alerts.set(alert.alertId, alert);
      }
    });
    renderAlertPanel();
    setLastEvent(`初始加载 ${nextAlerts.length} 个 alerts`);
  } catch (error) {
    console.error("初始 alerts 加载失败", error);
    setLastEvent("初始 alerts 加载失败");
  }
}

async function loadRecommendations() {
  try {
    const response = await fetch("/api/v1/recommendations");
    if (!response.ok) {
      throw new Error(`GET /api/v1/recommendations 返回 ${response.status}`);
    }

    const payload = await response.json();
    const nextRecommendations = Array.isArray(payload.recommendations) ? payload.recommendations : [];
    recommendations.clear();
    nextRecommendations.forEach((recommendation) => {
      if (recommendation?.recommendationId) {
        recommendations.set(recommendation.recommendationId, recommendation);
      }
    });
    renderRecommendationPanel();
    renderAlertPanel();
    renderEntityPanel();
    updateSelectedMarkerStatus();
    setLastEvent(`初始加载 ${nextRecommendations.length} 个 recommendations`);
  } catch (error) {
    console.error("初始 recommendations 加载失败", error);
    setLastEvent("初始 recommendations 加载失败");
  }
}

async function loadObjects() {
  try {
    const response = await fetch("/api/v1/objects");
    if (!response.ok) {
      throw new Error(`GET /api/v1/objects 返回 ${response.status}`);
    }

    const payload = await response.json();
    const nextObjects = Array.isArray(payload.objects) ? payload.objects : [];
    objects.clear();
    nextObjects.forEach((objectMetadata) => {
      if (objectMetadata?.objectId) {
        objects.set(objectMetadata.objectId, objectMetadata);
      }
    });
    refreshObjectViews();
    setLastEvent(`初始加载 ${nextObjects.length} 个 objects`);
  } catch (error) {
    console.error("初始 objects 加载失败", error);
    setLastEvent("初始 objects 加载失败");
  }
}

function upsertTask(task) {
  if (!task?.taskId) {
    console.warn("task 缺少 taskId，已跳过", task);
    return;
  }

  tasks.set(task.taskId, task);
  renderTaskPanel();
  updateSelectedMarkerStatus();
  if (selectedEntityId === task.relatedEntityId) {
    showEntityPopup(selectedEntityId);
  }
}

function upsertAlert(alert) {
  if (!alert?.alertId) {
    console.warn("alert 缺少 alertId，已跳过", alert);
    return;
  }

  alerts.set(alert.alertId, alert);
  renderAlertPanel();
  renderEntityPanel();
  if (selectedEntityId === alert.entityId) {
    showEntityPopup(selectedEntityId);
  }
}

function upsertRecommendation(recommendation) {
  if (!recommendation?.recommendationId) {
    console.warn("recommendation 缺少 recommendationId，已跳过", recommendation);
    return;
  }

  recommendations.set(recommendation.recommendationId, recommendation);
  renderRecommendationPanel();
  renderAlertPanel();
  updateSelectedMarkerStatus();
  if (selectedEntityId === recommendation.entityId) {
    showEntityPopup(selectedEntityId);
  }
}

function deleteTask(taskId) {
  const existingTask = tasks.get(taskId);
  tasks.delete(taskId);
  renderTaskPanel();
  updateSelectedMarkerStatus();
  if (selectedEntityId && existingTask?.relatedEntityId === selectedEntityId) {
    showEntityPopup(selectedEntityId);
  }
}

function upsertObject(objectMetadata) {
  if (!objectMetadata?.objectId) {
    console.warn("object 缺少 objectId，已跳过", objectMetadata);
    return;
  }

  objects.set(objectMetadata.objectId, objectMetadata);
  refreshObjectViews();
}

function deleteObject(objectId) {
  objects.delete(objectId);
  refreshObjectViews();
}

function refreshObjectViews() {
  refreshEntityPopups();
  renderTaskPanel();
}

async function updateAlertStatus(alertId, status) {
  try {
    const response = await fetch(`/api/v1/alerts/${encodeURIComponent(alertId)}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status }),
    });
    if (!response.ok) {
      throw new Error(`PATCH /api/v1/alerts/${alertId} 返回 ${response.status}`);
    }

    const alert = await response.json();
    setLastEvent(`已更新告警状态 ${alertId} -> ${status}`);
    if (!isStreamOpen()) {
      upsertAlert(alert);
    }
  } catch (error) {
    console.error("更新告警状态失败", error);
    setLastEvent(`更新告警状态失败 ${alertId}`);
  }
}

async function generateRecommendationForAlert(alertId) {
  const alert = alerts.get(alertId);
  if (!alert) {
    setLastEvent(`找不到告警 ${alertId}`);
    return;
  }

  const entity = entities.get(alert.entityId);
  if (!entity) {
    setLastEvent(`找不到告警关联目标 ${alert.entityId || ""}`.trim());
    return;
  }

  const latestRecommendation = getLatestRecommendationForAlert(alertId);
  if (latestRecommendation) {
    try {
      const currentSignature = await computeRecommendationStateSignature(alert, entity);
      if (latestRecommendation.stateSignature === currentSignature) {
        ensurePanelExpanded("recommendations");
        scrollRecommendationIntoView(latestRecommendation.recommendationId, alert.entityId);
        setLastEvent(`当前状态无变化，已显示已有建议 ${latestRecommendation.recommendationId}`);
        return;
      }

      const shouldRegenerate = window.confirm("当前状态已变化，是否重新生成建议？\n取消后将继续显示当前已有建议。");
      if (!shouldRegenerate) {
        ensurePanelExpanded("recommendations");
        scrollRecommendationIntoView(latestRecommendation.recommendationId, alert.entityId);
        setLastEvent(`已保留当前建议 ${latestRecommendation.recommendationId}`);
        return;
      }
    } catch (error) {
      console.warn("计算 recommendation 状态签名失败", error);
    }
  }

  try {
    const response = await fetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/recommendation`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`POST /api/v1/alerts/${alertId}/recommendation 返回 ${response.status}`);
    }

    const payload = await response.json();
    setLastEvent(payload.reused ? `已复用建议 ${payload.recommendationId}` : `已生成建议 ${payload.recommendationId}`);
    if (!isStreamOpen()) {
      upsertRecommendation(payload.recommendation);
    }
    ensurePanelExpanded("recommendations");
    scrollRecommendationIntoView(payload.recommendation.recommendationId, payload.recommendation.entityId);
  } catch (error) {
    console.error("生成建议失败", error);
    setLastEvent(`生成建议失败 ${alertId}`);
  }
}

async function createTaskFromRecommendation(recommendationId) {
  const recommendation = recommendations.get(recommendationId);
  const selectedAction = recommendation?.actions?.[0] || recommendation?.summary || "执行处置建议";

  try {
    const response = await fetch(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}/create-task`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        assignedAssetId: "SIM_ASSET_001",
        selectedAction,
      }),
    });
    if (!response.ok) {
      throw new Error(`POST /api/v1/recommendations/${recommendationId}/create-task 返回 ${response.status}`);
    }

    const payload = await response.json();
    setLastEvent(`已从建议创建任务 ${payload.taskId}`);
    if (!isStreamOpen()) {
      upsertTask(payload.task);
    }
    await loadRecommendations();
  } catch (error) {
    console.error("从建议创建任务失败", error);
    setLastEvent(`从建议创建任务失败 ${recommendationId}`);
  }
}

function isStreamOpen() {
  return streamSocket?.readyState === WebSocket.OPEN;
}

async function createTaskForEntity(entityId) {
  const entity = entities.get(entityId);
  const threat = entity?.metadata?.threat || {};
  const payload = {
    taskType: "RESPOND_TO_THREAT",
    title: "处置疑似威胁目标",
    description: threat.recommendation || "对指定 entity 进行模拟威胁处置任务",
    priority: "NORMAL",
    relatedEntityId: entityId,
    assignedAssetId: "SIM_ASSET_001",
    metadata: {
      createdFrom: "map_popup",
      threatAnalysis: threat,
    },
  };

  try {
    const response = await fetch("/api/v1/tasks", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`POST /api/v1/tasks 返回 ${response.status}`);
    }

    const task = await response.json();
    setLastEvent(`已创建处置任务 ${task.taskId || ""}`.trim());
    if (!isStreamOpen()) {
      upsertTask(task);
    }
  } catch (error) {
    console.error("创建处置任务失败", error);
    setLastEvent(`创建处置任务失败 ${entityId}`);
  }
}

function renderEntityPanel() {
  updateEntityCount();

  if (!entityListEl) {
    return;
  }

  entityListEl.innerHTML = "";
  const sortedEntities = [...entities.values()].sort((left, right) => {
    const leftThreat = getThreatValue(left, "threatLevel") || "";
    const rightThreat = getThreatValue(right, "threatLevel") || "";
    const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };
    const threatDelta = (rank[rightThreat] || 0) - (rank[leftThreat] || 0);
    if (threatDelta !== 0) {
      return threatDelta;
    }
    const leftTime = Date.parse(left?.provenance?.sourceUpdateTime || left?.createdTime || "") || 0;
    const rightTime = Date.parse(right?.provenance?.sourceUpdateTime || right?.createdTime || "") || 0;
    return rightTime - leftTime;
  });

  if (sortedEntities.length === 0) {
    entityListEl.innerHTML = '<p class="entity-empty">暂无目标</p>';
    return;
  }

  sortedEntities.forEach((entity) => {
    const entityId = valueOrDash(entity.entityId);
    const threatLevel = valueOrDash(getThreatValue(entity, "threatLevel"));
    const anomalyType = valueOrDash(getThreatValue(entity, "anomalyType"));
    const recommendation = valueOrDash(getThreatValue(entity, "recommendation"));
    const relatedAlerts = getAlertsForEntity(entity.entityId);
    const latLng = getLatLng(entity);
    const latestAlert = relatedAlerts[0];
    const card = document.createElement("article");
    card.className = `entity-card threat-${String(threatLevel).toLowerCase()}`;
    card.dataset.entityId = entity.entityId;
    card.innerHTML = `
      <div class="entity-card-title">
        <h3>${escapeHtml(getEntityName(entity))}</h3>
        <span class="threat-badge">${escapeHtml(threatLevel)}</span>
      </div>
      <div class="entity-meta-row">
        <span class="entity-meta-pill">${escapeHtml(compactText(entityId, 28))}</span>
        <span class="entity-meta-pill">${escapeHtml(compactText(anomalyType, 18))}</span>
        <span class="entity-meta-pill">${escapeHtml(compactText(valueOrDash(formatSensorSources(entity)), 18))}</span>
      </div>
      <p class="entity-summary">${escapeHtml(compactText(latestAlert?.summary || recommendation || "当前无进一步处置建议", 88))}</p>
      <dl class="entity-fields">
        <div>
          <dt>位置</dt>
          <dd>${escapeHtml(formatLatLng(latLng))}</dd>
        </div>
        <div>
          <dt>告警</dt>
          <dd>${escapeHtml(compactText(latestAlert?.title || "无", 40))}</dd>
        </div>
      </dl>
      <div class="entity-actions">
        <button type="button" class="entity-focus-button">定位目标</button>
        <button type="button" class="entity-create-task-button">创建处置任务</button>
      </div>
    `;

    card.querySelector(".entity-focus-button")?.addEventListener("click", () => {
      focusEntity(entity.entityId);
    });
    card.querySelector(".entity-create-task-button")?.addEventListener("click", () => {
      createTaskForEntity(entity.entityId);
    });

    entityListEl.appendChild(card);
  });
}

function renderAlertPanel() {
  updateAlertCount();

  if (!alertListEl) {
    return;
  }

  alertListEl.innerHTML = "";
  const sortedAlerts = [...alerts.values()].sort((left, right) => {
    const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
    const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
    return rightTime - leftTime;
  });

  if (sortedAlerts.length === 0) {
    alertListEl.innerHTML = '<p class="task-empty">暂无告警</p>';
    return;
  }

  sortedAlerts.forEach((alert) => {
    const latestRecommendation = getLatestRecommendationForAlert(alert.alertId);
    const card = document.createElement("article");
    card.className = `alert-card risk-${getAlertRiskBadge(alert.riskLevel)}`;
    card.dataset.alertId = alert.alertId;
    const statusButtons = ALERT_STATUSES.map((nextStatus) => {
      const disabled = nextStatus === alert.status ? "disabled" : "";
      return `<button type="button" class="alert-status-action" data-status="${nextStatus}" ${disabled}>${nextStatus}</button>`;
    }).join("");

    card.innerHTML = `
      <div class="task-card-title">
        <h3>${escapeHtml(valueOrDash(alert.title))}</h3>
        <span class="threat-badge">${escapeHtml(valueOrDash(alert.riskLevel))}</span>
      </div>
      <div class="entity-meta-row">
        <span class="entity-meta-pill">${escapeHtml(valueOrDash(alert.status))}</span>
        <span class="entity-meta-pill">${escapeHtml(compactText(valueOrDash(alert.entityId), 22))}</span>
        <span class="entity-meta-pill">${escapeHtml(compactText(valueOrDash(alert.alertId), 22))}</span>
      </div>
      <p class="entity-summary">${escapeHtml(compactText(valueOrDash(alert.summary), 88))}</p>
      <dl class="entity-fields alert-fields">
        <div>
          <dt>建议</dt>
          <dd>${escapeHtml(compactText(valueOrDash(latestRecommendation?.summary || "未生成"), 50))}</dd>
        </div>
      </dl>
      <div class="action-grid action-grid-primary">
        <button type="button" class="alert-focus-button">定位目标</button>
        <button type="button" class="alert-generate-recommendation-button">生成建议</button>
        <button type="button" class="alert-open-recommendation-button" ${latestRecommendation ? "" : "disabled"}>查看建议</button>
      </div>
      <details class="more-actions alert-more-actions">
        <summary>更多状态</summary>
        <div class="action-grid action-grid-status alert-actions">
          ${statusButtons}
        </div>
      </details>
    `;

    card.addEventListener("click", (event) => {
      if (event.target instanceof HTMLElement && event.target.closest("button")) {
        return;
      }
      if (alert.entityId) {
        focusEntity(alert.entityId);
      }
    });

    card.querySelector(".alert-focus-button")?.addEventListener("click", () => {
      if (alert.entityId) {
        focusEntity(alert.entityId);
      }
    });

    card.querySelector(".alert-generate-recommendation-button")?.addEventListener("click", () => {
      generateRecommendationForAlert(alert.alertId);
    });
    card.querySelector(".alert-open-recommendation-button")?.addEventListener("click", () => {
      if (latestRecommendation?.recommendationId) {
        scrollRecommendationIntoView(latestRecommendation.recommendationId, alert.entityId);
      }
    });

    card.querySelectorAll(".alert-status-action").forEach((button) => {
      button.addEventListener("click", () => {
        updateAlertStatus(alert.alertId, button.dataset.status);
      });
    });

    alertListEl.appendChild(card);
  });
}

function scrollRecommendationIntoView(recommendationId, entityId) {
  const card = recommendationListEl?.querySelector(`[data-recommendation-id="${CSS.escape(recommendationId)}"]`);
  if (entityId) {
    focusEntity(entityId);
  }
  if (card) {
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("flash-highlight");
    window.setTimeout(() => {
      card.classList.remove("flash-highlight");
    }, 1600);
  }
}

function renderRecommendationPanel() {
  updateRecommendationCount();

  if (!recommendationListEl) {
    return;
  }

  recommendationListEl.innerHTML = "";
  const sortedRecommendations = [...recommendations.values()].sort((left, right) => {
    const leftTime = Date.parse(left?.updatedAt || left?.createdAt || "") || 0;
    const rightTime = Date.parse(right?.updatedAt || right?.createdAt || "") || 0;
    return rightTime - leftTime;
  });

  if (sortedRecommendations.length === 0) {
    recommendationListEl.innerHTML = '<p class="task-empty">暂无建议</p>';
    return;
  }

  sortedRecommendations.forEach((recommendation) => {
    const card = document.createElement("article");
    card.className = `recommendation-card risk-${getAlertRiskBadge(recommendation.riskLevel)}`;
    card.dataset.recommendationId = recommendation.recommendationId;
    const actions = Array.isArray(recommendation.actions) ? recommendation.actions : [];
    const references = Array.isArray(recommendation.references) ? recommendation.references : [];
    const alert = alerts.get(recommendation.alertId);
    const evidence = Array.isArray(alert?.evidence) ? alert.evidence : [];
    const rationale = buildRecommendationRationale(recommendation, alert, references);
    const primaryAction = actions[0] || "无";

    card.innerHTML = `
      <div class="task-card-title">
        <h3>${escapeHtml(valueOrDash(recommendation.summary))}</h3>
        <span class="threat-badge">${escapeHtml(valueOrDash(recommendation.riskLevel))}</span>
      </div>
      <div class="entity-meta-row">
        <span class="entity-meta-pill">${escapeHtml(valueOrDash(recommendation.status))}</span>
        <span class="entity-meta-pill">${escapeHtml(compactText(valueOrDash(recommendation.provider), 18))}</span>
        <span class="entity-meta-pill">${escapeHtml(formatConfidence(recommendation.confidence))}</span>
      </div>
      <p class="entity-summary">${escapeHtml(compactText(primaryAction, 88))}</p>
      <dl class="entity-fields alert-fields">
        <div>
          <dt>来源告警</dt>
          <dd>${escapeHtml(compactText(valueOrDash(recommendation.alertId), 26))}</dd>
        </div>
        <div>
          <dt>关联目标</dt>
          <dd>${escapeHtml(compactText(valueOrDash(recommendation.entityId), 26))}</dd>
        </div>
      </dl>
      <div class="action-grid action-grid-primary recommendation-actions">
        <button type="button" class="recommendation-create-task-button">采纳并创建任务</button>
        <button type="button" class="recommendation-focus-entity-button">定位目标</button>
        <button type="button" class="recommendation-open-alert-button">查看告警</button>
      </div>
      <details class="recommendation-details task-details">
        <summary>展开详情</summary>
        ${
          alert
            ? `
        <div class="recommendation-section">
          <h4>触发原因</h4>
          <p class="recommendation-context">${escapeHtml(valueOrDash(alert.summary))}</p>
        </div>
        <div class="recommendation-section">
          <h4>触发证据</h4>
          ${
            evidence.length === 0
              ? '<p class="recommendation-context">暂无证据明细</p>'
              : `
          <ul class="recommendation-evidence-list">
            ${evidence.map((item) => `<li>${escapeHtml(valueOrDash(item))}</li>`).join("")}
          </ul>`
          }
        </div>`
            : ""
        }
        <div class="recommendation-section">
          <h4>处置理由</h4>
          <div class="recommendation-rationale-cards">
            ${rationale.map((item) => `<article class="rationale-card">${escapeHtml(valueOrDash(item))}</article>`).join("")}
          </div>
        </div>
        <div class="recommendation-section">
          <h4>建议动作</h4>
          <ul class="recommendation-actions-list">
            ${actions.map((action) => `<li>${escapeHtml(valueOrDash(action))}</li>`).join("")}
          </ul>
        </div>
        <div class="recommendation-section">
          <h4>参考依据</h4>
          <div class="recommendation-reference-cards">
            ${
              references.length === 0
                ? '<p class="recommendation-context">无</p>'
                : references
                    .map((reference) => {
                      const formatted = formatReference(reference);
                      return `
                        <article class="reference-card">
                          <strong>${escapeHtml(valueOrDash(formatted.title))}</strong>
                          ${
                            formatted.excerpt
                              ? `<p>${escapeHtml(valueOrDash(formatted.excerpt))}</p>`
                              : ""
                          }
                        </article>
                      `;
                    })
                    .join("")
            }
          </div>
        </div>
      </details>
    `;

    card.addEventListener("click", (event) => {
      if (event.target instanceof HTMLElement && event.target.closest("button")) {
        return;
      }
      if (recommendation.entityId) {
        focusEntity(recommendation.entityId);
      }
    });

    card.querySelector(".recommendation-create-task-button")?.addEventListener("click", () => {
      createTaskFromRecommendation(recommendation.recommendationId);
    });
    card.querySelector(".recommendation-open-alert-button")?.addEventListener("click", () => {
      if (recommendation.alertId) {
        scrollAlertIntoView(recommendation.alertId, recommendation.entityId);
      }
    });
    card.querySelector(".recommendation-focus-entity-button")?.addEventListener("click", () => {
      if (recommendation.entityId) {
        focusEntity(recommendation.entityId);
      }
    });

    recommendationListEl.appendChild(card);
  });
}

function scrollAlertIntoView(alertId, entityId) {
  const card = alertListEl?.querySelector(`[data-alert-id="${CSS.escape(alertId)}"]`);
  if (entityId) {
    focusEntity(entityId);
  }
  if (card) {
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("flash-highlight");
    window.setTimeout(() => {
      card.classList.remove("flash-highlight");
    }, 1600);
  }
}

async function updateTaskStatus(taskId, status) {
  try {
    const response = await fetch(`/api/v1/tasks/${encodeURIComponent(taskId)}/status`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status }),
    });

    if (!response.ok) {
      throw new Error(`PATCH /api/v1/tasks/${taskId}/status 返回 ${response.status}`);
    }

    const task = await response.json();
    setLastEvent(`已更新任务状态 ${taskId} -> ${status}`);
    if (!isStreamOpen()) {
      upsertTask(task);
    }
  } catch (error) {
    console.error("更新任务状态失败", error);
    setLastEvent(`更新任务状态失败 ${taskId}`);
  }
}

async function removeTask(taskId) {
  try {
    const response = await fetch(`/api/v1/tasks/${encodeURIComponent(taskId)}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      throw new Error(`DELETE /api/v1/tasks/${taskId} 返回 ${response.status}`);
    }

    setLastEvent(`已删除任务 ${taskId}`);
    if (!isStreamOpen()) {
      deleteTask(taskId);
    }
  } catch (error) {
    console.error("删除任务失败", error);
    setLastEvent(`删除任务失败 ${taskId}`);
  }
}

function downloadObject(objectId) {
  if (!objectId) {
    setLastEvent("下载附件失败：缺少 objectId");
    return;
  }

  window.open(`/api/v1/objects/${encodeURIComponent(objectId)}/download`, "_blank");
}

async function deleteObjectById(objectId) {
  if (!objectId) {
    setLastEvent("删除附件失败：缺少 objectId");
    return;
  }

  try {
    const response = await fetch(`/api/v1/objects/${encodeURIComponent(objectId)}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      throw new Error(`DELETE /api/v1/objects/${objectId} 返回 ${response.status}`);
    }

    setLastEvent(`已删除附件 ${objectId}`);
    if (!isStreamOpen()) {
      deleteObject(objectId);
    }
  } catch (error) {
    console.error("删除附件失败", error);
    setLastEvent(`删除附件失败 ${objectId}`);
  }
}

async function uploadObject(formData, fileInput, descriptionInput, eventLabel) {
  try {
    const response = await fetch("/api/v1/objects", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 413) {
        throw new Error("附件大小不能超过 20MB");
      }
      throw new Error(`POST /api/v1/objects 返回 ${response.status}`);
    }

    const objectMetadata = await response.json();
    fileInput.value = "";
    if (descriptionInput) {
      descriptionInput.value = "";
    }
    setLastEvent(`已上传${eventLabel}附件 ${objectMetadata.objectId}`);
    if (!isStreamOpen()) {
      upsertObject(objectMetadata);
    }
  } catch (error) {
    console.error("上传附件失败", error);
    setLastEvent(`上传附件失败：${error.message}`);
  }
}

function uploadObjectForEntity(entityId, fileInputId, descriptionInputId) {
  const fileInput = document.getElementById(fileInputId);
  const descriptionInput = document.getElementById(descriptionInputId);
  const file = fileInput?.files?.[0];
  if (!file) {
    setLastEvent("请选择 entity 附件文件");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("relatedEntityId", entityId);
  formData.append("description", descriptionInput?.value || "");
  formData.append("metadata", JSON.stringify({ createdFrom: "entity_popup" }));
  uploadObject(formData, fileInput, descriptionInput, " entity");
}

function uploadObjectForTask(taskId, fileInputId, descriptionInputId) {
  const fileInput = document.getElementById(fileInputId);
  const descriptionInput = document.getElementById(descriptionInputId);
  const file = fileInput?.files?.[0];
  if (!file) {
    setLastEvent("请选择 task 附件文件");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("relatedTaskId", taskId);
  formData.append("description", descriptionInput?.value || "");
  formData.append("metadata", JSON.stringify({ createdFrom: "task_panel" }));
  uploadObject(formData, fileInput, descriptionInput, " task");
}

function focusEntity(entityId) {
  const marker = markers.get(entityId);
  if (!marker) {
    setLastEvent(`找不到对应 entity marker ${entityId}`);
    return;
  }

  map.center = marker.latLng;
  map.zoom = Math.max(map.zoom, 12);
  updateAllMarkerPositions();
  showEntityPopup(entityId);
  emphasizeEntity(entityId);
  setLastEvent(`已定位 entity ${entityId}`);
}

function formatTaskTime(value) {
  return escapeHtml(valueOrDash(value));
}

function renderTaskPanel() {
  updateTaskCount();
  taskListEl.innerHTML = "";

  const sortedTasks = [...tasks.values()].sort((left, right) => {
    const leftTime = Date.parse(left?.createdAt || "") || 0;
    const rightTime = Date.parse(right?.createdAt || "") || 0;
    return rightTime - leftTime;
  });

  if (sortedTasks.length === 0) {
    taskListEl.innerHTML = '<p class="task-empty">暂无任务</p>';
    return;
  }

  sortedTasks.forEach((task) => {
    const taskId = valueOrDash(task.taskId);
    const status = valueOrDash(task.status);
    const relatedEntityId = valueOrDash(task.relatedEntityId);
    const resultSummary = task.resultSummary;
    const recommendation = task?.metadata?.threatAnalysis?.recommendation;
    const createdFrom = task?.metadata?.createdFrom;
    const sourceAlertId = task?.metadata?.alertId;
    const sourceRecommendationId = task?.metadata?.recommendationId;
    const selectedAction = task?.metadata?.selectedAction || task?.description;
    const sourceRecommendation = sourceRecommendationId ? recommendations.get(sourceRecommendationId) : null;
    const sourceAlert = sourceAlertId ? alerts.get(sourceAlertId) : null;
    const relatedObjects = getObjectsForTask(task.taskId);
    const statusButtons = TASK_STATUSES.map((nextStatus) => {
      const disabled = nextStatus === task.status ? "disabled" : "";
      const isCurrent = nextStatus === task.status ? "is-current" : "";
      return `<button type="button" class="task-status-action ${isCurrent}" data-status="${nextStatus}" ${disabled}>${nextStatus}</button>`;
    }).join("");

    const card = document.createElement("article");
    card.className = `task-card status-${String(task.status || "UNKNOWN").toLowerCase()}`;
    card.dataset.taskId = task.taskId;
    card.innerHTML = `
      <div class="task-card-title">
        <h3>${escapeHtml(valueOrDash(task.title))}</h3>
        <span class="task-status">${escapeHtml(status)}</span>
      </div>
      <p class="entity-summary task-summary">${escapeHtml(compactText(selectedAction || recommendation || "执行处置任务", 96))}</p>
      <details class="task-details task-chain-details">
        <summary>任务链路</summary>
        <div class="task-chain">
          <div class="task-chain-badges">
            <span class="task-chain-badge">${escapeHtml(createdFrom === "recommendation" ? "来源: 建议" : "来源: 面板创建")}</span>
            ${
              sourceAlertId
                ? `<span class="task-chain-badge">告警: ${escapeHtml(valueOrDash(sourceAlertId))}</span>`
                : ""
            }
            ${
              sourceRecommendationId
                ? `<span class="task-chain-badge">建议: ${escapeHtml(valueOrDash(sourceRecommendationId))}</span>`
                : ""
            }
          </div>
          <div class="task-chain-action">
            <span class="task-chain-label">执行动作</span>
            <p>${escapeHtml(valueOrDash(selectedAction || recommendation || "执行处置任务"))}</p>
          </div>
          <div class="task-chain-actions">
            ${
              sourceAlertId
                ? `<button type="button" class="task-open-alert-button" data-alert-id="${escapeHtml(sourceAlertId)}">查看来源告警</button>`
                : ""
            }
            ${
              sourceRecommendationId
                ? `<button type="button" class="task-open-recommendation-button" data-recommendation-id="${escapeHtml(sourceRecommendationId)}">查看来源建议</button>`
                : ""
            }
          </div>
        </div>
      </details>
      <details class="task-details">
        <summary>任务详情</summary>
        <dl class="task-fields">
          <div>
            <dt>taskId</dt>
            <dd>${escapeHtml(taskId)}</dd>
          </div>
          <div>
            <dt>relatedEntityId</dt>
            <dd>
              <button type="button" class="related-entity-button" data-entity-id="${escapeHtml(relatedEntityId)}">
                ${escapeHtml(relatedEntityId)}
              </button>
            </dd>
          </div>
          <div>
            <dt>assignedAssetId</dt>
            <dd>${escapeHtml(valueOrDash(task.assignedAssetId))}</dd>
          </div>
          <div>
            <dt>createdAt</dt>
            <dd>${formatTaskTime(task.createdAt)}</dd>
          </div>
          <div>
            <dt>updatedAt</dt>
            <dd>${formatTaskTime(task.updatedAt)}</dd>
          </div>
          ${
            resultSummary
              ? `
          <div>
            <dt>result</dt>
            <dd>${escapeHtml(resultSummary)}</dd>
          </div>`
              : ""
          }
        </dl>
      </details>
      <details class="task-details task-assets">
        <summary>任务附件</summary>
        <section class="task-objects">
          ${renderObjectUploadForm("task", task.taskId)}
          ${renderObjectList(relatedObjects)}
        </section>
      </details>
      <section class="task-status-group" aria-label="任务状态操作">
        <h4>任务状态</h4>
        <div class="task-status-segmented">
          ${statusButtons}
        </div>
      </section>
      <button type="button" class="task-delete-button">删除任务</button>
    `;

    card.querySelector(".related-entity-button")?.addEventListener("click", () => {
      if (task.relatedEntityId) {
        focusEntity(task.relatedEntityId);
      } else {
        setLastEvent(`任务 ${taskId} 没有关联 entity`);
      }
    });

    card.querySelectorAll(".task-status-action").forEach((button) => {
      button.addEventListener("click", () => {
        updateTaskStatus(task.taskId, button.dataset.status);
      });
    });

    card.querySelector(".task-delete-button")?.addEventListener("click", () => {
      removeTask(task.taskId);
    });

    card.querySelector(".task-open-alert-button")?.addEventListener("click", () => {
      if (sourceAlertId) {
        scrollAlertIntoView(sourceAlertId, task.relatedEntityId);
      }
    });

    card.querySelector(".task-open-recommendation-button")?.addEventListener("click", () => {
      if (sourceRecommendationId) {
        scrollRecommendationIntoView(sourceRecommendationId, task.relatedEntityId);
      }
    });

    const uploadButton = card.querySelector('.object-upload-button[data-upload-context="task"]');
    uploadButton?.addEventListener("click", () => {
      uploadObjectForTask(
        task.taskId,
        uploadButton.dataset.fileInputId,
        uploadButton.dataset.descriptionInputId,
      );
    });

    bindObjectActions(card);

    taskListEl.appendChild(card);
  });
}

function handleStreamMessage(message) {
  if (message.type === "stream.connected") {
    setWebSocketStatus("已连接");
    setLastEvent(message.message || "stream 已连接");
    return;
  }

  if (message.type === "entity.upserted") {
    upsertMarker(message.entity);
    loadTrackHistory(message.entityId);
    setLastEvent(`upsert ${message.entityId}`);
    return;
  }

  if (message.type === "entity.deleted") {
    deleteMarker(message.entityId);
    setLastEvent(`delete ${message.entityId}`);
    return;
  }

  if (message.type === "task.created") {
    upsertTask(message.task);
    setLastEvent(`task.created ${message.taskId}`);
    return;
  }

  if (message.type === "alert.created") {
    upsertAlert(message.alert);
    setLastEvent(`alert.created ${message.alertId}`);
    return;
  }

  if (message.type === "alert.updated") {
    upsertAlert(message.alert);
    setLastEvent(`alert.updated ${message.alertId}`);
    return;
  }

  if (message.type === "recommendation.created") {
    upsertRecommendation(message.recommendation);
    setLastEvent(`recommendation.created ${message.recommendationId}`);
    return;
  }

  if (message.type === "task.status_updated") {
    upsertTask(message.task);
    setLastEvent(`task.status_updated ${message.taskId} -> ${message.status}`);
    return;
  }

  if (message.type === "task.deleted") {
    deleteTask(message.taskId);
    setLastEvent(`task.deleted ${message.taskId}`);
    return;
  }

  if (message.type === "object.created") {
    upsertObject(message.object);
    setLastEvent(`object.created ${message.objectId}`);
    return;
  }

  if (message.type === "object.deleted") {
    deleteObject(message.objectId);
    setLastEvent(`object.deleted ${message.objectId}`);
    return;
  }

  console.warn("收到未知 stream 消息", message);
}

function connectStream() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const streamUrl = `${protocol}//${window.location.host}/api/v1/entities/stream`;
  setWebSocketStatus("连接中");

  streamSocket = new WebSocket(streamUrl);

  streamSocket.addEventListener("open", () => {
    setWebSocketStatus("已连接");
  });

  streamSocket.addEventListener("message", (event) => {
    try {
      handleStreamMessage(JSON.parse(event.data));
    } catch (error) {
      console.error("stream 消息解析失败", error);
      setLastEvent("stream 消息解析失败");
    }
  });

  streamSocket.addEventListener("close", () => {
    setWebSocketStatus("已断开，准备重连");
    reconnectTimer = setTimeout(connectStream, 2000);
  });

  streamSocket.addEventListener("error", () => {
    setWebSocketStatus("连接异常");
  });
}

function connectWebSocket() {
  connectStream();
}

function clearPanelDropIndicators() {
  document.querySelectorAll(".panel-section").forEach((section) => {
    section.classList.remove("panel-section-drop-before", "panel-section-drop-after", "is-dragging");
  });
}

function savePanelOrder() {
  const panelIds = [...document.querySelectorAll(".task-panel > .panel-section")]
    .map((section) => section.dataset.panelId)
    .filter(Boolean);

  try {
    window.localStorage.setItem(PANEL_ORDER_STORAGE_KEY, JSON.stringify(panelIds));
  } catch (error) {
    console.warn("保存面板排序失败", error);
  }
}

function applySavedPanelOrder() {
  const taskPanelEl = document.querySelector(".task-panel");
  if (!taskPanelEl) {
    return;
  }

  try {
    const raw = window.localStorage.getItem(PANEL_ORDER_STORAGE_KEY);
    const panelIds = raw ? JSON.parse(raw) : null;
    if (!Array.isArray(panelIds) || panelIds.length === 0) {
      return;
    }

    panelIds.forEach((panelId) => {
      const section = taskPanelEl.querySelector(`.panel-section[data-panel-id="${panelId}"]`);
      if (section) {
        taskPanelEl.appendChild(section);
      }
    });
  } catch (error) {
    console.warn("读取面板排序失败", error);
  }
}

function initSortablePanels() {
  const taskPanelEl = document.querySelector(".task-panel");
  if (!taskPanelEl) {
    return;
  }

  applySavedPanelOrder();

  let draggedSection = null;

  taskPanelEl.querySelectorAll(".panel-section").forEach((section) => {
    const handle = section.querySelector("[data-drag-handle]");
    if (!handle) {
      return;
    }

    handle.draggable = true;

    handle.addEventListener("dragstart", (event) => {
      draggedSection = section;
      clearPanelDropIndicators();
      section.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", section.dataset.panelId || "");
    });

    handle.addEventListener("dragend", () => {
      clearPanelDropIndicators();
      draggedSection = null;
    });

    section.addEventListener("dragover", (event) => {
      if (!draggedSection || draggedSection === section) {
        return;
      }
      event.preventDefault();
      const rect = section.getBoundingClientRect();
      const insertBefore = event.clientY < rect.top + rect.height / 2;
      section.classList.toggle("panel-section-drop-before", insertBefore);
      section.classList.toggle("panel-section-drop-after", !insertBefore);
    });

    section.addEventListener("dragleave", () => {
      section.classList.remove("panel-section-drop-before", "panel-section-drop-after");
    });

    section.addEventListener("drop", (event) => {
      if (!draggedSection || draggedSection === section) {
        return;
      }
      event.preventDefault();
      const rect = section.getBoundingClientRect();
      const insertBefore = event.clientY < rect.top + rect.height / 2;
      if (insertBefore) {
        taskPanelEl.insertBefore(draggedSection, section);
      } else {
        taskPanelEl.insertBefore(draggedSection, section.nextSibling);
      }
      clearPanelDropIndicators();
      savePanelOrder();
    });
  });
}

function getCollapsedPanels() {
  try {
    const raw = window.localStorage.getItem(PANEL_COLLAPSE_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? new Set(parsed) : new Set();
  } catch (error) {
    console.warn("读取折叠面板状态失败", error);
    return new Set();
  }
}

function saveCollapsedPanels(collapsedPanels) {
  try {
    window.localStorage.setItem(PANEL_COLLAPSE_STORAGE_KEY, JSON.stringify([...collapsedPanels]));
  } catch (error) {
    console.warn("保存折叠面板状态失败", error);
  }
}

function setPanelCollapsedState(button, collapsed) {
  const targetId = button.dataset.panelTarget;
  const targetEl = document.getElementById(targetId);
  if (!targetEl) {
    return;
  }
  const sectionEl = targetEl.closest("section");
  if (!sectionEl) {
    return;
  }

  sectionEl.classList.toggle("is-collapsed", collapsed);
  button.setAttribute("aria-expanded", collapsed ? "false" : "true");
  button.textContent = collapsed ? "展开" : "收起";
}

function initCollapsiblePanels() {
  const collapsedPanels = getCollapsedPanels();
  const toggleButtons = document.querySelectorAll(".panel-toggle-button[data-panel-target]");

  toggleButtons.forEach((button) => {
    const targetId = button.dataset.panelTarget;
    const isCollapsed = collapsedPanels.has(targetId);
    setPanelCollapsedState(button, isCollapsed);

    button.addEventListener("click", () => {
      const currentlyExpanded = button.getAttribute("aria-expanded") === "true";
      const nextCollapsed = currentlyExpanded;
      setPanelCollapsedState(button, nextCollapsed);

      if (nextCollapsed) {
        collapsedPanels.add(targetId);
      } else {
        collapsedPanels.delete(targetId);
      }
      saveCollapsedPanels(collapsedPanels);
    });
  });
}

function applyTaskPanelWidth(width) {
  const normalized = Math.max(400, Math.min(760, Math.round(width)));
  document.body.style.setProperty("--task-panel-width", `${normalized}px`);
  try {
    window.localStorage.setItem(PANEL_WIDTH_STORAGE_KEY, String(normalized));
  } catch (error) {
    console.warn("保存面板宽度失败", error);
  }
}

function initPanelResizer() {
  if (!panelResizerEl || window.innerWidth <= 900) {
    return;
  }

  try {
    const savedWidth = Number(window.localStorage.getItem(PANEL_WIDTH_STORAGE_KEY));
    if (Number.isFinite(savedWidth) && savedWidth > 0) {
      applyTaskPanelWidth(savedWidth);
    }
  } catch (error) {
    console.warn("读取面板宽度失败", error);
  }

  let dragging = false;
  let activePointerId = null;

  const onPointerMove = (event) => {
    if (!dragging) {
      return;
    }
    const nextWidth = window.innerWidth - event.clientX;
    applyTaskPanelWidth(nextWidth);
  };

  const stopDragging = () => {
    if (!dragging) {
      return;
    }
    dragging = false;
    panelResizerEl.classList.remove("is-dragging");
    document.body.style.userSelect = "";
    if (activePointerId !== null) {
      panelResizerEl.releasePointerCapture?.(activePointerId);
      activePointerId = null;
    }
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", stopDragging);
  };

  panelResizerEl.addEventListener("pointerdown", (event) => {
    if (window.innerWidth <= 900) {
      return;
    }
    dragging = true;
    activePointerId = event.pointerId;
    panelResizerEl.classList.add("is-dragging");
    document.body.style.userSelect = "none";
    panelResizerEl.setPointerCapture?.(event.pointerId);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", stopDragging);
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth <= 900) {
      document.body.style.removeProperty("--task-panel-width");
      return;
    }
    try {
      const savedWidth = Number(window.localStorage.getItem(PANEL_WIDTH_STORAGE_KEY));
      if (Number.isFinite(savedWidth) && savedWidth > 0) {
        applyTaskPanelWidth(savedWidth);
      }
    } catch (error) {
      console.warn("恢复面板宽度失败", error);
    }
  });
}

function initMap() {
  const initialView = getInitialMapView();
  map = {
    center: initialView.center,
    zoom: initialView.zoom,
  };
  renderLocalMapShell();
  updateMapCenterLabel();
}

refreshTasksButton.addEventListener("click", loadTasks);

document.querySelectorAll(".summary-card[data-summary-action]").forEach((button) => {
  button.addEventListener("click", () => {
    handleSummaryAction(button.dataset.summaryAction);
  });
});

document.addEventListener("DOMContentLoaded", () => {
  initSortablePanels();
  initCollapsiblePanels();
  initPanelResizer();
  initMap();
  loadMapOverlays();
  loadEntities();
  loadAlerts();
  loadRecommendations();
  loadTasks();
  loadObjects();
  connectWebSocket();
});
