import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": "http://localhost:8080",
      "/health": "http://localhost:8080",
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined;
          }
          if (
            id.includes("/react/") ||
            id.includes("/react-dom/") ||
            id.includes("scheduler")
          ) {
            return "react-vendor";
          }
          if (id.includes("recharts")) {
            return "charts";
          }
          if (id.includes("lightweight-charts")) {
            return "price-chart";
          }
          if (id.includes("framer-motion")) {
            return "motion";
          }
          if (id.includes("lucide-react")) {
            return "icons";
          }
          return "vendor";
        },
      },
    },
  },
});
