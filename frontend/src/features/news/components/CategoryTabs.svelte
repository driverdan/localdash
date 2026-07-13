<script lang="ts">
  import { news } from "../state.svelte";
</script>

<nav class="tabs">
  {#each news.tabs as [slug, label] (slug)}
    <button class:active={slug === news.shownTab} onclick={() => (news.activeTab = slug)}>
      {label}
    </button>
  {/each}
</nav>

<style>
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    padding: 0 16px 6px;
  }
  .tabs button {
    font: inherit;
    font-size: 13px;
    background: #fff;
    color: #1b1f24;
    border: 1px solid #cfd6df;
    border-radius: 999px;
    padding: 4px 14px;
    cursor: pointer;
  }
  .tabs button:hover { border-color: #0071ce; }
  .tabs button.active {
    background: #0071ce;
    border-color: #0071ce;
    color: #fff;
  }
</style>
