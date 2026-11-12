// Public surface of the auth feature (matches /api/v1/auth). The shell and the
// admin feature import only this module; everything else here is internal.
export { default as LoginPage } from "./components/LoginPage.svelte";
export { authState, loadUser, logout } from "./state.svelte";
export type { AuthStatus } from "./state.svelte";
export type { User } from "./api";
