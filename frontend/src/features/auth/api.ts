// The /api/v1/auth endpoints. The session token lives in an HttpOnly cookie the
// browser sets and sends on its own (same origin); no code here ever sees it.

export interface User {
  id: string;
  email: string;
  is_superuser: boolean;
}

/** "ok" on 204, "invalid" on 401 (any credential problem), "error" otherwise. */
export type LoginResult = "ok" | "invalid" | "error";

export async function login(
  email: string,
  password: string,
): Promise<LoginResult> {
  try {
    // A URLSearchParams body is sent as application/x-www-form-urlencoded,
    // which is what the backend's OAuth2PasswordRequestForm reads.
    const r = await fetch("/api/v1/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    });
    if (r.status === 204) return "ok";
    if (r.status === 401) return "invalid";
    return "error";
  } catch {
    return "error";
  }
}

/** The signed-in user, or null when the request carries no valid session. */
export async function fetchMe(): Promise<User | null> {
  const r = await fetch("/api/v1/auth/me");
  if (r.status === 401) return null;
  if (!r.ok) throw new Error(`GET /api/v1/auth/me -> ${r.status}`);
  return r.json() as Promise<User>;
}

export async function postLogout(): Promise<void> {
  const r = await fetch("/api/v1/auth/logout", { method: "POST" });
  if (!r.ok) throw new Error(`POST /api/v1/auth/logout -> ${r.status}`);
}
