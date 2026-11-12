// Public surface of the admin feature (will match /api/v1/admin). The shell
// imports only this module. Admin reaches the signed-in user and log-out only
// through the auth feature's index.ts.
export { default as AdminPage } from "./components/AdminPage.svelte";
