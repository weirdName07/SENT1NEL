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
            },
            '/api': apiTarget,
            '/health': apiTarget,
            '/ready': apiTarget,
            '/metrics': apiTarget,
        },
    },
});
