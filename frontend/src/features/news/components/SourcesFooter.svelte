<script lang="ts">
  import { timeAgo } from "../../../lib/format";
  import { news } from "../state.svelte";
</script>

<footer class="sources">
  <h2>Sources</h2>
  <table>
    <thead>
      <tr><th>Source</th><th>Section</th><th>Articles</th><th>Last fetch</th><th>Status</th></tr>
    </thead>
    <tbody>
      {#each news.sources as s (s.slug + s.category)}
        <tr>
          <td><a href={s.homepage} target="_blank" rel="noopener">{s.name}</a></td>
          <td>{news.categories[s.category] ?? s.category}</td>
          <td>{s.article_count}</td>
          <td>{s.last_fetch ? timeAgo(s.last_fetch) : "—"}</td>
          <td>{s.last_status ?? "pending"}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</footer>
