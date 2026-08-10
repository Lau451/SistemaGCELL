import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
      // `server-only`'s default export condition throws unconditionally —
      // it only resolves to a safe no-op via the "react-server" package
      // export condition, which Vitest's plain Node resolution does not
      // apply. Alias straight to that no-op so page.tsx modules (which
      // transitively import `server-only` through `lib/supabase/server.ts`)
      // can be statically imported in tests without a full RSC runtime.
      // Scoped to this one package only — does not touch React's own
      // module resolution, so client-component RTL rendering is unaffected.
      "server-only": path.resolve(
        import.meta.dirname,
        "./node_modules/server-only/empty.js",
      ),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
});
