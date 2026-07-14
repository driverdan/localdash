<script lang="ts">
  import { loadActive, toggleCategory, toggleSource } from "../api";
  import { SOURCES, catKey, catLabel, colorFor } from "../sources";
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
  <div class="source-tree">
    <span class="tree-heading">Sources &amp; categories</span>
    {#each Object.entries(SOURCES) as [key, s] (key)}
      {@const cats = s.categories}
      {@const onCount = cats.filter((c) =>
        ts.categories.has(catKey(key, c)),
      ).length}
      <div class="source-group">
        <label class="source-row">
          <input
            type="checkbox"
            checked={onCount === cats.length}
            indeterminate={onCount > 0 && onCount < cats.length}
            onchange={(e) => toggleSource(key, e.currentTarget.checked)}
          />
          {s.name}
        </label>
        <div class="cat-children">
          {#each cats as c (c)}
            <label>
              <input
                type="checkbox"
                checked={ts.categories.has(catKey(key, c))}
                onchange={(e) =>
                  toggleCategory(key, c, e.currentTarget.checked)}
              />
              <span class="dot" style="background:{colorFor(key, c)}"
              ></span>{catLabel(c)}
            </label>
          {/each}
        </div>
      </div>
    {/each}
  </div>
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
