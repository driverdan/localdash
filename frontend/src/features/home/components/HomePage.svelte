<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../../lib/router.svelte";
  import { StoryCard } from "../../news";
  import { EventCard } from "../../events";
  import { loadStories, loadEvents } from "../api";
  import { home } from "../state.svelte";

  // Fire both digest fetches on mount; each resolves into its own widget's
  // state independently (a failure in one leaves the other untouched).
  onMount(() => {
    loadStories();
    loadEvents();
  });

  function go(event: MouseEvent, to: string) {
    event.preventDefault();
    navigate(to);
  }
</script>

<section class="home-grid">
  <article class="widget">
    <div class="widget-head">
      <h2>Latest news</h2>
      <a class="view-all" href="/news" onclick={(e) => go(e, "/news")}
        >View all →</a
      >
    </div>
    <!-- Reuse the news scope so StoryCard's feature-scoped styling applies
         verbatim; home.css neutralizes the page-frame rules on this wrapper. -->
    <div id="news" class="widget-body">
      {#if home.storiesError}
        <div class="notice error">Could not load news.</div>
      {:else if !home.storiesLoaded}
        <div class="notice">Loading…</div>
      {:else if home.stories.length === 0}
        <div class="notice">No recent stories.</div>
      {:else}
        {#each home.stories as story (story.id)}
          <StoryCard {story} />
        {/each}
      {/if}
    </div>
  </article>

  <article class="widget">
    <div class="widget-head">
      <h2>Upcoming events</h2>
      <a class="view-all" href="/events" onclick={(e) => go(e, "/events")}
        >View all →</a
      >
    </div>
    <div id="events" class="widget-body">
      {#if home.eventsError}
        <div class="notice error">Could not load events.</div>
      {:else if !home.eventsLoaded}
        <div class="notice">Loading…</div>
      {:else if home.events.length === 0}
        <div class="notice">No upcoming events.</div>
      {:else}
        {#each home.events as item (item.id)}
          <EventCard {item} />
        {/each}
      {/if}
    </div>
  </article>
</section>
