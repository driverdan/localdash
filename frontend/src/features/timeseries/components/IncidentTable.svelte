<script lang="ts">
  import {
    catLabel,
    cfgFor,
    featureColor,
    isClosed,
    statusLabelForRaw,
  } from "../sources";
  import { ts } from "../state.svelte";
  import type { TrackedFeature } from "../types";

  function openDetail(f: TrackedFeature) {
    ts.detailId = f.id;
    // MapView focuses by id: flies to a point or fits a polygon's bounds.
    if (f.geometry) ts.flyToRequest = f.id;
  }
</script>

<section class="table-wrap">
  <h2>Active ({ts.visibleSorted.length})</h2>
  <table id="incident-table">
    <thead>
      <tr><th>Source</th><th>Category</th><th>Status</th><th>Type</th></tr>
    </thead>
    <!-- One <tbody> per entity groups its header row with an optional full-width
         location sub-line, so hover/click target the whole entity as one unit
         and the location text can wrap across the sidebar instead of a column. -->
    {#each ts.visibleSorted as f (f.id)}
      {@const p = f.properties}
      {@const cfg = cfgFor(p.source)}
      {@const closed = isClosed(f)}
      {@const loc = cfg.location(p)}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
      <tbody class:closed-row={closed} onclick={() => openDetail(f)}>
        <tr class="row-head" class:has-loc={loc}>
          <td>{cfg.short}</td>
          <td>
            {#if closed}<span class="dot cat-closed"></span>{:else}<span
                class="dot"
                style="background:{featureColor(f)}"
              ></span>{/if}
            {catLabel(p.category)}
          </td>
          <td
            >{#if closed}<span class="badge-closed">Closed</span
              >{:else}{statusLabelForRaw(p.status)}{/if}</td
          >
          <td>{cfg.title(p)}</td>
        </tr>
        <!-- Location as a full-width sub-line; omitted when the source has none
             (e.g. epb) so those entities stay a single row. -->
        {#if loc}
          <tr class="row-loc"><td colspan="4">{loc}</td></tr>
        {/if}
      </tbody>
    {/each}
  </table>
</section>
