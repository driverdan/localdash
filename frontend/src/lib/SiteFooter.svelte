<script lang="ts">
  // Site-wide footer, rendered as the last child of each content route's scroll
  // region (home, news, events — never the viewport-locked map) so it flows
  // after the content instead of pinning to the viewport. The link opens a new
  // tab so the SPA and its live WebSocket keep running. Styled by .site-footer
  // in base.css. The lang="ts" block keeps the component typed under strict
  // svelte-check even though it holds no logic.
</script>

<footer class="site-footer">
  <a
    href="https://github.com/driverdan/localdash"
    target="_blank"
    rel="noopener">100% Open Source</a
  >
</footer>
