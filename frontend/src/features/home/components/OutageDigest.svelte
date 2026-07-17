<script lang="ts">
  import { navigate } from "../../../lib/router.svelte";
  import { home } from "../state.svelte";

  // service key -> row noun ("3 power outages" / "1 fiber outage"). Iteration
  // order is display order: power first.
  const LABELS = { energy: "power", fiber: "fiber" } as const;

  // One row per service with active outages; all-zero means the reassuring
  // "no current outages" state, not an empty card.
  const rows = $derived(
    home.outages === null
      ? []
      : (Object.keys(LABELS) as (keyof typeof LABELS)[])
          .map((service) => ({
            service,
            label: LABELS[service],
            ...home.outages![service],
          }))
          .filter((row) => row.count > 0),
  );

  function go(event: MouseEvent) {
    event.preventDefault();
    navigate("/map");
  }
</script>

<article class="widget">
  <div class="widget-head">
    <h2>Outages</h2>
    <a class="view-all" href="/map" onclick={go}>View all →</a>
  </div>
  <div class="widget-body outages-digest">
    {#if !home.outagesLoaded}
      <div class="notice">Loading…</div>
      <!-- Error shows only with no summary to render: a failed live refetch
         keeps the previous counts on screen instead of blanking them. -->
    {:else if home.outages === null}
      <div class="notice error">Could not load outages.</div>
    {:else if rows.length === 0}
      <div class="notice">No current outages.</div>
    {:else}
      {#each rows as row (row.service)}
        <div class="outage-row">
          <span class="outage-count">
            {row.count}
            {row.label} outage{row.count === 1 ? "" : "s"}
          </span>
          {#if row.customers > 0}
            <span class="outage-customers">
              · {row.customers.toLocaleString()} customers
            </span>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</article>
