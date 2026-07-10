"use strict";

// EPB outage status -> marker color, matching epb.com/outage-storm-center's map.
const EPB_STATUS_COLORS = {
  OUTAGE_REPORTED: "#E10101",    // Outage Reported (red)
  EN_ROUTE: "#F97B06",           // Crew En Route (orange)
  REPAIR_IN_PROGRESS: "#0392CF", // Repair in Progress (blue)
  RESTORED: "#76A84F",           // Restored (green)
  Closed: "#76A84F",             // dropped from the feed == service restored
};
// EPB scales each marker by customers affected (16 + n*0.024, bucketed), like its map.
function epbMarkerSize(p) {
  const n = Number(p.customer_quantity);
  const s = 16 + (Number.isFinite(n) ? n * 0.024 : 0);
  return s >= 40 ? 40 : s >= 32 ? 32 : s >= 24 ? 24 : 16;
}

// ---- per-source config -------------------------------------------------------
// The backend is source-agnostic; the only source-specific knowledge is here:
// each source's categories, their colors, and how to pull a title / location /
// jurisdiction / detail rows out of a feature's properties. Features carry their
// own `source`, so every render looks up config per-feature (see cfgFor) — that's
// what lets several sources be shown on the map at once.
const SOURCES = {
  hc911: {
    name: "Hamilton County 911",
    short: "911",
    categories: ["police", "fire", "ems", "other"],
    colors: { police: "#2563eb", fire: "#dc2626", ems: "#059669", other: "#6b7280" },
    title: (p) => p.label || p.type || "Incident",
    location: (p) => p.location || "",
    jurisdiction: (p) => p.jurisdiction || "",
    detail: (p, d) => [
      ["Status", p.status], ["Agency", p.agency_type], ["Jurisdiction", p.jurisdiction],
      ["Location", p.location], ["Cross streets", p.crossstreets], ["City", p.city],
      ["Priority", p.priority], ["Incident #", p.sequencenumber], ["Active", String(d.is_active)],
    ],
  },
  tdot: {
    name: "TDOT SmartWay",
    short: "TDOT",
    categories: ["incident", "construction", "special_event", "severe"],
    colors: { incident: "#2563eb", construction: "#d97706", special_event: "#7c3aed", severe: "#dc2626" },
    title: (p) => p.label || p.eventTypeName || "Event",
    location: (p) => p.description || tdotCounty(p) || "",
    jurisdiction: (p) => tdotCounty(p),
    detail: (p, d) => [
      ["Status", p.status], ["Type", p.eventTypeName], ["Subtype", p.eventSubTypeDescription],
      ["Direction", p.directionDescription], ["Impact", p.impactDescription],
      ["County", tdotCounty(p)], ["Route mile", p.mileMarker],
      ["Severe", p.isSevere ? "Yes" : null], ["Active", String(d.is_active)],
      ["Description", p.description],
    ],
  },
  epb: {
    name: "EPB Outages",
    short: "EPB",
    categories: ["energy", "fiber"],
    colors: { energy: "#d97706", fiber: "#0891b2" },
    // EPB's map colors a marker by outage status and sizes it by customers affected,
    // shown as a round dot rather than the default teardrop pin.
    round: true,
    markerColor: (p) => EPB_STATUS_COLORS[p.status] || "#666666",
    markerSize: epbMarkerSize,
    title: (p) => p.label || (p.service === "fiber" ? "Fiber Outage" : "Energy Outage"),
    location: (p) => "",
    jurisdiction: (p) => cap(p.service || ""),
    detail: (p, d) => [
      ["Status", catLabel(p.status)], ["Service", cap(p.service || "")],
      ["Customers affected", p.customer_quantity], ["Active", String(d.is_active)],
    ],
  },
};
const tdotCounty = (p) => (p.locations && p.locations[0] && p.locations[0].countyName) || "";

// Fallback for a feature whose source has no client config (shouldn't happen).
const FALLBACK = {
  name: "Unknown", short: "?", categories: [], colors: {},
  title: (p) => p.label || "Item", location: (p) => p.location || "",
  jurisdiction: (p) => p.jurisdiction || "",
  detail: (p, d) => [["Status", p.status], ["Active", String(d.is_active)]],
};
const cfgFor = (key) => SOURCES[key] || FALLBACK;

const DEFAULT_VIEW = { center: [35.0456, -85.3097], zoom: 11 };  // Chattanooga, TN area

// ---- state -------------------------------------------------------------------
const selectedSources = new Set(Object.keys(SOURCES));  // all sources on by default

const features = new Map();   // entity id (globally unique) -> GeoJSON feature
const markers = new Map();    // entity id -> Leaflet marker
const filters = { categories: new Set(), status: "", jurisdiction: "", search: "", showClosed: false, closedWindow: 60 };

const isClosed = (f) => f.properties.active === false;
const catLabel = (cat) => cap(String(cat || "").replace(/_/g, " "));
const colorFor = (sourceKey, cat) => cfgFor(sourceKey).colors[cat] || "#6b7280";
// A feature's display color: a source may color by status/properties (e.g. EPB
// outage status); otherwise fall back to its category color.
const featureColor = (f) => {
  const cfg = cfgFor(f.properties.source);
  return cfg.markerColor ? cfg.markerColor(f.properties) : colorFor(f.properties.source, f.properties.category);
};

// Categories across the currently-selected sources, de-duped by name.
function selectedCategories() {
  const out = [];
  for (const key of selectedSources) {
    for (const c of cfgFor(key).categories) if (!out.includes(c)) out.push(c);
  }
  return out;
}
// Color for a category checkbox/dot (from whichever selected source defines it).
function catColor(cat) {
  for (const key of selectedSources) {
    const c = cfgFor(key).colors[cat];
    if (c) return c;
  }
  return "#6b7280";
}

let map, cluster, trackLayer, socket;

// ---- map setup ---------------------------------------------------------------
async function initMap() {
  const cfg = await fetch("/api/config").then((r) => r.json());
  map = L.map("map").setView(DEFAULT_VIEW.center, DEFAULT_VIEW.zoom);
  L.tileLayer(cfg.tile_url, { attribution: cfg.tile_attribution, maxZoom: 18 }).addTo(map);
  // Only group markers that share the same location (coincident points); every
  // distinct outage is shown individually. A 1px radius means nothing clusters
  // unless the points overlap, and identical coordinates can still be spiderfied.
  cluster = L.markerClusterGroup({ maxClusterRadius: 1 });
  map.addLayer(cluster);
  trackLayer = L.layerGroup().addTo(map);
  addStatusLegend();
}

// EPB-style status legend (matches the outage-status marker colors).
function addStatusLegend() {
  const legend = L.control({ position: "bottomright" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "map-legend");
    div.innerHTML = "<b>EPB Outage Status</b>" + [
      ["Outage Reported", EPB_STATUS_COLORS.OUTAGE_REPORTED],
      ["Crew En Route", EPB_STATUS_COLORS.EN_ROUTE],
      ["Repair in Progress", EPB_STATUS_COLORS.REPAIR_IN_PROGRESS],
      ["Restored", EPB_STATUS_COLORS.RESTORED],
    ].map(([t, c]) => `<div><span class="lg-dot" style="background:${c}"></span>${t}</div>`).join("");
    return div;
  };
  legend.addTo(map);
}

function markerIcon(f) {
  const p = f.properties;
  const cfg = cfgFor(p.source);
  const closed = isClosed(f);
  const color = featureColor(f);
  // Round dot (sized per-source) for sources like EPB; teardrop pin otherwise.
  if (cfg.round) {
    const size = cfg.markerSize ? cfg.markerSize(p) : 16;
    return L.divIcon({
      className: "",
      html: `<div class="marker-dot${closed ? " closed" : ""}" style="width:${size}px;height:${size}px;background:${color}"></div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -(size / 2) - 2],
    });
  }
  return L.divIcon({
    className: "",
    html: `<div class="marker-pin${closed ? " closed" : ""}" style="background:${color}"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 16],
    popupAnchor: [0, -16],
  });
}

// ---- rendering ---------------------------------------------------------------
function passesFilters(f) {
  const p = f.properties;
  if (!selectedSources.has(p.source)) return false;
  if (isClosed(f) && !filters.showClosed) return false;
  if (!filters.categories.has(p.category)) return false;
  if (filters.status && p.status !== filters.status) return false;
  const cfg = cfgFor(p.source);
  if (filters.jurisdiction && cfg.jurisdiction(p) !== filters.jurisdiction) return false;
  if (filters.search) {
    const hay = `${cfg.title(p)} ${cfg.location(p)} ${p.status || ""}`.toLowerCase();
    if (!hay.includes(filters.search.toLowerCase())) return false;
  }
  return true;
}

function upsertFeature(f) {
  features.set(f.id, f);
  renderMarker(f);
}

function renderMarker(f) {
  const existing = markers.get(f.id);
  if (existing) { cluster.removeLayer(existing); markers.delete(f.id); }
  if (!passesFilters(f) || !f.geometry) return;

  const [lon, lat] = f.geometry.coordinates;
  const marker = L.marker([lat, lon], { icon: markerIcon(f) });
  marker.bindPopup(popupHtml(f));
  marker.on("click", () => showDetail(f.id));
  cluster.addLayer(marker);
  markers.set(f.id, marker);
}

function removeFeature(id) {
  features.delete(id);
  const m = markers.get(id);
  if (m) { cluster.removeLayer(m); markers.delete(id); }
}

// An incident dropped out of the feed. Keep it (muted) when "show closed" is on,
// otherwise remove it from the map entirely.
function closeFeature(id) {
  const f = features.get(id);
  if (!filters.showClosed || !f) { removeFeature(id); return; }
  f.properties.active = false;
  f.properties.status = "Closed";
  f.properties.last_seen_at = new Date().toISOString();
  renderMarker(f);
}

function popupHtml(f) {
  const p = f.properties;
  const cfg = cfgFor(p.source);
  return `<strong>${esc(cfg.title(p))}</strong><br>
    <span class="popup-src">${esc(cfg.short)}</span> &middot; ${esc(p.status || "")} &middot; ${esc(cfg.jurisdiction(p))}<br>
    ${esc(cfg.location(p))}`;
}

function refreshAll() {
  // Reconcile dropdowns first: a selected value that no longer exists (e.g. "Closed"
  // after hiding closed incidents) is cleared so state and UI stay in sync.
  renderFilterOptions();
  for (const f of features.values()) renderMarker(f);
  renderTable();
}

function renderTable() {
  const tbody = document.querySelector("#incident-table tbody");
  const visible = [...features.values()].filter(passesFilters)
    .sort((a, b) => (b.properties.last_seen_at || "").localeCompare(a.properties.last_seen_at || ""));
  document.getElementById("count").textContent = visible.length;
  tbody.innerHTML = "";
  for (const f of visible) {
    const p = f.properties;
    const cfg = cfgFor(p.source);
    const closed = isClosed(f);
    const tr = document.createElement("tr");
    if (closed) tr.classList.add("closed-row");
    const dot = closed
      ? `<span class="dot cat-closed"></span>`
      : `<span class="dot" style="background:${featureColor(f)}"></span>`;
    const statusCell = closed ? `<span class="badge-closed">Closed</span>` : esc(p.status || "");
    tr.innerHTML = `<td>${esc(cfg.short)}</td>
      <td>${dot} ${esc(catLabel(p.category))}</td>
      <td>${statusCell}</td><td>${esc(cfg.title(p))}</td><td>${esc(cfg.location(p))}</td>`;
    tr.addEventListener("click", () => { showDetail(f.id); if (f.geometry) map.flyTo([f.geometry.coordinates[1], f.geometry.coordinates[0]], 15); });
    tbody.appendChild(tr);
  }
}

function renderFilterOptions() {
  // Populate status + jurisdiction dropdowns from current data, preserving selection.
  reconcileSelect("status-filter", "status", uniq((f) => f.properties.status));
  reconcileSelect("jurisdiction-filter", "jurisdiction", uniq((f) => cfgFor(f.properties.source).jurisdiction(f.properties)));
}

// Rebuild a select's options and drop the active filter if its value is gone, so
// the dropdown's displayed value and `filters[key]` never diverge.
function reconcileSelect(id, filterKey, values) {
  if (filters[filterKey] && !values.includes(filters[filterKey])) {
    filters[filterKey] = "";
  }
  fillSelect(id, values, filters[filterKey]);
}

function uniq(getter) {
  return [...new Set([...features.values()].filter((f) => selectedSources.has(f.properties.source)).map(getter).filter(Boolean))].sort();
}

function fillSelect(id, values, current) {
  const sel = document.getElementById(id);
  if (sel.dataset.values === values.join("|")) return; // unchanged
  sel.dataset.values = values.join("|");
  sel.innerHTML = `<option value="">All</option>` +
    values.map((v) => `<option value="${esc(v)}"${v === current ? " selected" : ""}>${esc(v)}</option>`).join("");
}

// ---- detail / track ----------------------------------------------------------
async function showDetail(id) {
  const panel = document.getElementById("detail");
  const body = document.getElementById("detail-body");
  body.innerHTML = "Loading…";
  panel.classList.remove("hidden");

  const d = await fetch(`/api/entities/${id}`).then((r) => r.json());
  const cfg = cfgFor(d.source);
  const p = d.latest_properties || {};
  const rows = [["Source", cfg.name], ...cfg.detail(p, d)].filter(([, v]) => v != null && v !== "");

  body.innerHTML =
    `<h3>${esc(d.label || cfg.title(p))}</h3>` +
    rows.map(([k, v]) => `<div class="kv"><b>${esc(k)}</b>${esc(String(v))}</div>`).join("") +
    `<h2>History (${d.track.length})</h2>` +
    `<ul class="track">` +
    d.track.slice().reverse().map((t) =>
      `<li><span class="t">${fmt(t.observed_at)}</span> — ${esc(t.status || "")}</li>`).join("") +
    `</ul>`;

  drawTrack(d.track);
}

function drawTrack(track) {
  trackLayer.clearLayers();
  const pts = track.filter((t) => t.lat != null && t.lon != null).map((t) => [t.lat, t.lon]);
  if (pts.length > 1) L.polyline(pts, { color: "#111", weight: 2, dashArray: "4 4" }).addTo(trackLayer);
  for (const t of track) {
    if (t.lat != null && t.lon != null) {
      L.circleMarker([t.lat, t.lon], { radius: 4, color: "#111", fillColor: "#fff", fillOpacity: 1 })
        .bindTooltip(`${t.status || ""} @ ${fmt(t.observed_at)}`).addTo(trackLayer);
    }
  }
}

// ---- data loading + live updates ---------------------------------------------
async function fetchSourceInto(key) {
  let url = `/api/active?source=${key}`;
  if (filters.showClosed) url += `&include_closed=true&closed_within_minutes=${filters.closedWindow}`;
  const fc = await fetch(url).then((r) => r.json());
  for (const f of fc.features) features.set(f.id, f);
}

// Reload every selected source from scratch (used on first load + closed-window changes).
async function loadActive() {
  for (const m of markers.values()) cluster.removeLayer(m);
  markers.clear();
  features.clear();
  await Promise.all([...selectedSources].map(fetchSourceInto));
  refreshAll();
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  // No source filter: subscribe to every source and filter client-side by selectedSources.
  socket = new WebSocket(`${proto}://${location.host}/api/ws/live`);
  const bar = document.getElementById("status-bar");
  socket.onopen = () => { bar.textContent = "live"; bar.className = "status-bar ok"; };
  socket.onclose = () => {
    bar.textContent = "disconnected — retrying"; bar.className = "status-bar err";
    setTimeout(connectWs, 3000);
  };
  socket.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type !== "diff" || !selectedSources.has(msg.source)) return;  // ignore muted sources
    for (const f of msg.new) upsertFeature(f);
    for (const f of msg.updated) upsertFeature(f);
    for (const id of msg.closed) closeFeature(id);
    renderFilterOptions();  // reconcile selections before rendering the table
    renderTable();
  };
}

// ---- source selection --------------------------------------------------------
async function toggleSource(key, on) {
  if (!SOURCES[key]) return;
  if (on) {
    selectedSources.add(key);
    for (const c of cfgFor(key).categories) filters.categories.add(c);  // show its categories
    initCategoryFilters();
    await fetchSourceInto(key);
    refreshAll();
  } else {
    selectedSources.delete(key);
    const stillVisible = new Set(selectedCategories());
    for (const c of cfgFor(key).categories) if (!stillVisible.has(c)) filters.categories.delete(c);
    for (const [id, f] of [...features]) if (f.properties.source === key) removeFeature(id);
    initCategoryFilters();
    refreshAll();
  }
}

// ---- filter wiring -----------------------------------------------------------
function initSourceFilters() {
  const box = document.getElementById("source-filters");
  box.innerHTML = Object.entries(SOURCES).map(([key, s]) =>
    `<label><input type="checkbox" value="${key}"${selectedSources.has(key) ? " checked" : ""}> ${esc(s.name)}</label>`).join("");
  box.addEventListener("change", (e) => toggleSource(e.target.value, e.target.checked));
}

function initCategoryFilters() {
  const box = document.getElementById("category-filters");
  box.innerHTML = selectedCategories().map((c) =>
    `<label><input type="checkbox" value="${c}"${filters.categories.has(c) ? " checked" : ""}> <span class="dot" style="background:${catColor(c)}"></span>${catLabel(c)}</label>`).join("");
}

function initFilters() {
  initSourceFilters();

  // Default: every category of every selected source enabled.
  for (const c of selectedCategories()) filters.categories.add(c);
  initCategoryFilters();

  document.getElementById("category-filters").addEventListener("change", (e) => {
    const v = e.target.value;
    if (e.target.checked) filters.categories.add(v); else filters.categories.delete(v);
    refreshAll();
  });
  document.getElementById("status-filter").addEventListener("change", (e) => { filters.status = e.target.value; refreshAll(); });
  document.getElementById("jurisdiction-filter").addEventListener("change", (e) => { filters.jurisdiction = e.target.value; refreshAll(); });
  document.getElementById("search").addEventListener("input", (e) => { filters.search = e.target.value; refreshAll(); });

  const windowRow = document.getElementById("closed-window-row");
  document.getElementById("show-closed").addEventListener("change", (e) => {
    filters.showClosed = e.target.checked;
    windowRow.classList.toggle("hidden", !filters.showClosed);
    loadActive();  // refetch: pulls in (or drops) closed incidents server-side
  });
  document.getElementById("closed-window").addEventListener("change", (e) => {
    filters.closedWindow = Number(e.target.value);
    if (filters.showClosed) loadActive();
  });

  document.getElementById("detail-close").addEventListener("click", () => {
    document.getElementById("detail").classList.add("hidden");
    trackLayer.clearLayers();
  });
}

// ---- utils -------------------------------------------------------------------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");
const fmt = (iso) => { try { return new Date(iso).toLocaleString(); } catch { return iso; } };

// ---- boot --------------------------------------------------------------------
(async function main() {
  initFilters();
  await initMap();
  await loadActive();
  connectWs();
})();
