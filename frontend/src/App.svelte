<script lang="ts">
  import { TimeseriesDashboard, connectionState } from "./features/timeseries";

  const label = $derived(
    connectionState() === "live"
      ? "live"
      : connectionState() === "connecting"
        ? "connecting…"
        : "disconnected — retrying",
  );
  const klass = $derived(
    connectionState() === "live" ? "ok" : connectionState() === "connecting" ? "" : "err",
  );
</script>

<header>
  <h1>LocalDash</h1>
  <span class="status-bar {klass}">{label}</span>
</header>

<TimeseriesDashboard />
