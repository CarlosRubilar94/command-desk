import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BACKEND = process.env.HERMES_DASHBOARD_URL ?? "http://127.0.0.1:9119";

function hermesDevToken() {
  const TOKEN_RE = /window\.__HERMES_SESSION_TOKEN__\s*=\s*"([^"]+)"/;
  const EMBEDDED_RE =
    /window\.__HERMES_DASHBOARD_EMBEDDED_CHAT__\s*=\s*(true|false)/;

  return {
    name: "hermes:dev-session-token",
    apply: "serve",
    async transformIndexHtml() {
      try {
        const res = await fetch(BACKEND, { headers: { accept: "text/html" } });
        const html = await res.text();
        const match = html.match(TOKEN_RE);
        if (!match) return;
        const embeddedMatch = html.match(EMBEDDED_RE);
        const embeddedJs = embeddedMatch ? embeddedMatch[1] : "true";
        return [
          {
            tag: "script",
            injectTo: "head",
            children:
              `window.__HERMES_SESSION_TOKEN__="${match[1]}";` +
              `window.__HERMES_DASHBOARD_EMBEDDED_CHAT__=${embeddedJs};`,
          },
        ];
      } catch {
        /* dev-only helper */
      }
    },
  };
}

export default defineConfig({
  cacheDir: path.resolve(__dirname, ".vite-cache"),
  plugins: [react(), tailwindcss(), hermesDevToken()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: [
      "react",
      "react-dom",
      "@react-three/fiber",
      "@observablehq/plot",
      "three",
      "leva",
      "gsap",
    ],
  },
  build: {
    outDir: "../hermes_cli/web_dist",
    emptyOutDir: true,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "vendor-react",
              test: /node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/,
              priority: 100,
            },
            {
              name: "vendor-ui",
              test: /node_modules[\\/]@nous-research[\\/]ui[\\/]/,
              priority: 95,
            },
            {
              name: "vendor-icons",
              test: /node_modules[\\/]lucide-react[\\/]/,
              priority: 90,
            },
            {
              name: "vendor-markdown",
              test: /node_modules[\\/](remark-|rehype-|unified|mdast-|hast-|micromark|prismjs)/,
              priority: 80,
            },
            {
              name: "vendor-charts",
              test: /node_modules[\\/](chart\.js|recharts|d3-|@observablehq[\\/]plot)/,
              priority: 70,
            },
            {
              name: "vendor-3d",
              test: /node_modules[\\/](three|@react-three|troika-)/,
              priority: 60,
            },
            {
              name: "vendor-terminal",
              test: /node_modules[\\/]xterm[\\/]/,
              priority: 50,
            },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": { target: BACKEND, ws: true },
      "/dashboard-plugins": BACKEND,
    },
  },
});
