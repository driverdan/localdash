<script lang="ts">
  // Shell-owned debug overlay: the always-present π toggle button and the
  // route-aware modal. Feature-agnostic (imports only lib/), mounted once in
  // App.svelte so it rides above every route. Styling lives in base.css /
  // theme-dark.css per the styling contract (no scoped styles here).
  import { currentPath } from "./router.svelte";
  import { debug } from "./debug.svelte";

  const onMap = $derived(currentPath() === "/map");

  // Values are shown as stored, not as the owning feature reads them:
  // `persistPrefs` skips its first save, so in-memory state and storage
  // routinely disagree, and storage is the side worth debugging. Objects
  // pretty-print; a bare string (`localdash.theme`) or unparseable content shows
  // raw, so a corrupt value stays visible and deletable instead of breaking the
  // panel.
  function formatValue(raw: string): string {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (parsed !== null && typeof parsed === "object") {
        return JSON.stringify(parsed, null, 2);
      }
    } catch {
      /* not JSON — show it as stored */
    }
    return raw;
  }
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
    <!-- Scoped to the route-specific content above, not the modal as a whole:
         the Settings section below always renders, so the modal is never bare. -->
    {#if !onMap && debug.actions.length === 0}
      <p class="debug-empty">No debug data for this view.</p>
    {/if}
    <!-- Always present, unlike the route-gated sections above: preferences are
         global browser state, so a key stays inspectable from any route. -->
    <section class="debug-section">
      <h4>Settings</h4>
      {#if debug.settings.length === 0}
        <p class="debug-empty">No settings saved.</p>
      {:else}
        {#each debug.settings as entry (entry.key)}
          {@const deleted = debug.deletedSettings.has(entry.key)}
          <div class="debug-setting">
            <div class="debug-setting-head">
              <code class="debug-setting-key">{entry.key}</code>
              <button
                class="debug-setting-delete"
                disabled={deleted}
                onclick={() => debug.deleteSetting(entry.key)}>Delete</button
              >
            </div>
            <pre class="debug-setting-value">{formatValue(entry.raw)}</pre>
            {#if deleted}
              <p class="debug-setting-notice">Deleted — reload to apply.</p>
            {/if}
          </div>
        {/each}
      {/if}
    </section>
  </aside>
{/if}
