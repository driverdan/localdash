// Minimal path router for the shell. Two routes don't justify a dependency:
// a reactive current path, History-API navigation, and a popstate listener.
// The route table itself lives in App.svelte.

let path = $state(window.location.pathname);

export function currentPath(): string {
  return path;
}

export function navigate(to: string): void {
  if (to === path) return;
  history.pushState(null, "", to);
  path = to;
}

window.addEventListener("popstate", () => {
  path = window.location.pathname;
});
