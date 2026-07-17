// Public surface of the events feature. The app shell imports only this module;
// everything else in this namespace is feature-internal.
export { default as EventsPage } from "./components/EventsPage.svelte";
// The home feature's events digest renders its own abbreviated rows; it needs
// only the item type from here (see openspec abbreviate-home-events).
export type { EventItem } from "./types";
export { registerLive as registerEventsLive } from "./live";
