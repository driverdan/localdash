// Public surface of the events feature. The app shell imports only this module;
// everything else in this namespace is feature-internal.
export { default as EventsPage } from "./components/EventsPage.svelte";
// Shared with the home feature so it can render an events digest without
// reaching into events internals (see openspec add-home-landing-page).
export { default as EventCard } from "./components/EventCard.svelte";
export type { EventItem } from "./types";
