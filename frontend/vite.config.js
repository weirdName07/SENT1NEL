import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.VITE_API_URL || 'http://127.0.0.1:8000';
const wsTarget = apiTarget.replace(/^http/, 'ws');

export default defineConfig({
    plugins: [react()],
    server: {
        port: 3000,
        proxy: {
            '/api/v1/ws': {
                target: wsTarget,
                ws: true,
                changeOrigin: true,
                rewrite: (path) => path,
                configure: (proxy, _options) => {
                    proxy.on('error', (err, _req, _res) => {
                        if (err.code === 'ECONNRESET' || err.code === 'EPIPE') {
                            // Suppress normal disconnect errors
                            return;
                        }
                        console.error('WS Proxy Error:', err);
                    });
                },
            },
            '/api': {
                target: apiTarget,
                changeOrigin: true,
            },
            '/health': {
                target: apiTarget,
                changeOrigin: true,
            },
            '/ready': {
                target: apiTarget,
                changeOrigin: true,
            },
            '/metrics': {
                target: apiTarget,
                changeOrigin: true,
            },
        },
    },
});
