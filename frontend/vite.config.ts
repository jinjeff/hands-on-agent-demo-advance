import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Docker 容器内 127.0.0.1 指向容器自身，需用服务名覆盖代理目标
const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        // SSE 不能被代理缓冲，否则思维链 / 逐字要等整段结束才出现
        configure(proxy) {
          proxy.on("proxyRes", (proxyRes, req, res) => {
            if (String(req.url || "").includes("/api/stream")) {
              proxyRes.headers["cache-control"] = "no-cache, no-transform";
              res.setHeader("Cache-Control", "no-cache, no-transform");
              res.setHeader("X-Accel-Buffering", "no");
            }
          });
        },
      },
    },
  },
});
