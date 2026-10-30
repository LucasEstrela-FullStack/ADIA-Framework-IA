import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api vai para a API local de scripts/dev-backend.ps1.
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
