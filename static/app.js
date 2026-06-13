"use strict";

// ---- state -------------------------------------------------------------------
const SOURCE = "hc911";
const CATEGORIES = ["police", "fire", "ems", "other"];
const CAT_COLOR = { police: "#2563eb", fire: "#dc2626", ems: "#059669", other: "#6b7280" };

const features = new Map();   // entity id -> GeoJSON feature
const markers = new Map();    // entity id -> Leaflet marker
const filters = { categories: new Set(CATEGORIES), status: "", jurisdiction: "", search: "" };

let map, cluster, trackLayer;

// ---- map setup ---------------------------------------------------------------
async function initMap() {
  const cfg = await fetch("/api/config").then((r) => r.json());
  map = L.map("map").setView([35.0887, -85.2399], 11);
  L.tileLayer(cfg.tile_url, { attribution: cfg.tile_attribution, maxZoom: 18 }).addTo(map);
  cluster = L.markerClusterGroup({ maxClusterRadius: 45 });
  map.addLayer(cluster);
  trackLayer = L.layerGroup().addTo(map);
}

function markerIcon(category) {
  const color = CAT_COLOR[category] || CAT_COLOR.other;
  return L.divIcon({
    className: "",
    html: `<div class="marker-pin" style="background:${color}"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 16],
    popupAnchor: [0, -16],
  });
}

// ---- rendering ---------------------------------------------------------------
function passesFilters(f) {
  const p = f.properties;
  if (!filters.categories.has(p.category)) return false;
  if (filters.status && p.status !== filters.status) return false;
  if (filters.jurisdiction && p.jurisdiction !== filters.jurisdiction) return false;
  if (filters.search) {
    const hay = `${p.type || ""} ${p.location || ""} ${p.label || ""} ${p.status || ""}`.toLowerCase();
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
  const p = f.properties;
  const marker = L.marker([lat, lon], { icon: markerIcon(p.category) });
  marker.bindPopup(popupHtml(p));
  marker.on("click", () => showDetail(f.id));
  cluster.addLayer(marker);
  markers.set(f.id, marker);
}

function removeFeature(id) {
  features.delete(id);
  const m = markers.get(id);
  if (m) { cluster.removeLayer(m); markers.delete(id); }
}

function popupHtml(p) {
  return `<strong>${esc(p.label || p.type || "Incident")}</strong><br>
    ${esc(p.status || "")} &middot; ${esc(p.jurisdiction || "")}<br>
    ${esc(p.location || "")}`;
}

function refreshAll() {
  for (const f of features.values()) renderMarker(f);
  renderTable();
  renderFilterOptions();
}

function renderTable() {
  const tbody = document.querySelector("#incident-table tbody");
  const visible = [...features.values()].filter(passesFilters)
    .sort((a, b) => (b.properties.last_seen_at || "").localeCompare(a.properties.last_seen_at || ""));
  document.getElementById("count").textContent = visible.length;
  tbody.innerHTML = "";
  for (const f of visible) {
    const p = f.properties;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><span class="dot cat-${p.category}"></span> ${esc(cap(p.category))}</td>
      <td>${esc(p.status || "")}</td><td>${esc(p.label || p.type || "")}</td><td>${esc(p.location || "")}</td>`;
    tr.addEventListener("click", () => { showDetail(f.id); if (f.geometry) map.flyTo([f.geometry.coordinates[1], f.geometry.coordinates[0]], 15); });
    tbody.appendChild(tr);
  }
}

function renderFilterOptions() {
  // Populate status + jurisdiction dropdowns from current data, preserving selection.
  fillSelect("status-filter", uniq((f) => f.properties.status), filters.status);
  fillSelect("jurisdiction-filter", uniq((f) => f.properties.jurisdiction), filters.jurisdiction);
}

function uniq(getter) {
  return [...new Set([...features.values()].map(getter).filter(Boolean))].sort();
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
  const p = d.latest_properties || {};
  const rows = [
    ["Status", p.status], ["Agency", p.agency_type], ["Jurisdiction", p.jurisdiction],
    ["Location", p.location], ["Cross streets", p.crossstreets], ["City", p.city],
    ["Priority", p.priority], ["Incident #", p.sequencenumber], ["Active", String(d.is_active)],
  ].filter(([, v]) => v != null && v !== "");

  body.innerHTML =
    `<h3>${esc(d.label || p.type || "Incident")}</h3>` +
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
async function loadActive() {
  const fc = await fetch(`/api/active?source=${SOURCE}`).then((r) => r.json());
  for (const f of fc.features) features.set(f.id, f);
  refreshAll();
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/ws/live?source=${SOURCE}`);
  const bar = document.getElementById("status-bar");
  ws.onopen = () => { bar.textContent = "live"; bar.className = "status-bar ok"; };
  ws.onclose = () => {
    bar.textContent = "disconnected — retrying"; bar.className = "status-bar err";
    setTimeout(connectWs, 3000);
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type !== "diff") return;
    for (const f of msg.new) upsertFeature(f);
    for (const f of msg.updated) upsertFeature(f);
    for (const id of msg.closed) removeFeature(id);
    renderTable();
    renderFilterOptions();
  };
}

// ---- filter wiring -----------------------------------------------------------
function initFilters() {
  const box = document.getElementById("category-filters");
  box.innerHTML = CATEGORIES.map((c) =>
    `<label><input type="checkbox" value="${c}" checked> <span class="dot cat-${c}"></span>${cap(c)}</label>`).join("");
  box.addEventListener("change", (e) => {
    const v = e.target.value;
    if (e.target.checked) filters.categories.add(v); else filters.categories.delete(v);
    refreshAll();
  });
  document.getElementById("status-filter").addEventListener("change", (e) => { filters.status = e.target.value; refreshAll(); });
  document.getElementById("jurisdiction-filter").addEventListener("change", (e) => { filters.jurisdiction = e.target.value; refreshAll(); });
  document.getElementById("search").addEventListener("input", (e) => { filters.search = e.target.value; refreshAll(); });
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
