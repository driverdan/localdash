// Public surface of the news feature. The app shell imports only this module;
// everything else in this namespace is feature-internal.
export { default as NewsFeed } from "./components/NewsFeed.svelte";
// Shared with the home feature so it can render story digests without reaching
// into news internals (see openspec add-home-landing-page).
export { default as StoryCard } from "./components/StoryCard.svelte";
export type { Story } from "./types";
export { setCategoryLabels } from "./state.svelte";
export { registerLive as registerNewsLive } from "./live";
