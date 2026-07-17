<script lang="ts">
  import { onMount } from "svelte";
  import { loadItems, loadTags, refreshSources } from "../api";
  import { events } from "../state.svelte";
  import { debug } from "../../../lib/debug.svelte";
  import EventCard from "./EventCard.svelte";

  let loaded = $state(false);
  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  // Ongoing freshness comes from the shell-registered live subscription (see
  // live.ts) — no polling timer; mount only does the initial load.
  onMount(() => {
    Promise.all([loadItems(), loadTags()]).finally(() => (loaded = true));
    // Manual refresh lives in the shell debug panel, not the toolbar. Getters keep
    // disabled/status live so the panel reflects an in-flight refresh.
    debug.registerAction({
      id: "events-refresh",
      label: "Refresh sources",
      run: refreshSources,
      get disabled() {
        return events.refreshing;
      },
      get status() {
        return events.statusText;
      },
    });
    return () => {
      clearTimeout(searchTimer);
      debug.unregisterAction("events-refresh");
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

<div id="events">
  <div class="toolbar">
    <input
      type="search"
      placeholder="Search events…"
      value={events.search}
      oninput={setSearch}
    />
    <label>
      Distance
      <select
        value={events.maxMiles === null ? "" : String(events.maxMiles)}
        onchange={setMaxMiles}
      >
        <option value="">Any</option>
        <option value="5">≤ 5 mi</option>
        <option value="15">≤ 15 mi</option>
        <option value="30">≤ 30 mi</option>
        <option value="50">≤ 50 mi</option>
      </select>
    </label>
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
