<script lang="ts">
  import { onMount } from "svelte";
  import L from "leaflet";
  import "leaflet.markercluster";
  import "leaflet/dist/leaflet.css";
  import "leaflet.markercluster/dist/MarkerCluster.css";
  import "leaflet.markercluster/dist/MarkerCluster.Default.css";
  import { fetchConfig, type AppConfig } from "../../../lib/api";
  import { activeTheme } from "../../../lib/theme.svelte";
  import { esc, fmt } from "../../../lib/format";
  import {
    EPB_STATUS_COLORS,
    cfgFor,
    featureColor,
    isClosed,
  } from "../sources";
  import { ts } from "../state.svelte";
  import type { EntityId, TrackedFeature } from "../types";

  const DEFAULT_VIEW = {
    center: [35.0456, -85.3097] as [number, number],
    zoom: 11,
  }; // Chattanooga, TN area

  let mapEl = $state<HTMLElement>();
  let ready = $state(false);
  let cfg = $state<AppConfig>();
  let map: L.Map | undefined;
  let cluster: L.MarkerClusterGroup | undefined;
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
      map = L.map(mapEl!, { maxZoom: 18 }).setView(
        DEFAULT_VIEW.center,
        DEFAULT_VIEW.zoom,
      );
      // Basemap follows the active theme (see the effect below); Leaflet panes
      // keep tiles under the markers regardless of add order.
      // Only group markers that share the same location (coincident points); every
      // distinct incident is shown individually. A 1px radius means nothing clusters
      // unless the points overlap, and identical coordinates can still be spiderfied.
      cluster = L.markerClusterGroup({ maxClusterRadius: 1 });
      map.addLayer(cluster);
      trackLayer = L.layerGroup().addTo(map);
      addStatusLegend(map);
      ready = true;
    })();
    return () => {
      disposed = true;
      map?.remove();
    };
  });

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

  function markerIcon(f: TrackedFeature): L.DivIcon {
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

  function popupHtml(f: TrackedFeature): string {
    const p = f.properties;
    const cfg = cfgFor(p.source);
    return `<strong>${esc(cfg.title(p))}</strong><br>
      <span class="popup-src">${esc(cfg.short)}</span> &middot; ${esc(p.status || "")} &middot; ${esc(cfg.jurisdiction(p))}<br>
      ${esc(cfg.location(p))}`;
  }

  // Reconcile Leaflet markers against the derived visible set. Feature objects
  // are replaced (never mutated) on update, so reference equality identifies the
  // markers that actually changed — unaffected markers are left untouched.
  const rendered = new Map<EntityId, { f: TrackedFeature; marker: L.Marker }>();
  $effect(() => {
    if (!ready || !cluster) return;
    const shown = new Set<EntityId>();
    for (const f of ts.visibleFeatures) {
      if (!f.geometry) continue;
      shown.add(f.id);
      const cur = rendered.get(f.id);
      if (cur && cur.f === f) continue;
      if (cur) cluster.removeLayer(cur.marker);
      const [lon, lat] = f.geometry.coordinates;
      const marker = L.marker([lat, lon], { icon: markerIcon(f) });
      marker.bindPopup(popupHtml(f));
      marker.on("click", () => (ts.detailId = f.id));
      cluster.addLayer(marker);
      rendered.set(f.id, { f, marker });
    }
    for (const [id, r] of rendered) {
      if (!shown.has(id)) {
        cluster.removeLayer(r.marker);
        rendered.delete(id);
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
          .bindTooltip(`${t.status || ""} @ ${fmt(t.observed_at)}`)
          .addTo(trackLayer);
      }
    }
  });

  // One-shot focus requests from the table.
  $effect(() => {
    const req = ts.flyToRequest;
    if (!ready || !req || !map) return;
    map.flyTo([req.lat, req.lon], 15);
    ts.flyToRequest = null;
  });
</script>

<main id="map" bind:this={mapEl}></main>
