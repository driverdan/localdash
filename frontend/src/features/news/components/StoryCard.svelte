<script lang="ts">
  import { timeAgo } from "../../../lib/format";
  import { news } from "../state.svelte";
  import type { Story } from "../types";

  let { story }: { story: Story } = $props();
</script>

<article class="story">
  <div class="meta">
    <span class="badge cat">{news.categories[story.category] ?? story.category}</span>
    <span class="badge" class:multi={story.source_count > 1}>
      {story.source_count > 1 ? `${story.source_count} sources` : story.sources[0].source}
    </span>
    {timeAgo(story.latest_published)}
  </div>
  <h3><a href={story.sources[0].url} target="_blank" rel="noopener">{story.title}</a></h3>
  {#if story.summary}
    <p class="summary">{story.summary}</p>
  {/if}
  <div class="links">
    {#each story.sources as link (link.slug)}
      <a href={link.url} target="_blank" rel="noopener" title={link.title}>{link.source} ↗</a>
    {/each}
  </div>
</article>

<style>
  .story {
    background: #fff;
    border: 1px solid #dde2e8;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 12px 0;
  }
  .story h3 { margin: 0 0 5px; font-size: 17px; line-height: 1.3; }
  .story h3 a { color: inherit; text-decoration: none; }
  .story h3 a:hover { color: #0071ce; }
  .meta { font-size: 11px; color: #5a6573; margin-bottom: 7px; }
  .badge {
    display: inline-block;
    font-weight: 600;
    border-radius: 999px;
    padding: 1px 8px;
    margin-right: 6px;
    background: #e8f0fa;
    color: #0071ce;
  }
  .badge.multi { background: #dcebe3; color: #2d6a4f; }
  .badge.cat {
    background: transparent;
    border: 1px solid #cfd6df;
    color: #5a6573;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 10px;
  }
  .summary { margin: 0 0 9px; font-size: 13px; line-height: 1.5; }
  .links { display: flex; flex-wrap: wrap; gap: 6px; font-size: 12px; }
  .links a {
    text-decoration: none;
    color: #1b1f24;
    background: #f7f9fb;
    border: 1px solid #cfd6df;
    border-radius: 999px;
    padding: 2px 10px;
  }
  .links a:hover { border-color: #0071ce; color: #0071ce; }
</style>
