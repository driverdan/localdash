<script lang="ts">
  import { onMount } from "svelte";
  import { loadSources, loadStories, refreshFeeds } from "../api";
  import { news } from "../state.svelte";
  import CategoryTabs from "./CategoryTabs.svelte";
  import SourcesFooter from "./SourcesFooter.svelte";
  import StoryCard from "./StoryCard.svelte";

  let loaded = $state(false);

  onMount(() => {
    Promise.all([loadStories(), loadSources()]).finally(() => (loaded = true));
    const timer = setInterval(() => {
      loadStories();
      loadSources();
    }, 5 * 60 * 1000);
    return () => clearInterval(timer);
  });

  function setHours(e: Event) {
    news.hours = Number((e.currentTarget as HTMLSelectElement).value);
    loadStories();
  }
</script>

<div class="news-page">
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
    <button onclick={refreshFeeds} disabled={news.refreshing}>Refresh feeds</button>
    <span class="status">{news.statusText}</span>
  </div>

  <CategoryTabs />

  <main>
    {#if news.loadError}
      <div class="notice error">Could not load stories.</div>
    {:else if !loaded}
      <div class="notice">Loading…</div>
    {:else if news.shownStories.length === 0}
      <div class="notice">No stories in this window.</div>
    {:else if news.shownTab === "all"}
      {#each news.groupedShown as [slug, label, group] (slug)}
        <h2 class="section-head">{label}</h2>
        {#each group as story (story.id)}
          <StoryCard {story} />
        {/each}
      {/each}
    {:else}
      {#each news.shownStories as story (story.id)}
        <StoryCard {story} />
      {/each}
    {/if}
  </main>

  <SourcesFooter />
</div>

<style>
  /* The header is 44px; the page owns its own scroll like the map owns #layout. */
  .news-page {
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
  .toolbar label.inline { display: flex; align-items: center; gap: 5px; }
  .toolbar select,
  .toolbar button {
    font: inherit;
    color: #1b1f24;
    background: #fff;
    border: 1px solid #cfd6df;
    border-radius: 6px;
    padding: 5px 9px;
    cursor: pointer;
  }
  .toolbar button:hover:enabled { border-color: #0071ce; }
  .toolbar button:disabled { opacity: 0.6; cursor: default; }
  .toolbar .status { color: #5a6573; font-size: 12px; }
  main { max-width: 46rem; margin: 0 auto; padding: 4px 16px 24px; }
  .section-head {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #0071ce;
    border-bottom: 1px solid #dde2e8;
    padding-bottom: 4px;
    margin: 26px 0 2px;
  }
  .notice { text-align: center; color: #5a6573; padding: 48px 0; }
  .notice.error { color: #b4552d; }
</style>
