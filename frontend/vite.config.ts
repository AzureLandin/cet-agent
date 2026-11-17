import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND_TARGET = "http://localhost:5001";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": { target: BACKEND_TARGET, changeOrigin: true },
      "/profile": { target: BACKEND_TARGET, changeOrigin: true },
      "/sessions": { target: BACKEND_TARGET, changeOrigin: true },
      "/questions": { target: BACKEND_TARGET, changeOrigin: true },
      "/admin": { target: BACKEND_TARGET, changeOrigin: true },
      "/health": { target: BACKEND_TARGET, changeOrigin: true },
      "/uploads": { target: BACKEND_TARGET, changeOrigin: true },
    },
  },
});
