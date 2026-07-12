<script lang="ts">
  import { fmt } from "../../../lib/format";
  import type { EventItem } from "../types";

  let { item }: { item: EventItem } = $props();

  const when = $derived(
    fmt(item.starts_at) + (item.ends_at ? ` – ${new Date(item.ends_at).toLocaleTimeString()}` : ""),
  );
  const where = $derived(
    [item.venue_name, item.venue_name === item.address ? null : item.address]
      .filter(Boolean)
      .join(" · "),
  );
</script>

<article class="event">
  <div class="meta">
    {#each item.tags as tag (tag)}
      <span class="badge cat">{tag}</span>
    {/each}
    {when}
    {#if item.distance_miles !== null}
      <span class="distance">{item.distance_miles} mi</span>
    {/if}
  </div>
  <h3><a href={item.links[0]?.source_url} target="_blank" rel="noopener">{item.title}</a></h3>
  {#if where}
    <p class="where">{where}</p>
  {/if}
  {#if item.description}
    <p class="summary">{item.description}</p>
  {/if}
  <div class="links">
    {#each item.links as link (link.source_name)}
      <a href={link.source_url} target="_blank" rel="noopener">{link.source_name} ↗</a>
    {/each}
  </div>
</article>

<style>
  .event {
    background: #fff;
    border: 1px solid #dde2e8;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 12px 0;
  }
  .event h3 { margin: 0 0 5px; font-size: 17px; line-height: 1.3; }
  .event h3 a { color: inherit; text-decoration: none; }
  .event h3 a:hover { color: #0071ce; }
  .meta { font-size: 11px; color: #5a6573; margin-bottom: 7px; }
  .badge.cat {
    display: inline-block;
    font-weight: 600;
    border-radius: 999px;
    padding: 1px 8px;
    margin-right: 6px;
    background: transparent;
    border: 1px solid #cfd6df;
    color: #5a6573;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 10px;
  }
  .distance { margin-left: 6px; font-weight: 600; color: #2d6a4f; }
  .where { margin: 0 0 6px; font-size: 12px; color: #44505f; font-weight: 600; }
  .summary {
    margin: 0 0 9px;
    font-size: 13px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
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
