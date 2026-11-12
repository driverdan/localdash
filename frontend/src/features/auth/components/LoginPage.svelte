<script lang="ts">
  // The /login form. The shell renders it only for an anonymous visitor; once
  // a login succeeds, reloading the user flips the status to signedIn and the
  // shell's guard sends the user on (admin -> /admin, anyone else -> /).
  import SiteFooter from "../../../lib/SiteFooter.svelte";
  import { login } from "../api";
  import { authState, invalidateUser, loadUser } from "../state.svelte";

  let email = $state("");
  let password = $state("");
  let submitting = $state(false);
  let error = $state<string | null>(null);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    error = null;
    const result = await login(email, password);
    if (result === "ok") {
      password = "";
      invalidateUser();
      await loadUser();
      // The login worked but the user could not be loaded (e.g. the request
      // failed): say so rather than leaving the form looking untouched.
      if (authState().status !== "signedIn")
        error = "Could not sign in. Please try again.";
    } else if (result === "invalid") {
      // One message for every credential problem, as the backend gives no more.
      error = "Incorrect email or password";
    } else {
      error = "Could not sign in. Please try again.";
    }
    submitting = false;
  }
</script>

<div id="login">
  <form class="login-form" onsubmit={submit}>
    <h2>Sign in</h2>
    <label>
      Email
      <input
        type="email"
        name="username"
        autocomplete="username"
        required
        bind:value={email}
      />
    </label>
    <label>
      Password
      <input
        type="password"
        name="password"
        autocomplete="current-password"
        required
        bind:value={password}
      />
    </label>
    {#if error}
      <p class="login-error" role="alert">{error}</p>
    {/if}
    <button type="submit" disabled={submitting}>
      {submitting ? "Signing in…" : "Sign in"}
    </button>
  </form>

  <SiteFooter />
</div>
