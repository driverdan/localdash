<script lang="ts">
  import { catLabel, cfgFor, featureColor, isClosed } from "../sources";
  import { ts } from "../state.svelte";
  import type { TrackedFeature } from "../types";

  function openDetail(f: TrackedFeature) {
    ts.detailId = f.id;
    if (f.geometry) {
      const [lon, lat] = f.geometry.coordinates;
      ts.flyToRequest = { lat, lon };
    }
  }
</script>

<section class="table-wrap">
  <h2>Active ({ts.visibleSorted.length})</h2>
  <table id="incident-table">
    <thead>
      <tr><th>Source</th><th>Category</th><th>Status</th><th>Type</th><th>Location</th></tr>
    </thead>
    <tbody>
      {#each ts.visibleSorted as f (f.id)}
        {@const p = f.properties}
        {@const cfg = cfgFor(p.source)}
        {@const closed = isClosed(f)}
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
        <tr class:closed-row={closed} onclick={() => openDetail(f)}>
          <td>{cfg.short}</td>
          <td>
            {#if closed}<span class="dot cat-closed"></span>{:else}<span
                class="dot"
                style="background:{featureColor(f)}"
              ></span>{/if}
            {catLabel(p.category)}
          </td>
          <td>{#if closed}<span class="badge-closed">Closed</span>{:else}{p.status || ""}{/if}</td>
          <td>{cfg.title(p)}</td>
          <td>{cfg.location(p)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</section>
