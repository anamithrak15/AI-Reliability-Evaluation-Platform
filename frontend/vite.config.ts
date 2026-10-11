import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const target = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": target,
      "/health": target,
      "/ready": target,
    },
  },
});
