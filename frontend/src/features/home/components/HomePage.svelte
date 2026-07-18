<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../../lib/router.svelte";
  import SiteFooter from "../../../lib/SiteFooter.svelte";
  import { StoryCard } from "../../news";
  import WeatherStrip from "./WeatherStrip.svelte";
  import OutageDigest from "./OutageDigest.svelte";
  import EventDigest from "./EventDigest.svelte";
  import { loadStories, loadEvents, loadWeather, loadOutages } from "../api";
  import { home } from "../state.svelte";

  // Fire all digest fetches on mount; each resolves into its own widget's
  // state independently (a failure in one leaves the others untouched).
  onMount(() => {
    loadWeather();
    loadOutages();
    loadStories();
    loadEvents();
  });

  function go(event: MouseEvent, to: string) {
    event.preventDefault();
    navigate(to);
  }
</script>

<div class="home-scroll">
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
        <!-- Error shows only with nothing to render: a failed live refetch
           keeps the previous stories on screen instead of blanking them. -->
        {#if home.storiesError && home.stories.length === 0}
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

    <!-- Weather, outages, and events share one grid item so the auto-fit grid
       still sees two columns and future top-level widgets stay pure additions. -->
    <div class="widget-column">
      <WeatherStrip />

      <OutageDigest />

      <article class="widget">
        <div class="widget-head">
          <h2>Current events</h2>
          <a class="view-all" href="/events" onclick={(e) => go(e, "/events")}
            >View all →</a
          >
        </div>
        <!-- Abbreviated home-owned rows (linked title + date/time + distance),
           not the events feature's full card; styled by home.css like the
           weather strip. -->
        <div class="widget-body events-digest">
          {#if home.eventsError && home.events.length === 0}
            <div class="notice error">Could not load events.</div>
          {:else if !home.eventsLoaded}
            <div class="notice">Loading…</div>
          {:else if home.events.length === 0}
            <div class="notice">No current events.</div>
          {:else}
            {#each home.events as item (item.id)}
              <EventDigest {item} />
            {/each}
          {/if}
        </div>
      </article>
    </div>
  </section>

  <SiteFooter />
</div>
