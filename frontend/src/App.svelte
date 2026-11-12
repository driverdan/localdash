<script lang="ts">
  import { untrack } from "svelte";
  import { currentPath, navigate, redirect } from "./lib/router.svelte";
  import { themes, currentTheme, applyTheme } from "./lib/theme.svelte";
  import { startLive, liveState } from "./lib/live.svelte";
  import DebugPanel from "./lib/DebugPanel.svelte";
  import { TimeseriesDashboard } from "./features/timeseries";
  import { HomePage, registerHomeLive } from "./features/home";
  import { NewsFeed, registerNewsLive } from "./features/news";
  import { EventsPage, registerEventsLive } from "./features/events";
  import { LoginPage, authState, loadUser, logout } from "./features/auth";
  import { AdminPage } from "./features/admin";

  // The one live-update connection plus each feature's permanent subscriptions
  // (timeseries subscribes mount-scoped from its dashboard instead).
  startLive();
  registerNewsLive();
  registerEventsLive();
  registerHomeLive();

  // Route table: "/" -> home, "/news" -> news, "/map" -> timeseries,
  // "/events" -> events, "/login" -> auth's login page, "/admin" -> admin's
  // dashboard (admins only). The last two are not in the nav.
  const onHome = $derived(currentPath() === "/");
  const onMap = $derived(currentPath() === "/map");
  const onNews = $derived(currentPath() === "/news");
  const onEvents = $derived(currentPath() === "/events");
  const onLogin = $derived(currentPath() === "/login");
  const onAdmin = $derived(currentPath() === "/admin");

  // Route guard for /login and /admin, by signed-in state:
  //   route    unknown    anonymous         admin              signed-in non-admin
  //   /admin   Loading…   -> /login         dashboard          no-access + log out
  //   /login   Loading…   login form        -> /admin          -> /
  // Redirects replace the history entry so Back never bounces. This is a
  // convenience, not a security boundary: the API's require_admin is.
  const auth = authState();

  // Only these two routes ever ask who is signed in; public pages never call
  // /api/v1/auth/me. untrack: re-run on route changes, not on auth changes.
  $effect(() => {
    if (onLogin || onAdmin) untrack(() => loadUser());
  });

  $effect(() => {
    if (onAdmin && auth.status === "anonymous") redirect("/login");
    else if (onLogin && auth.status === "signedIn")
      redirect(auth.user?.is_superuser ? "/admin" : "/");
  });

  let loggingOut = $state(false);
  async function signOut() {
    loggingOut = true;
    await logout();
    loggingOut = false;
    redirect("/login");
  }

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
{:else if onLogin}
  {#if auth.status === "anonymous"}
    <LoginPage />
  {:else}
    <!-- unknown, or signed in and about to be redirected -->
    <p class="route-notice">Loading…</p>
  {/if}
{:else if onAdmin}
  {#if auth.status === "signedIn" && auth.user?.is_superuser}
    <AdminPage />
  {:else if auth.status === "signedIn"}
    <div class="route-notice no-access">
      <p>You do not have access to this page.</p>
      <button type="button" onclick={signOut} disabled={loggingOut}
        >Log out</button
      >
    </div>
  {:else}
    <!-- unknown, or anonymous and about to be redirected -->
    <p class="route-notice">Loading…</p>
  {/if}
{:else}
  <p class="not-found">
    Page not found — <a href="/" onclick={(e) => go(e, "/")}
      >go to the home page</a
    >.
  </p>
{/if}

<!-- Shell-owned debug overlay: present on every route, outside the route chain. -->
<DebugPanel />
