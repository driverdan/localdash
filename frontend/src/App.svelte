<script lang="ts">
  import { currentPath, navigate } from "./lib/router.svelte";
  import { themes, currentTheme, applyTheme } from "./lib/theme.svelte";
  import DebugPanel from "./lib/DebugPanel.svelte";
  import { TimeseriesDashboard, connectionState } from "./features/timeseries";
  import { NewsFeed } from "./features/news";
  import { EventsPage } from "./features/events";

  // Route table: "/" -> news, "/map" -> timeseries, "/events" -> events.
  const onMap = $derived(currentPath() === "/map");
  const onNews = $derived(currentPath() === "/");
  const onEvents = $derived(currentPath() === "/events");

  // Timeseries-specific connection indicator; shown only on the map route.
  const label = $derived(
    connectionState() === "live"
      ? "live"
      : connectionState() === "connecting"
        ? "connecting…"
        : "disconnected — retrying",
  );
  const klass = $derived(
    connectionState() === "live"
      ? "ok"
      : connectionState() === "connecting"
        ? ""
        : "err",
  );

  function go(event: MouseEvent, to: string) {
    event.preventDefault();
    navigate(to);
  }
</script>

<header>
  <h1>LocalDash</h1>
  <nav>
    <a href="/" class:active={onNews} onclick={(e) => go(e, "/")}>News</a>
    <a href="/map" class:active={onMap} onclick={(e) => go(e, "/map")}>Map</a>
    <a href="/events" class:active={onEvents} onclick={(e) => go(e, "/events")}
      >Events</a
    >
  </nav>
  {#if onMap}
    <span class="status-bar {klass}">{label}</span>
  {/if}
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

{#if onMap}
  <TimeseriesDashboard />
{:else if onNews}
  <NewsFeed />
{:else if onEvents}
  <EventsPage />
{:else}
  <p class="not-found">
    Page not found — <a href="/" onclick={(e) => go(e, "/")}
      >go to the news feed</a
    >.
  </p>
{/if}

<!-- Shell-owned debug overlay: present on every route, outside the route chain. -->
<DebugPanel />
