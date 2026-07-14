<script lang="ts">
  import { loadActive, toggleSource } from "../api";
  import { SOURCES, catLabel } from "../sources";
  import { ts } from "../state.svelte";

  const WINDOWS = [
    { minutes: 30, label: "30 min" },
    { minutes: 60, label: "1 hour" },
    { minutes: 180, label: "3 hours" },
    { minutes: 720, label: "12 hours" },
  ];

  // Drop a dropdown selection whose value no longer exists (e.g. "Closed" after
  // hiding closed incidents) so the displayed value and the filter never diverge.
  $effect(() => {
    if (ts.status && !ts.statusOptions.includes(ts.status)) ts.status = "";
  });
  $effect(() => {
    if (ts.jurisdiction && !ts.jurisdictionOptions.includes(ts.jurisdiction))
      ts.jurisdiction = "";
  });
</script>

<section class="filters">
  <h2>Filters</h2>
  <label
    >Sources
    <div class="checks">
      {#each Object.entries(SOURCES) as [key, s] (key)}
        <label>
          <input
            type="checkbox"
            checked={ts.selectedSources.has(key)}
            onchange={(e) => toggleSource(key, e.currentTarget.checked)}
          />
          {s.name}
        </label>
      {/each}
    </div>
  </label>
  <label
    >Category
    <div class="checks">
      {#each ts.selectedCategoryList as c (c)}
        <label>
          <input
            type="checkbox"
            checked={ts.categories.has(c)}
            onchange={(e) =>
              e.currentTarget.checked
                ? ts.categories.add(c)
                : ts.categories.delete(c)}
          />
          <span class="dot" style="background:{ts.catColor(c)}"
          ></span>{catLabel(c)}
        </label>
      {/each}
    </div>
  </label>
  <label
    >Status
    <select bind:value={ts.status}>
      <option value="">All</option>
      {#each ts.statusOptions as v (v)}<option value={v}>{v}</option>{/each}
    </select>
  </label>
  <label
    >Jurisdiction
    <select bind:value={ts.jurisdiction}>
      <option value="">All</option>
      {#each ts.jurisdictionOptions as v (v)}<option value={v}>{v}</option
        >{/each}
    </select>
  </label>
  <label
    >Search
    <input type="text" placeholder="type, location…" bind:value={ts.search} />
  </label>
  <label class="inline">
    <input
      type="checkbox"
      checked={ts.showClosed}
      onchange={(e) => {
        ts.showClosed = e.currentTarget.checked;
        loadActive(); // refetch: pulls in (or drops) closed incidents server-side
      }}
    />
    Show recently closed
  </label>
  {#if ts.showClosed}
    <label
      >Closed within
      <select bind:value={ts.closedWindow} onchange={() => loadActive()}>
        {#each WINDOWS as w (w.minutes)}<option value={w.minutes}
            >{w.label}</option
          >{/each}
      </select>
    </label>
  {/if}
  <button
    class="reset"
    onclick={() => {
      ts.resetFilters();
      loadActive(); // refetch: previously-hidden sources need loading, closed drop out
    }}
  >
    Reset filters
  </button>
</section>
