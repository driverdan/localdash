<script lang="ts">
  import { news } from "../state.svelte";
</script>

<nav class="tabs">
  {#each news.tabs as [slug, label] (slug)}
    <button
      class:active={slug === news.shownTab}
      onclick={() => (news.activeTab = slug)}
    >
      {label}
    </button>
  {/each}
</nav>
