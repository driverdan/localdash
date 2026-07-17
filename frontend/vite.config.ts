import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  build: {
    // The FastAPI app mounts ../static at "/" — the build IS the served frontend.
    outDir: "../static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      // ws: true also upgrades /api/v1/ws connections.
      "/api": { target: "http://localhost:8000", ws: true },
    },
  },
});
