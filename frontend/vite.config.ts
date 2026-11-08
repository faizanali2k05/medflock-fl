import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "../src/medflock/resources/web", emptyOutDir: true },
  server: {
    proxy: {
      "/graphql": "http://127.0.0.1:8088",
      "/api": "http://127.0.0.1:8088",
    },
  },
});
