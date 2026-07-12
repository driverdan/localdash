<script lang="ts">
  import { onMount } from "svelte";
  import { loadItems, loadTags, refreshSources } from "../api";
  import { events } from "../state.svelte";
  import EventCard from "./EventCard.svelte";

  let loaded = $state(false);
  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  onMount(() => {
    Promise.all([loadItems(), loadTags()]).finally(() => (loaded = true));
    const timer = setInterval(() => {
      loadItems();
      loadTags();
    }, 5 * 60 * 1000);
    return () => {
      clearInterval(timer);
      clearTimeout(searchTimer);
    };
  });

  function toggleTopic(name: string) {
    events.toggleTopic(name);
    loadItems();
  }

  function setMaxMiles(e: Event) {
    const v = (e.currentTarget as HTMLSelectElement).value;
    events.maxMiles = v ? Number(v) : null;
    loadItems();
  }

  function setSearch(e: Event) {
    events.search = (e.currentTarget as HTMLInputElement).value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadItems, 300);
  }
</script>

<div class="events-page">
  <div class="toolbar">
    <input
      type="search"
      placeholder="Search events…"
      value={events.search}
      oninput={setSearch}
    />
    <label>
      Distance
      <select value={events.maxMiles === null ? "" : String(events.maxMiles)} onchange={setMaxMiles}>
        <option value="">Any</option>
        <option value="5">≤ 5 mi</option>
        <option value="15">≤ 15 mi</option>
        <option value="30">≤ 30 mi</option>
        <option value="50">≤ 50 mi</option>
      </select>
    </label>
    <button onclick={refreshSources} disabled={events.refreshing}>Refresh sources</button>
    <span class="status">{events.statusText}</span>
  </div>

  {#if events.tags.length > 0}
    <div class="chips">
      {#each events.tags as tag (tag)}
        <button
          class="chip"
          class:active={events.topics.includes(tag)}
          onclick={() => toggleTopic(tag)}
        >
          {tag}
        </button>
      {/each}
    </div>
  {/if}

  <main>
    {#if events.loadError}
      <div class="notice error">Could not load events.</div>
    {:else if !loaded}
      <div class="notice">Loading…</div>
    {:else if events.items.length === 0}
      <div class="notice">
        No upcoming events match.
        {#if events.topics.length === 0 && !events.search && events.maxMiles === null}
          Event sources may not be configured yet.
        {/if}
      </div>
    {:else}
      {#each events.items as item (item.id)}
        <EventCard {item} />
      {/each}
    {/if}
  </main>
</div>

<style>
  /* The header is 44px; the page owns its own scroll like the news page. */
  .events-page {
    height: calc(100vh - 44px);
    overflow-y: auto;
    background: #f7f9fb;
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    justify-content: center;
    padding: 12px 16px 8px;
    font-size: 13px;
  }
  .toolbar label { font-weight: 600; color: #44505f; }
  .toolbar input[type="search"],
  .toolbar select,
  .toolbar button {
    font: inherit;
    color: #1b1f24;
    background: #fff;
    border: 1px solid #cfd6df;
    border-radius: 6px;
    padding: 5px 9px;
  }
  .toolbar input[type="search"] { width: 220px; }
  .toolbar select,
  .toolbar button { cursor: pointer; }
  .toolbar button:hover:enabled { border-color: #0071ce; }
  .toolbar button:disabled { opacity: 0.6; cursor: default; }
  .toolbar .status { color: #5a6573; font-size: 12px; }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    padding: 0 16px 4px;
  }
  .chip {
    font: inherit;
    font-size: 12px;
    color: #44505f;
    background: #fff;
    border: 1px solid #cfd6df;
    border-radius: 999px;
    padding: 3px 12px;
    cursor: pointer;
  }
  .chip:hover { border-color: #0071ce; }
  .chip.active {
    background: #0071ce;
    border-color: #0071ce;
    color: #fff;
    font-weight: 600;
  }
  main { max-width: 46rem; margin: 0 auto; padding: 4px 16px 24px; }
  .notice { text-align: center; color: #5a6573; padding: 48px 0; }
  .notice.error { color: #b4552d; }
</style>
