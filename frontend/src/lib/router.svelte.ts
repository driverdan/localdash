// Minimal path router for the shell. A handful of routes don't justify a
// dependency: a reactive current path, History-API navigation, and a popstate
// listener. The route table itself lives in App.svelte.

let path = $state(window.location.pathname);

export function currentPath(): string {
  return path;
}

export function navigate(to: string): void {
  if (to === path) return;
  history.pushState(null, "", to);
  path = to;
}

// Replace the current history entry instead of adding one: for guard redirects
// (e.g. /admin -> /login), so Back skips the page that redirected rather than
// landing on it and bouncing forward again.
export function redirect(to: string): void {
  if (to === path) return;
  history.replaceState(null, "", to);
  path = to;
}

window.addEventListener("popstate", () => {
  path = window.location.pathname;
});
