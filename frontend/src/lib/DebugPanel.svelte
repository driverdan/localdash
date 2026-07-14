<script lang="ts">
  // Shell-owned debug overlay: the always-present π toggle button and the
  // route-aware modal. Feature-agnostic (imports only lib/), mounted once in
  // App.svelte so it rides above every route. Styling lives in base.css /
  // theme-dark.css per the styling contract (no scoped styles here).
  import { currentPath } from "./router.svelte";
  import { debug } from "./debug.svelte";

  const onMap = $derived(currentPath() === "/map");
</script>

<button
  class="debug-toggle"
  aria-label="Toggle debug panel"
  aria-expanded={debug.open}
  onclick={() => debug.toggle()}>π</button
>

{#if debug.open}
  <aside class="debug-modal" aria-label="Debug panel">
    <button
      class="debug-close"
      aria-label="Close debug panel"
      onclick={() => (debug.open = false)}>×</button
    >
    <h3>Debug</h3>
    {#if onMap}
      <section class="debug-section">
        <h4>Map</h4>
        <dl class="debug-kv">
          <dt>Zoom</dt>
          <dd>{debug.map ? debug.map.zoom : "—"}</dd>
          <dt>Center</dt>
          <dd>
            {debug.map
              ? `${debug.map.lat.toFixed(5)}, ${debug.map.lng.toFixed(5)}`
              : "—"}
          </dd>
        </dl>
      </section>
    {/if}
    {#if debug.actions.length > 0}
      <section class="debug-section">
        <h4>Actions</h4>
        {#each debug.actions as action (action.id)}
          <div class="debug-action">
            <button onclick={action.run} disabled={action.disabled}
              >{action.label}</button
            >
            {#if action.status}
              <span class="debug-action-status">{action.status}</span>
            {/if}
          </div>
        {/each}
      </section>
    {/if}
    {#if !onMap && debug.actions.length === 0}
      <p class="debug-empty">No debug data for this view.</p>
    {/if}
  </aside>
{/if}
