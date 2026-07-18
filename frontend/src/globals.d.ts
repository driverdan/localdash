// The backend injects the configured site name as a synchronous global in
// index.html (see app/main.py `_index_html`), read by the shell header before
// the bundle mounts. Declared here so svelte-check sees it under strict mode.
declare global {
  interface Window {
    __SITE_NAME__: string;
  }
}

export {};
