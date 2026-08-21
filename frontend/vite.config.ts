import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/agent_hub/static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/admin": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/agents": "http://localhost:8000",
      "/conversations": {
        target: "http://localhost:8000",
        ws: true,
      },
      "/health": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    exclude: ["e2e/**", "node_modules/**"],
    setupFiles: "./src/test/setup.ts",
  },
});
