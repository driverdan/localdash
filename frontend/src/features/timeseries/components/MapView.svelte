<script lang="ts">
  import { onMount } from "svelte";
  import L from "leaflet";
  import "leaflet.markercluster";
  import "leaflet/dist/leaflet.css";
  import "leaflet.markercluster/dist/MarkerCluster.css";
  import "leaflet.markercluster/dist/MarkerCluster.Default.css";
  import { fetchConfig, type AppConfig } from "../../../lib/api";
  import { asNumber, loadPrefs, savePrefs } from "../../../lib/prefs.svelte";
  import { activeTheme } from "../../../lib/theme.svelte";
  import { esc, fmt } from "../../../lib/format";
  import {
    EPB_STATUS_COLORS,
    cfgFor,
    featureColor,
    iconFor,
    isClosed,
    statusLabelForRaw,
  } from "../sources";
  import { iconSvg } from "../../../lib/icons";
  import { debug } from "../../../lib/debug.svelte";
  import { ts } from "../state.svelte";
  import type { EntityId, TrackedFeature } from "../types";

  const DEFAULT_VIEW = {
    center: [35.0456, -85.3097] as [number, number],
    zoom: 12,
  }; // Chattanooga, TN area

  // Persisted map viewport. Deliberately a separate localStorage key from the
  // `localdash.map` filter blob (owned by state.svelte's persistPrefs): that blob's
  // key-presence flips filtering into allowlist mode, so folding the viewport in
  // would make merely panning the map silently change future source-filtering.
  const VIEW_PREFS_KEY = "localdash.map.view";

  // Restore the saved viewport, or null when there is none / it is unusable. All
  // three fields must be finite numbers — a partially valid record is treated as
  // no record, so we never open a half-restored (e.g. wrong-zoom) view.
  function loadSavedView(): { center: [number, number]; zoom: number } | null {
    const saved = loadPrefs(VIEW_PREFS_KEY);
    if (!saved) return null;
    const zoom = asNumber(saved.zoom);
    const lat = asNumber(saved.lat);
    const lng = asNumber(saved.lng);
    if (zoom == null || lat == null || lng == null) return null;
    return { center: [lat, lng], zoom };
  }

  let mapEl = $state<HTMLElement>();
  let ready = $state(false);
  let cfg = $state<AppConfig>();
  let map: L.Map | undefined;
  let cluster: L.MarkerClusterGroup | undefined;
  // Polygon (area) features render here, deliberately outside the marker cluster —
  // clustering only makes sense for point markers.
  let polyLayer: L.LayerGroup | undefined;
  let trackLayer: L.LayerGroup | undefined;
  let tileLayer: L.TileLayer | undefined;

  onMount(() => {
    let disposed = false;
    (async () => {
      const loaded = await fetchConfig();
      if (disposed) return;
      cfg = loaded;
      // maxZoom lives on the map (not only the tile layer) because the basemap is
      // added later, in the theme effect below — without it Leaflet throws
      // "Map has no maxZoom specified" when the cluster/markers initialise here.
      // Resume the user's last viewport when saved; otherwise the default view.
      const view = loadSavedView() ?? DEFAULT_VIEW;
      map = L.map(mapEl!, { maxZoom: 18 }).setView(view.center, view.zoom);
      // Basemap follows the active theme (see the effect below); Leaflet panes
      // keep tiles under the markers regardless of add order.
      // Only group markers that share the same location (coincident points); every
      // distinct incident is shown individually. A 1px radius means nothing clusters
      // unless the points overlap, and identical coordinates can still be spiderfied.
      cluster = L.markerClusterGroup({ maxClusterRadius: 1 });
      map.addLayer(cluster);
      polyLayer = L.layerGroup().addTo(map);
      trackLayer = L.layerGroup().addTo(map);
      addStatusLegend(map);
      // Mirror the live viewport out to the shell debug store (read by DebugPanel).
      // Seed once on init, then keep it in sync on pan (moveend) and zoom (zoomend).
      publishViewport();
      map.on("moveend zoomend", publishViewport);
      ready = true;
    })();
    return () => {
      disposed = true;
      debug.clearMapViewport();
      map?.remove();
    };
  });

  // Push the current zoom + center coordinates into the shell debug store, and
  // persist them so a reload resumes this viewport (see VIEW_PREFS_KEY). Fires on
  // init and on every moveend/zoomend.
  function publishViewport() {
    if (!map) return;
    const c = map.getCenter();
    const viewport = { zoom: map.getZoom(), lat: c.lat, lng: c.lng };
    debug.setMapViewport(viewport);
    savePrefs(VIEW_PREFS_KEY, viewport);
  }

  // Basemap follows the active theme: the theme's tile override when the registry
  // declares one, else the server-configured tile_url (the default theme's
  // basemap). Re-runs when the theme changes while the map is open, swapping the
  // Leaflet tile layer in place with no reload.
  $effect(() => {
    if (!ready || !map || !cfg) return;
    const theme = activeTheme();
    const url = theme.tileUrl ?? cfg.tile_url;
    const attribution = theme.tileAttribution ?? cfg.tile_attribution;
    if (tileLayer) map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(url, { attribution, maxZoom: 18 }).addTo(map);
  });

  // EPB-style status legend (matches the outage-status marker colors).
  function addStatusLegend(m: L.Map) {
    const legend = new L.Control({ position: "bottomright" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "map-legend");
      div.innerHTML =
        "<b>EPB Outage Status</b>" +
        [
          ["Outage Reported", EPB_STATUS_COLORS.OUTAGE_REPORTED],
          ["Crew En Route", EPB_STATUS_COLORS.EN_ROUTE],
          ["Repair in Progress", EPB_STATUS_COLORS.REPAIR_IN_PROGRESS],
          ["Restored", EPB_STATUS_COLORS.RESTORED],
        ]
          .map(
            ([t, c]) =>
              `<div><span class="lg-dot" style="background:${c}"></span>${t}</div>`,
          )
          .join("");
      return div;
    };
    legend.addTo(m);
  }

  // Default glyph size (px). Sources with a markerSize override (EPB) scale their
  // glyph per-feature (customers affected); everything else uses this.
  const GLYPH_SIZE = 24;

  function markerIcon(f: TrackedFeature): L.DivIcon {
    const p = f.properties;
    const cfg = cfgFor(p.source);
    const closed = isClosed(f);
    const color = featureColor(f);
    const size = cfg.markerSize ? cfg.markerSize(p) : GLYPH_SIZE;
    // The marker is the category glyph itself — tinted by featureColor, haloed and
    // (when closed) muted via the .marker-glyph CSS. Centered on the coordinate.
    const svg = iconSvg(iconFor(p.source, p.category), { size, color });
    return L.divIcon({
      className: "",
      html: `<div class="marker-glyph${closed ? " closed" : ""}">${svg}</div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -(size / 2) - 2],
    });
  }

  // Fill/stroke for an area feature: the source's category color (e.g. emergency
  // vs general advisory), muted when the entity is closed/lifted.
  function polyStyle(f: TrackedFeature): L.PathOptions {
    const color = featureColor(f);
    const closed = isClosed(f);
    return {
      color,
      weight: 2,
      opacity: closed ? 0.4 : 0.9,
      fillColor: color,
      fillOpacity: closed ? 0.08 : 0.25,
    };
  }

  function popupHtml(f: TrackedFeature): string {
    const p = f.properties;
    const cfg = cfgFor(p.source);
    return `<strong>${esc(cfg.title(p))}</strong><br>
      <span class="popup-src">${esc(cfg.short)}</span> &middot; ${esc(statusLabelForRaw(p.status))} &middot; ${esc(cfg.jurisdiction(p))}<br>
      ${esc(cfg.location(p))}`;
  }

  // Reconcile Leaflet layers against the derived visible set. Feature objects are
  // replaced (never mutated) on update, so reference equality identifies the layers
  // that actually changed — unaffected ones are left untouched. Points render as
  // clustered markers; polygons render in the separate (non-clustered) polyLayer.
  const renderedMarkers = new Map<
    EntityId,
    { f: TrackedFeature; marker: L.Marker }
  >();
  const renderedPolys = new Map<
    EntityId,
    { f: TrackedFeature; layer: L.GeoJSON }
  >();
  $effect(() => {
    if (!ready || !cluster || !polyLayer) return;
    const shown = new Set<EntityId>();
    for (const f of ts.visibleFeatures) {
      if (!f.geometry) continue;
      shown.add(f.id);
      if (f.geometry.type === "Point") {
        const cur = renderedMarkers.get(f.id);
        if (cur && cur.f === f) continue;
        if (cur) cluster.removeLayer(cur.marker);
        const [lon, lat] = f.geometry.coordinates;
        const marker = L.marker([lat, lon], { icon: markerIcon(f) });
        marker.bindPopup(popupHtml(f));
        marker.on("click", () => (ts.detailId = f.id));
        cluster.addLayer(marker);
        renderedMarkers.set(f.id, { f, marker });
      } else {
        const cur = renderedPolys.get(f.id);
        if (cur && cur.f === f) continue;
        if (cur) polyLayer.removeLayer(cur.layer);
        const layer = L.geoJSON(f as unknown as GeoJSON.Feature, {
          style: () => polyStyle(f),
        });
        layer.bindPopup(popupHtml(f));
        layer.on("click", () => (ts.detailId = f.id));
        polyLayer.addLayer(layer);
        renderedPolys.set(f.id, { f, layer });
      }
    }
    for (const [id, r] of renderedMarkers) {
      if (!shown.has(id)) {
        cluster.removeLayer(r.marker);
        renderedMarkers.delete(id);
      }
    }
    for (const [id, r] of renderedPolys) {
      if (!shown.has(id)) {
        polyLayer.removeLayer(r.layer);
        renderedPolys.delete(id);
      }
    }
  });

  // Draw the open detail entity's track (points + dashed line between them).
  $effect(() => {
    if (!ready || !trackLayer) return;
    const track = ts.detailTrack;
    trackLayer.clearLayers();
    if (!track) return;
    const pts = track
      .filter((t) => t.lat != null && t.lon != null)
      .map((t) => [t.lat!, t.lon!] as [number, number]);
    if (pts.length > 1)
      L.polyline(pts, { color: "#111", weight: 2, dashArray: "4 4" }).addTo(
        trackLayer,
      );
    for (const t of track) {
      if (t.lat != null && t.lon != null) {
        L.circleMarker([t.lat, t.lon], {
          radius: 4,
          color: "#111",
          fillColor: "#fff",
          fillOpacity: 1,
        })
          .bindTooltip(`${statusLabelForRaw(t.status)} @ ${fmt(t.observed_at)}`)
          .addTo(trackLayer);
      }
    }
  });

  // One-shot focus requests from the table: fly to a point entity's coordinates,
  // or fit the map to a polygon entity's affected-area bounds.
  $effect(() => {
    const req = ts.flyToRequest;
    if (!ready || req == null || !map) return;
    const f = ts.features.get(req);
    if (f?.geometry) {
      if (f.geometry.type === "Point") {
        const [lon, lat] = f.geometry.coordinates;
        map.flyTo([lat, lon], 15);
      } else {
        const bounds = L.geoJSON(f as unknown as GeoJSON.Feature).getBounds();
        if (bounds.isValid()) map.fitBounds(bounds, { maxZoom: 15 });
      }
    }
    ts.flyToRequest = null;
  });
</script>

<main id="map" bind:this={mapEl}></main>
