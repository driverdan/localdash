<script lang="ts">
  import { onMount } from "svelte";
  import { loadSources, loadStories, refreshFeeds } from "../api";
  import { news } from "../state.svelte";
  import { debug } from "../../../lib/debug.svelte";
  import CategoryTabs from "./CategoryTabs.svelte";
  import SourcesFooter from "./SourcesFooter.svelte";
  import StoryCard from "./StoryCard.svelte";

  let loaded = $state(false);

  // Ongoing freshness comes from the shell-registered live subscription (see
  // live.ts) — no polling timer; mount only does the initial load.
  onMount(() => {
    Promise.all([loadStories(), loadSources()]).finally(() => (loaded = true));
    // Manual refresh lives in the shell debug panel, not the toolbar. Getters keep
    // disabled/status live so the panel reflects an in-flight refresh.
    debug.registerAction({
      id: "news-refresh",
      label: "Refresh feeds",
      run: refreshFeeds,
      get disabled() {
        return news.refreshing;
      },
      get status() {
        return news.statusText;
      },
    });
    return () => {
      debug.unregisterAction("news-refresh");
    };
  });

  function setHours(e: Event) {
    news.hours = Number((e.currentTarget as HTMLSelectElement).value);
    loadStories();
  }
</script>

<div id="news">
  <div class="toolbar">
    <label>
      Window
      <select value={String(news.hours)} onchange={setHours}>
        <option value="24">24 hours</option>
        <option value="48">2 days</option>
        <option value="72">3 days</option>
        <option value="168">7 days</option>
      </select>
    </label>
    <label class="inline">
      <input type="checkbox" bind:checked={news.multiOnly} /> Multi-source only
    </label>
  </div>

  <CategoryTabs />

  <main>
    {#if news.loadError}
      <div class="notice error">Could not load stories.</div>
    {:else if !loaded}
      <div class="notice">Loading…</div>
    {:else if news.shownStories.length === 0}
      <div class="notice">No stories in this window.</div>
    {:else}
      <h2 class="section-head">{news.shownTabLabel}</h2>
      {#each news.shownStories as story (story.id)}
        <StoryCard {story} />
      {/each}
    {/if}
  </main>

  <SourcesFooter />
</div>
