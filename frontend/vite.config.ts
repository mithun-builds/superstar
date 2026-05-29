import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api and /admin to Django on :8000 so the frontend
// can call the backend without CORS friction.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/admin": "http://localhost:8000",
      "/static": "http://localhost:8000",
    },
  },
});
