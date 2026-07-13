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

<article class="event-card">
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
    <!-- An event merged from duplicate listings carries several links from
         one source, so the source name alone is not a unique key. -->
    {#each item.links as link (`${link.source_name}|${link.source_url}`)}
      <a href={link.source_url} target="_blank" rel="noopener">{link.source_name} ↗</a>
    {/each}
  </div>
</article>
