import { fetchMe, postLogout, type User } from "./api";

export type AuthStatus = "unknown" | "anonymous" | "signedIn";

// The browser's view of who is signed in. Starts "unknown" and is resolved
// lazily by loadUser(), which the shell calls only on /login and /admin, so the
// public pages never request /api/v1/auth/me.
class AuthState {
  status = $state<AuthStatus>("unknown");
  user = $state<User | null>(null);
}

const auth = new AuthState();

// Whether the status reflects the server (set by a completed /me request) and
// the request in flight, if any. Login and a failed log-out mark the status
// stale so the next loadUser() asks again.
let fresh = false;
let inFlight: Promise<void> | null = null;

function setUser(user: User | null): void {
  auth.user = user;
  auth.status = user ? "signedIn" : "anonymous";
}

export function authState(): AuthState {
  return auth;
}

/** Resolve the signed-in user with one /me request; a no-op once resolved. */
export function loadUser(): Promise<void> {
  if (inFlight) return inFlight;
  if (fresh) return Promise.resolve();
  inFlight = (async () => {
    try {
      setUser(await fetchMe());
    } catch {
      // Unreachable or erroring API: treat as signed out, so the visitor gets
      // the login form rather than a page stuck on "Loading…".
      setUser(null);
    } finally {
      fresh = true;
      inFlight = null;
    }
  })();
  return inFlight;
}

/** After a successful login: the cookie changed, so the next loadUser() refetches. */
export function invalidateUser(): void {
  fresh = false;
}

/** End the session and become anonymous. */
export async function logout(): Promise<void> {
  try {
    await postLogout();
  } catch {
    // The session may still be live; have the next loadUser() check again
    // rather than trusting the local "anonymous".
    fresh = false;
  }
  setUser(null);
}
