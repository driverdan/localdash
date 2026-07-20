<script lang="ts">
  // Site-wide footer, rendered as the last child of each route's scroll region
  // — the content region on home, news, and events; the sidebar (after the
  // incident table) on the map, whose map pane is viewport-locked but whose
  // sidebar scrolls like any other content. It flows wherever that content ends
  // and gets no per-route positioning, so it is reached by scrolling rather than
  // pinned to the viewport. The link opens a new tab so the SPA and its live
  // WebSocket keep running. Styled by .site-footer in base.css. The lang="ts"
  // block keeps the component typed under strict svelte-check even though it
  // holds no logic.
</script>

<footer class="site-footer">
  <a
    href="https://github.com/driverdan/localdash"
    target="_blank"
    rel="noopener">100% Open Source</a
  >
</footer>
