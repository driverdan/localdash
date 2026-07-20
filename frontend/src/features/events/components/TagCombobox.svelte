<script lang="ts">
  // Type-to-filter topic picker. Purely presentational: it owns only local UI
  // state (query text, open flag, active suggestion) and drives selection back
  // through `onToggle`. Only tags drawn from `candidates` can ever be
  // committed — free-typed text is never turned into a topic.
  let {
    candidates,
    selected,
    onToggle,
  }: {
    candidates: string[];
    selected: string[];
    onToggle: (tag: string) => void;
  } = $props();

  let query = $state("");
  let open = $state(false);
  let activeIndex = $state(0);
  let root: HTMLDivElement | undefined;
  let input: HTMLInputElement | undefined;

  const uid = $props.id();
  const listId = `${uid}-list`;
  const optionId = (i: number) => `${uid}-opt-${i}`;

  // Candidates minus what's already picked, then case-insensitive substring
  // match; empty query lists everything still available.
  const suggestions = $derived.by(() => {
    const chosen = new Set(selected);
    const q = query.trim().toLowerCase();
    return candidates.filter(
      (t) => !chosen.has(t) && (q === "" || t.toLowerCase().includes(q)),
    );
  });

  // Clamp the highlighted row to the current list so it never dangles past the
  // end when suggestions shrink (typing, or a selection removing a row).
  const active = $derived(
    Math.min(activeIndex, Math.max(0, suggestions.length - 1)),
  );

  function commit(tag: string) {
    onToggle(tag);
    query = "";
    activeIndex = 0;
    open = true;
    input?.focus();
  }

  function move(delta: number) {
    open = true;
    const n = suggestions.length;
    if (n === 0) return;
    activeIndex = Math.max(0, Math.min(n - 1, active + delta));
  }

  function handleKeydown(e: KeyboardEvent) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        move(1);
        break;
      case "ArrowUp":
        e.preventDefault();
        move(-1);
        break;
      case "Enter":
        if (open && suggestions.length > 0) {
          e.preventDefault();
          commit(suggestions[active]);
        }
        break;
      case "Escape":
        open = false;
        break;
      case "Backspace":
        // Empty box: peel off the most recently added pill.
        if (query === "" && selected.length > 0) {
          onToggle(selected[selected.length - 1]);
        }
        break;
    }
  }

  function handleFocusOut(e: FocusEvent) {
    // Close only when focus actually leaves the whole widget (not when moving
    // between the input and a pill/suggestion inside it).
    if (root && !root.contains(e.relatedTarget as Node | null)) open = false;
  }
</script>

<div class="tag-filter" bind:this={root} onfocusout={handleFocusOut}>
  <div class="tag-control">
    {#each selected as tag (tag)}
      <span class="tag-pill">
        {tag}
        <button
          type="button"
          class="tag-pill-remove"
          aria-label={`Remove ${tag}`}
          onclick={() => onToggle(tag)}
        >
          ×
        </button>
      </span>
    {/each}
    <input
      bind:this={input}
      bind:value={query}
      type="text"
      class="tag-input"
      placeholder="Filter by tag…"
      role="combobox"
      aria-expanded={open}
      aria-controls={listId}
      aria-autocomplete="list"
      aria-activedescendant={open && suggestions.length > 0
        ? optionId(active)
        : undefined}
      onfocus={() => (open = true)}
      oninput={() => {
        open = true;
        activeIndex = 0;
      }}
      onkeydown={handleKeydown}
    />
  </div>
  {#if open && suggestions.length > 0}
    <ul class="tag-suggestions" id={listId} role="listbox">
      {#each suggestions as tag, i (tag)}
        <li
          id={optionId(i)}
          role="option"
          aria-selected={i === active}
          class:active={i === active}
          onmousedown={(e) => {
            // Fire before the input's blur so the dropdown doesn't close first.
            e.preventDefault();
            commit(tag);
          }}
          onmouseenter={() => (activeIndex = i)}
        >
          {tag}
        </li>
      {/each}
    </ul>
  {/if}
</div>
