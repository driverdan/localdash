<script lang="ts">
  import { timeAgo } from "../../../lib/format";
  import { news } from "../state.svelte";
  import type { Story } from "../types";

  let { story }: { story: Story } = $props();
</script>

<article class="story-card">
  <div class="meta">
    <span class="badge cat"
      >{news.categories[story.category] ?? story.category}</span
    >
    <span class="badge" class:multi={story.source_count > 1}>
      {story.source_count > 1
        ? `${story.source_count} sources`
        : story.sources[0].source}
    </span>
    {timeAgo(story.latest_published)}
  </div>
  {#if story.image_url}
    <a href={story.sources[0].url} target="_blank" rel="noopener" class="image">
      <img src={story.image_url} alt="" loading="lazy" />
    </a>
  {/if}
  <h3>
    <a href={story.sources[0].url} target="_blank" rel="noopener"
      >{story.title}</a
    >
  </h3>
  {#if story.summary}
    <p class="summary">{story.summary}</p>
  {/if}
  <div class="links">
    {#each story.sources as link (link.slug)}
      <a href={link.url} target="_blank" rel="noopener" title={link.title}
        >{link.source} ↗</a
      >
    {/each}
  </div>
</article>
