<script lang="ts">
  import { onMount } from "svelte";
  import { loadActive } from "../api";
  import { connectLive } from "../live";
  import DetailPanel from "./DetailPanel.svelte";
  import FilterPanel from "./FilterPanel.svelte";
  import IncidentTable from "./IncidentTable.svelte";
  import MapView from "./MapView.svelte";

  onMount(() => {
    loadActive();
    return connectLive();
  });
</script>

<div id="layout">
  <aside id="sidebar">
    <FilterPanel />
    <IncidentTable />
  </aside>
  <MapView />
</div>
<DetailPanel />
