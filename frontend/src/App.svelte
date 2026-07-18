<script lang="ts">
  import { currentPath, navigate } from "./lib/router.svelte";
  import { themes, currentTheme, applyTheme } from "./lib/theme.svelte";
  import { startLive, liveState } from "./lib/live.svelte";
  import DebugPanel from "./lib/DebugPanel.svelte";
  import { TimeseriesDashboard } from "./features/timeseries";
  import { HomePage, registerHomeLive } from "./features/home";
  import { NewsFeed, registerNewsLive } from "./features/news";
  import { EventsPage, registerEventsLive } from "./features/events";

  // The one live-update connection plus each feature's permanent subscriptions
  // (timeseries subscribes mount-scoped from its dashboard instead).
  startLive();
  registerNewsLive();
  registerEventsLive();
  registerHomeLive();

  // Route table: "/" -> home, "/news" -> news, "/map" -> timeseries,
  // "/events" -> events.
  const onHome = $derived(currentPath() === "/");
  const onMap = $derived(currentPath() === "/map");
  const onNews = $derived(currentPath() === "/news");
  const onEvents = $derived(currentPath() === "/events");

  // Connection indicator for the shared bus; every route is live now.
  const label = $derived(
    liveState() === "live"
      ? "live"
      : liveState() === "connecting"
        ? "connecting…"
        : "disconnected — retrying",
  );
  const klass = $derived(
    liveState() === "live" ? "ok" : liveState() === "connecting" ? "" : "err",
  );

  function go(event: MouseEvent, to: string) {
    event.preventDefault();
    navigate(to);
  }

  // Configured site name, injected into index.html by the backend before the
  // bundle loads (see app/main.py). Constant for the page's lifetime.
  const siteName = window.__SITE_NAME__;
</script>

<header>
  <h1>{siteName}</h1>
  <nav>
    <a href="/" class:active={onHome} onclick={(e) => go(e, "/")}>Home</a>
    <a href="/news" class:active={onNews} onclick={(e) => go(e, "/news")}
      >News</a
    >
    <a href="/map" class:active={onMap} onclick={(e) => go(e, "/map")}>Map</a>
    <a href="/events" class:active={onEvents} onclick={(e) => go(e, "/events")}
      >Events</a
    >
  </nav>
  <span class="status-bar {klass}">{label}</span>
  <label class="theme-switcher">
    Theme
    <select
      value={currentTheme()}
      onchange={(e) => applyTheme(e.currentTarget.value)}
    >
      {#each themes as theme (theme.id)}
        <option value={theme.id}>{theme.label}</option>
      {/each}
    </select>
  </label>
</header>

{#if onHome}
  <HomePage />
{:else if onMap}
  <TimeseriesDashboard />
{:else if onNews}
  <NewsFeed />
{:else if onEvents}
  <EventsPage />
{:else}
  <p class="not-found">
    Page not found — <a href="/" onclick={(e) => go(e, "/")}
      >go to the home page</a
    >.
  </p>
{/if}

<!-- Shell-owned debug overlay: present on every route, outside the route chain. -->
<DebugPanel />
