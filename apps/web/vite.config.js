import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(function (_a) {
    var _b, _c;
    var mode = _a.mode;
    var env = loadEnv(mode, process.cwd(), "");
    var apiProxyTarget = (_c = (_b = env.VITE_API_PROXY_TARGET) !== null && _b !== void 0 ? _b : process.env.VITE_API_PROXY_TARGET) !== null && _c !== void 0 ? _c : "http://localhost:8000";
    return {
        plugins: [react()],
        server: {
            proxy: {
                "/api": {
                    target: apiProxyTarget,
                    changeOrigin: true,
                },
            },
        },
    };
});
