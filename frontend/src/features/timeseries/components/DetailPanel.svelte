<script lang="ts">
  import { fmt } from "../../../lib/format";
  import { fetchEntity, fetchTrack } from "../api";
  import { cfgFor } from "../sources";
  import { ts } from "../state.svelte";
  import type { DetailRow, EntityDetail, TrackPoint } from "../types";

  let detail = $state<EntityDetail | null>(null);
  let track = $state<TrackPoint[] | null>(null);

  $effect(() => {
    const id = ts.detailId;
    detail = null;
    track = null;
    ts.detailTrack = null;
    if (id == null) return;
    // Snapshot and history are separate resources; fetch them concurrently.
    Promise.all([fetchEntity(id), fetchTrack(id)]).then(([d, t]) => {
      if (ts.detailId !== id) return; // a different entity was opened meanwhile
      detail = d;
      track = t;
      ts.detailTrack = t;
    });
  });

  const rows = $derived.by((): DetailRow[] => {
    if (!detail) return [];
    const cfg = cfgFor(detail.source);
    const p = detail.latest_properties || {};
    const all: DetailRow[] = [["Source", cfg.name], ...cfg.detail(p, detail)];
    return all.filter(([, v]) => v != null && v !== "");
  });

  const title = $derived(
    detail ? detail.label || cfgFor(detail.source).title(detail.latest_properties || {}) : "",
  );
</script>

{#if ts.detailId != null}
  <div class="detail">
    <button class="close" onclick={() => (ts.detailId = null)}>&times;</button>
    {#if !detail || !track}
      <div>Loading…</div>
    {:else}
      <h3>{title}</h3>
      {#each rows as [k, v] (k)}
        <div class="kv"><b>{k}</b>{String(v)}</div>
      {/each}
      <h2>History ({track.length})</h2>
      <ul class="track">
        {#each [...track].reverse() as t, i (i)}
          <li><span class="t">{fmt(t.observed_at)}</span> — {t.status || ""}</li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}
