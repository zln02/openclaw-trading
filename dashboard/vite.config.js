import fs from "node:fs";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(() => {
  const certFile = process.env.VITE_SSL_CERT;
  const keyFile = process.env.VITE_SSL_KEY;
  const hasHttpsFiles = certFile && keyFile && fs.existsSync(certFile) && fs.existsSync(keyFile);

  return {
    plugins: [react()],
    server: {
      port: 3000,
      https: hasHttpsFiles
        ? {
            cert: fs.readFileSync(certFile),
            key: fs.readFileSync(keyFile),
          }
        : undefined,
      proxy: {
        "/api": {
          target: `${hasHttpsFiles ? "https" : "http"}://localhost:8080`,
          changeOrigin: true,
          secure: false,
        },
        "/health": {
          target: `${hasHttpsFiles ? "https" : "http"}://localhost:8080`,
          changeOrigin: true,
          secure: false,
        },
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
  };
});
