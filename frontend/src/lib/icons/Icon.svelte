<script lang="ts">
  // Template-facing wrapper over `iconSvg` — the same registry, the same output,
  // rendered inline via {@html}. Use this in Svelte markup; use `iconSvg` where you
  // need a raw string (e.g. building marker HTML imperatively).
  import { iconSvg, type IconName, type IconOptions } from "./iconSvg";

  interface Props extends IconOptions {
    name: IconName;
  }
  let { name, size, color, strokeWidth, class: cls }: Props = $props();
</script>

{@html iconSvg(name, { size, color, strokeWidth, class: cls })}
