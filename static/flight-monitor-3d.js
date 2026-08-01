(async () => {
  const C = Cesium;
  const viewer = new C.Viewer("cesium", {
    baseLayer: false, terrainProvider: new C.EllipsoidTerrainProvider(),
    animation: false, timeline: false, baseLayerPicker: false, geocoder: false,
    homeButton: false, sceneModePicker: false, navigationHelpButton: false,
    fullscreenButton: false, infoBox: false, selectionIndicator: false,
  });
    shadows: true,
  viewer.scene.globe.baseColor = C.Color.fromCssColorString("#17313d");
  viewer.scene.globe.enableLighting = true;
  viewer.scene.highDynamicRange = true;
  viewer.scene.morphTo3D(0);
  // 使用常见地图操作：左键拖动平移，滚轮缩放，中键拖动调整倾角。
  const cameraController = viewer.scene.screenSpaceCameraController;
  cameraController.enableRotate = false;
  cameraController.enableTranslate = true;
  cameraController.enableZoom = true;
  cameraController.enableTilt = true;
  cameraController.zoomEventTypes = [C.CameraEventType.WHEEL, C.CameraEventType.PINCH];
  cameraController.tiltEventTypes = [C.CameraEventType.MIDDLE_DRAG, C.CameraEventType.PINCH];
  let mapDragging = false;
  let dragAnchor;
  const dragHandler = new C.ScreenSpaceEventHandler(viewer.scene.canvas);
  dragHandler.setInputAction(event => {
    dragAnchor = viewer.camera.pickEllipsoid(event.position, viewer.scene.globe.ellipsoid);
    mapDragging = Boolean(dragAnchor);
    if (mapDragging) viewer.scene.canvas.style.cursor = "grabbing";
  }, C.ScreenSpaceEventType.LEFT_DOWN);
  dragHandler.setInputAction(event => {
    if (!mapDragging || !dragAnchor) return;
    const current = viewer.camera.pickEllipsoid(event.endPosition, viewer.scene.globe.ellipsoid);
    if (!current) return;
    const movement = C.Cartesian3.subtract(dragAnchor, current, new C.Cartesian3());
    viewer.camera.position = C.Cartesian3.add(viewer.camera.position, movement, new C.Cartesian3());
  }, C.ScreenSpaceEventType.MOUSE_MOVE);
  const stopMapDrag = () => {
    mapDragging = false;
    dragAnchor = undefined;
    viewer.scene.canvas.style.cursor = "grab";
  };
  dragHandler.setInputAction(stopMapDrag, C.ScreenSpaceEventType.LEFT_UP);
  viewer.scene.canvas.addEventListener("mouseleave", stopMapDrag);
  viewer.scene.canvas.style.cursor = "grab";

  viewer.scene.postProcessStages.fxaa.enabled = true;
  try {
    const imagery = await C.TileMapServiceImageryProvider.fromUrl(
      window.CESIUM_BASE_URL + "Assets/Textures/NaturalEarthII",
    );
    viewer.imageryLayers.addImageryProvider(imagery);
  } catch (error) {
    console.warn("离线底图加载失败", error);
  }
  try {
    viewer.imageryLayers.addImageryProvider(new C.UrlTemplateImageryProvider({
      url: "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
      credit: "地图数据 © OpenStreetMap 贡献者",
      maximumLevel: 19,
    }));
  } catch (error) {
    console.warn("在线地图不可用，使用本地底图", error);
  }
  try {
    const buildings = await C.GeoJsonDataSource.load("/static/maps/beijing-buildings.geojson", {clampToGround: false});
    viewer.dataSources.add(buildings);
    for (const building of buildings.entities.values) {
      if (!building.polygon) continue;
      const properties = building.properties?.getValue(C.JulianDate.now()) || {};
      const height = Number(properties.height) || 12;
      const minHeight = Number(properties.minHeight) || 0;
      building.polygon.height = minHeight;
      building.polygon.extrudedHeight = height;
      building.polygon.material = C.Color.fromCssColorString(height > 45 ? "#8fa6af" : "#718892").withAlpha(.9);
      building.polygon.outline = true;
      building.polygon.outlineColor = C.Color.fromCssColorString("#c4d2d7").withAlpha(.28);
      building.polygon.shadows = C.ShadowMode.ENABLED;
    }
  } catch (error) {
    console.warn("北京建筑图层加载失败", error);
  }

  const targetId = "beijing-flight-demo";
  let history = [], alerts = [], recommendations = [], telemetry = {};
  let situation = {sensors: [], externalTargets: []}, externalTargetEntities = [];
  let playing = true, segment = 0, segmentStart = performance.now(), following = false;
  let currentPosition = C.Cartesian3.fromDegrees(116.4074, 39.9042, 165);
  let currentOrientation = C.Quaternion.IDENTITY;
  const positionProperty = new C.CallbackProperty(() => currentPosition, false);
  const orientationProperty = new C.CallbackProperty(() => currentOrientation, false);
  const common = {position: positionProperty, orientation: orientationProperty};

  function addBuildings() {
    const colors = ["#426775", "#315666", "#52727b"];
    for (let index = 0; index < 54; index += 1) {
      const column = index % 9, row = Math.floor(index / 9);
      const height = 28 + ((index * 43) % 120);
      const width = 48 + ((index * 17) % 42);
      const depth = 42 + ((index * 29) % 48);
      viewer.entities.add({
        position: C.Cartesian3.fromDegrees(116.399 + column * .00205 + (row % 2) * .00035, 39.899 + row * .00185, height / 2),
        box: {dimensions: new C.Cartesian3(width, depth, height), material: C.Color.fromCssColorString(colors[index % 3]).withAlpha(.88), outline: true, outlineColor: C.Color.fromCssColorString("#8fb1bb").withAlpha(.42), shadows: C.ShadowMode.ENABLED},
      });
    }
  }
  // 真实地图模式不叠加人工方块建筑。

  const aircraft = viewer.entities.add({
    id: targetId, name: "演示飞机 UAV-01", ...common,
    model: {uri: "/static/models/Cesium_Air.glb", minimumPixelSize: 9, maximumScale: 6, scale: .15, shadows: C.ShadowMode.ENABLED},
    label: {text: "UAV-01  演示飞机", font: "12px sans-serif", fillColor: C.Color.fromCssColorString("#72e4ff"), showBackground: true, backgroundColor: C.Color.fromCssColorString("#071923").withAlpha(.86), pixelOffset: new C.Cartesian2(0, -24), distanceDisplayCondition: new C.DistanceDisplayCondition(0, 12000)},
  });
  viewer.entities.add({
    id: "friendly-ground-marker",
    position: new C.CallbackProperty(() => {
      const point = C.Cartographic.fromCartesian(currentPosition);
      return C.Cartesian3.fromRadians(point.longitude, point.latitude, 2);
    }, false),
    point: {pixelSize: 6, color: C.Color.fromCssColorString("#32c8ea"), outlineColor: C.Color.fromCssColorString("#d5f8ff"), outlineWidth: 1},
    ellipse: {semiMajorAxis: 15, semiMinorAxis: 15, material: C.Color.CYAN.withAlpha(.025), outline: true, outlineColor: C.Color.CYAN.withAlpha(.7), height: 1},
  });

  const threatPosition = C.Cartesian3.fromDegrees(116.4096, 39.9051, 110);
  const threatGroundPosition = C.Cartesian3.fromDegrees(116.4096, 39.9051, 2);
  viewer.entities.add({
    id: "threat-track-t01", name: "疑似威胁 T-01", position: threatPosition,
    point: {pixelSize: 11, color: C.Color.fromCssColorString("#ff5964"), outlineColor: C.Color.fromCssColorString("#ffe4e6"), outlineWidth: 2},
    label: {text: "T-01  疑似威胁\n置信度 86%", font: "12px sans-serif", fillColor: C.Color.fromCssColorString("#ff9aa1"), showBackground: true, backgroundColor: C.Color.fromCssColorString("#25090d").withAlpha(.88), pixelOffset: new C.Cartesian2(0, -31), distanceDisplayCondition: new C.DistanceDisplayCondition(0, 12000)},
  });
  viewer.entities.add({
    id: "threat-ground-ring", position: threatGroundPosition,
    ellipse: {
      semiMajorAxis: new C.CallbackProperty(() => 22 + Math.sin(performance.now() / 380) * 4, false),
      semiMinorAxis: new C.CallbackProperty(() => 22 + Math.sin(performance.now() / 380) * 4, false),
      material: C.Color.RED.withAlpha(.045), outline: true, outlineColor: C.Color.RED.withAlpha(.85), height: 1,
    },
  });
  viewer.entities.add({
    id: "threat-bearing-line",
    polyline: {
      positions: new C.CallbackProperty(() => [currentPosition, threatPosition], false),
      width: 1.5,
      material: new C.PolylineDashMaterialProperty({color: C.Color.fromCssColorString("#ff5964").withAlpha(.78), dashLength: 14}),
    },
  });

  const legend = document.createElement("div");
  legend.className = "map-legend";
  legend.innerHTML = '<span><i class="legend-friendly"></i>演示飞机</span><span><i class="legend-external"></i>外部航迹</span><span><i class="legend-threat"></i>威胁目标</span>';
  document.body.appendChild(legend);
  const riskBadge = document.querySelector(".risk");
  if (riskBadge) {
    riskBadge.textContent = "己方平台";
    riskBadge.classList.add("friendly");
  }

  const escapeHtml = value => String(value ?? "-").replace(/[&<>]/g, character => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[character]));
  const recommendationFor = alertId => recommendations.find(item => item.alertId === alertId);
  function quaternion(position, heading, pitch = 0, roll = 0) {
    return C.Transforms.headingPitchRollQuaternion(position, new C.HeadingPitchRoll(C.Math.toRadians(heading || 0), C.Math.toRadians(pitch || 0), C.Math.toRadians(roll || 0)));
  }
  function lerpAngleDegrees(start, end, ratio) {
    const from = Number(start) || 0, to = Number(end) || 0;
    return from + ((((to - from) % 360) + 540) % 360 - 180) * ratio;
  }


  function renderRecommendation(item) {
    if (!item) return "";
    return `<div class="recommend"><h4>${escapeHtml(item.summary)}</h4>${(item.actions || []).map(action => `<div class="step">${escapeHtml(action)}</div>`).join("")}<h4>知识依据</h4>${(item.references || []).map(reference => `<div class="ref">${escapeHtml(reference.title)}</div>`).join("")}<div class="ref">人工确认：必须</div></div>`;
  }
  function renderDrawer() {
    const attitude = telemetry.attitude || {};
    document.querySelector("#details").innerHTML = `<div class="section threat-summary"><div class="section-heading"><h3>关联威胁目标</h3><span class="threat-level">高风险</span></div><div class="track-title"><b>T-01 · 疑似威胁</b><span>置信度 86%</span></div><div class="track-meta">红色标记为威胁目标；虚线表示与演示飞机的态势关联，不代表其飞行航迹。</div></div><div class="section"><h3>演示飞机动态观测</h3><div class="kv"><span>平台状态</span><span>持续监控</span><span>关联告警</span><span>${alerts.length} 条</span><span>机载异常</span><span>发动机故障</span><span>姿态</span><span>横滚 ${attitude.rollDegrees ?? "-"}° / 俯仰 ${attitude.pitchDegrees ?? "-"}°</span></div></div><div class="section"><h3>威胁研判与处置建议</h3>${alerts.map(alert => `<div class="alert"><b>${escapeHtml(alert.title)}</b><p>${escapeHtml(alert.summary)}</p><button class="action" onclick="window.makeRecommendation('${alert.alertId}',this)">${recommendationFor(alert.alertId) ? "查看/刷新处置建议" : "生成处置建议"}</button>${renderRecommendation(recommendationFor(alert.alertId))}</div>`).join("") || '<span class="status">暂无开放告警</span>'}</div>`;
  }
  const sensorNames = {IMU: "惯性测量单元", GNSS: "卫星定位", AIRSPEED: "空速传感器", BATTERY: "电源系统", ENGINE: "发动机监测", BAROMETER: "气压高度计", ATTITUDE: "姿态估计", FLIGHT_CONTROLLER: "飞行控制器"};
  const sensorStatus = {NOMINAL: "正常", DEGRADED: "降级", UNKNOWN: "未知", OFFLINE: "失联"};
  const baseRenderDrawer = renderDrawer;
  renderDrawer = function renderSituationDrawer() {
    baseRenderDrawer();
    const details = document.querySelector("#details");
    const sensors = Array.isArray(situation.sensors) ? situation.sensors : [];
    const sensorHtml = sensors.map(sensor => {
      const metrics = sensor.metrics || {};
      const mainMetric = sensor.type === "AIRSPEED" ? `${metrics.airSpeedMps ?? "-"} 米/秒`
        : sensor.type === "BATTERY" ? `${metrics.voltageV ?? "-"} 伏`
        : sensor.type === "IMU" ? `横滚 ${metrics.rollDeg ?? "-"}° / 俯仰 ${metrics.pitchDeg ?? "-"}°`
        : sensor.type === "GNSS" ? `${Number(metrics.latitudeDeg || 0).toFixed(4)}, ${Number(metrics.longitudeDeg || 0).toFixed(4)}`
        : sensor.type === "ENGINE" ? (metrics.faultActive ? `故障：${metrics.faultType || "未知"}` : "未发现故障")
        : `质量 ${Math.round(Number(sensor.quality || 0) * 100)}%`;
      return `<div class="sensor-card ${escapeHtml(String(sensor.status || "UNKNOWN").toLowerCase())}"><div class="sensor-title"><b>${escapeHtml(sensorNames[sensor.type] || sensor.type)}</b><span>${escapeHtml(sensorStatus[sensor.status] || sensor.status)}</span></div><div class="sensor-value">${escapeHtml(mainMetric)}</div><div class="sensor-quality"><i style="width:${Math.round(Number(sensor.quality || 0) * 100)}%"></i></div></div>`;
    }).join("");
    const targetHtml = (situation.externalTargets || []).slice(0, 4).map(target =>
      `<div class="external-track"><b>${escapeHtml(target.callsign)}</b><span>${Math.round(Number(target.altitudeMeters || 0))} 米 · ${Math.round(Number(target.velocityMps || 0))} 米/秒</span><small>ADS-B · ${escapeHtml(target.icao24)}</small></div>`
    ).join("");
    details.insertAdjacentHTML("afterbegin", `
      <div class="section sensor-section">
        <div class="section-heading"><h3>机载传感器状态</h3><span>${sensors.filter(item => item.status === "NOMINAL").length}/${sensors.length} 正常</span></div>
        <div class="sensor-grid">${sensorHtml || '<span class="status">暂无传感器数据</span>'}</div>
      </div>
      <div class="section external-section">
        <div class="section-heading"><h3>外部航空目标</h3><span>OpenSky ${situation.externalTargets?.length || 0}</span></div>
        ${targetHtml || '<span class="status">暂无外部航迹</span>'}
      </div>`);
  };

  viewer.entities.add({
    id: "sensor-coverage-ring", position: positionProperty,
    ellipse: {
      semiMajorAxis: 220, semiMinorAxis: 220,
      material: C.Color.CYAN.withAlpha(.025), outline: true,
      outlineColor: C.Color.CYAN.withAlpha(.42), height: 2,
    },
  });

  window.makeRecommendation = async (alertId, button) => {
    button.disabled = true;
    try {
      const response = await fetch(`/api/v1/alerts/${alertId}/recommendation`, {method: "POST"});
      const body = await response.json();
      recommendations = recommendations.filter(item => item.alertId !== alertId);
      recommendations.unshift(body.recommendation);
      renderDrawer();
    } finally {
      button.disabled = false;
    }
  };

  function buildTrail() {
    const positions = history.map(point => C.Cartesian3.fromDegrees(point.longitudeDegrees, point.latitudeDegrees, point.altitudeMeters ?? 165));
    const old = viewer.entities.getById("flight-trail");
    if (old) viewer.entities.remove(old);
    viewer.entities.add({id: "flight-trail", polyline: {positions, width: 3, material: new C.PolylineGlowMaterialProperty({glowPower: .18, color: C.Color.CYAN})}});
  }
  function buildExternalTargets() {
    externalTargetEntities.forEach(item => viewer.entities.remove(item));
    externalTargetEntities = [];
    for (const target of situation.externalTargets || []) {
      const longitude = Number(target.longitudeDegrees), latitude = Number(target.latitudeDegrees);
      if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) continue;
      const entity = viewer.entities.add({
        id: target.trackId,
        position: C.Cartesian3.fromDegrees(longitude, latitude, Number(target.altitudeMeters) || 1000),
        point: {
          pixelSize: 8, color: C.Color.fromCssColorString("#f4c75b"),
          outlineColor: C.Color.BLACK, outlineWidth: 2,
          distanceDisplayCondition: new C.DistanceDisplayCondition(0, 500000),
        },
        label: {
          text: `${target.callsign} · ADS-B`, font: "11px sans-serif",
          fillColor: C.Color.fromCssColorString("#ffe7a4"), showBackground: true,
          backgroundColor: C.Color.BLACK.withAlpha(.7),
          pixelOffset: new C.Cartesian2(0, -18),
          distanceDisplayCondition: new C.DistanceDisplayCondition(0, 250000),
        },
      });
      externalTargetEntities.push(entity);
    }
  }
  function buildDisplayHistory(rawHistory) {
    const valid = (rawHistory || []).filter(point => Number.isFinite(Number(point.longitudeDegrees)) && Number.isFinite(Number(point.latitudeDegrees)));
    const unique = [];
    const keys = new Set();
    for (const point of valid) {
      const key = `${Number(point.longitudeDegrees).toFixed(6)}:${Number(point.latitudeDegrees).toFixed(6)}:${Number(point.altitudeMeters || 0).toFixed(1)}`;
      if (!keys.has(key)) { keys.add(key); unique.push(point); }
    }
    if (unique.length >= 8) return valid;
    const anchor = unique[0] || {longitudeDegrees: 116.4078, latitudeDegrees: 39.9042, altitudeMeters: 165};
    const centerLon = Number(anchor.longitudeDegrees), centerLat = Number(anchor.latitudeDegrees);
    const count = 32, radiusLon = .0045, radiusLat = .0025;
    return Array.from({length: count}, (_, index) => {
      const angle = Math.PI * 2 * index / count;
      const longitudeDegrees = centerLon + radiusLon * Math.cos(angle);
      const latitudeDegrees = centerLat + radiusLat * Math.sin(angle);
      const altitudeMeters = 175 + 12 * Math.sin(angle * 2 - .5);
      const eastTangent = -radiusLon * Math.sin(angle) * 85000;
      const northTangent = radiusLat * Math.cos(angle) * 111000;
      const headingDegrees = (C.Math.toDegrees(Math.atan2(eastTangent, northTangent)) + 360) % 360;
      const pitchDegrees = Math.max(-5, Math.min(5, 4.5 * Math.cos(angle * 2 - .5)));
      const rollDegrees = -14 - 3 * Math.sin(angle);
      return {longitudeDegrees, latitudeDegrees, altitudeMeters, headingDegrees, yawDegrees: headingDegrees, rollDegrees, pitchDegrees, generatedForDisplay: true};
    });
  }

  function segmentDuration(start, end) {
    const east = (Number(end.longitudeDegrees) - Number(start.longitudeDegrees)) * 85000;
    const north = (Number(end.latitudeDegrees) - Number(start.latitudeDegrees)) * 111000;
    const vertical = Number(end.altitudeMeters || 0) - Number(start.altitudeMeters || 0);
    const distance = Math.hypot(east, north, vertical);
    const velocity = Number(telemetry.velocity?.groundSpeedMetersPerSecond || telemetry.velocity?.airSpeedMetersPerSecond || 30);
    return Math.max(1800, Math.min(5200, distance / Math.max(velocity, 8) * 1000));
  }

  function smoothStep(value) {
    return value * value * (3 - 2 * value);
  }


  async function loadData() {
    const [entityResponse, historyResponse, alertResponse, recommendationResponse] = await Promise.all([
      fetch(`/api/v1/entities/${targetId}`), fetch(`/api/v1/tracks/${targetId}/history`),
      fetch("/api/v1/alerts"), fetch("/api/v1/recommendations"),
    ]);
    if (!entityResponse.ok) throw new Error("请先运行北京样例回放");
    const entity = await entityResponse.json(), historyBody = await historyResponse.json();
    const alertBody = await alertResponse.json(), recommendationBody = await recommendationResponse.json();
    telemetry = entity.flightTelemetry || {};
    history = buildDisplayHistory(historyBody.history || []);
    alerts = (Array.isArray(alertBody) ? alertBody : (alertBody.alerts || [])).filter(item => item.entityId === targetId && item.status !== "RESOLVED");
    recommendations = Array.isArray(recommendationBody) ? recommendationBody : (recommendationBody.recommendations || []);
    document.querySelector("#name").textContent = "UAV-01 · 演示飞机";
    document.querySelector("#point-count").textContent = history.length;
    const situationResponse = await fetch(`/api/v1/situation/${targetId}`);
    situation = situationResponse.ok ? await situationResponse.json() : {sensors: [], externalTargets: []};
    document.querySelector("#airspeed").textContent = `${telemetry.velocity?.airSpeedMetersPerSecond ?? "-"} 米/秒`;
    buildTrail(); buildExternalTargets(); renderDrawer();
    document.querySelector("#connection").textContent = "● 三维数据链路正常";
    document.querySelector("#connection").className = "status ok";
  }

  async function ensureDemoData() {
    const existing = await fetch(`/api/v1/entities/${targetId}`);
    if (existing.ok) return;
    const response = await fetch("/api/v1/demo/minimal-validation", {method: "POST"});
    if (!response.ok) throw new Error("最小验证场景初始化失败");
    const result = await response.json();
    if (!result.ok) throw new Error("最小验证链路未通过");
  }

  function animate(now) {
    if (playing && history.length > 1) {
      const start = history[segment % history.length], end = history[(segment + 1) % history.length];
      const duration = segmentDuration(start, end);
      const linearRatio = Math.min((now - segmentStart) / duration, 1);
      const ratio = smoothStep(linearRatio);
      const longitude = C.Math.lerp(Number(start.longitudeDegrees), Number(end.longitudeDegrees), ratio);
      const latitude = C.Math.lerp(Number(start.latitudeDegrees), Number(end.latitudeDegrees), ratio);
      const altitude = C.Math.lerp(Number(start.altitudeMeters ?? 165), Number(end.altitudeMeters ?? 165), ratio);
      const heading = lerpAngleDegrees(start.headingDegrees ?? start.yawDegrees, end.headingDegrees ?? end.yawDegrees, ratio);
      const roll = C.Math.lerp(Number(start.rollDegrees) || 0, Number(end.rollDegrees) || 0, ratio);
      const pitch = C.Math.lerp(Number(start.pitchDegrees) || 0, Number(end.pitchDegrees) || 0, ratio);
      currentPosition = C.Cartesian3.fromDegrees(longitude, latitude, altitude);
      currentOrientation = quaternion(currentPosition, heading, pitch, roll);
      document.querySelector("#height").textContent = `${altitude.toFixed(1)} 米`;
      document.querySelector("#heading").textContent = `${heading.toFixed(1)}°`;
      telemetry.attitude = {...(telemetry.attitude || {}), rollDegrees: roll.toFixed(1), pitchDegrees: pitch.toFixed(1), yawDegrees: heading.toFixed(1)};
      if (linearRatio >= 1) { segment = (segment + 1) % history.length; segmentStart = now; }
    }
    viewer.scene.requestRender(); requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  document.querySelectorAll("[data-mode]").forEach(button => button.onclick = () => {
    document.querySelectorAll("[data-mode]").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    const mode = button.dataset.mode;
    if (mode === "2D") viewer.scene.morphTo2D(1);
    else if (mode === "CV") viewer.scene.morphToColumbusView(1);
    else viewer.scene.morphTo3D(1);
    document.querySelector("#mode-label").textContent = mode === "2D" ? "二维模式" : mode === "CV" ? "2.5D模式" : "三维模式";
  });
  document.querySelector("#toggle").onclick = event => { playing = !playing; event.target.textContent = playing ? "暂停" : "播放"; document.querySelector("#play-state").textContent = playing ? "播放中" : "已暂停"; segmentStart = performance.now(); };
  document.querySelector("#follow").onclick = event => { following = !following; viewer.trackedEntity = following ? aircraft : undefined; event.target.textContent = following ? "取消跟随" : "跟随飞机"; };
  function focusScene() {
    viewer.trackedEntity = undefined;
    following = false;
    viewer.scene.morphTo3D(0);
    const center = C.Cartesian3.fromDegrees(116.40762, 39.90421, 130);
    const offset = new C.HeadingPitchRange(C.Math.toRadians(22), C.Math.toRadians(-32), 900);
    viewer.camera.lookAt(center, offset);
    viewer.camera.lookAtTransform(C.Matrix4.IDENTITY);
  }
  const overview = () => focusScene();
  document.querySelector("#overview").onclick = overview;
  focusScene();
  try { await ensureDemoData(); await loadData(); } catch (error) { document.querySelector("#connection").textContent = `● ${error.message}`; document.querySelector("#details").textContent = error.message; }
  setInterval(loadData, 5000);
})();
