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
    const timer = setInterval(
      () => {
        loadStories();
        loadSources();
      },
      5 * 60 * 1000,
    );
    return () => clearInterval(timer);
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
    <button onclick={refreshFeeds} disabled={news.refreshing}
      >Refresh feeds</button
    >
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
