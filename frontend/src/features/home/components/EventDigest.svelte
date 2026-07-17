<script lang="ts">
  import { fmtEventDate } from "../../../lib/format";
  import type { EventItem } from "../../events";

  let { item }: { item: EventItem } = $props();

  const when = $derived(fmtEventDate(item.starts_at, item.ends_at));
  // Same primary-link choice as the events page's full card.
  const url = $derived(item.links[0]?.source_url);
</script>

<article class="event-digest">
  <h3>
    {#if url}
      <a href={url} target="_blank" rel="noopener">{item.title}</a>
    {:else}
      {item.title}
    {/if}
  </h3>
  <p class="when">
    <!-- Explicit {" "}: Svelte trims the whitespace at the {#if} block edge. -->
    {when}{#if item.distance_miles !== null}{" "}· {item.distance_miles} mi{/if}
  </p>
</article>
