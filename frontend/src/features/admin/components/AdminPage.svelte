<script lang="ts">
  // The /admin dashboard. The shell renders it only for a signed-in admin (see
  // App.svelte's guard); it has no content yet beyond who is signed in.
  import SiteFooter from "../../../lib/SiteFooter.svelte";
  import { redirect } from "../../../lib/router.svelte";
  import { authState, logout } from "../../auth";

  const auth = authState();
  let loggingOut = $state(false);

  async function signOut() {
    loggingOut = true;
    await logout();
    loggingOut = false;
    redirect("/login");
  }
</script>

<div id="admin">
  <section class="admin-dashboard">
    <h2>Admin</h2>
    <p class="admin-user">Signed in as <strong>{auth.user?.email}</strong></p>
    <button type="button" class="logout" onclick={signOut} disabled={loggingOut}
      >Log out</button
    >
  </section>

  <SiteFooter />
</div>
