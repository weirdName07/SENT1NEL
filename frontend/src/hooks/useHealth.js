import { useState, useEffect, useCallback } from 'react';

/**
 * Hook to poll /health and /ready endpoints.
 */
export function useHealth(intervalMs = 10000) {
    const [health, setHealth] = useState({
        status: 'unknown',
        timescaledb: false,
        redis: false,
        nats: false,
        uptime_s: 0,
    });

    const poll = useCallback(async () => {
        try {
            const [healthRes, readyRes] = await Promise.all([
                fetch('/health').catch(() => null),
                fetch('/ready').catch(() => null),
            ]);

            const healthData = healthRes?.ok ? await healthRes.json() : {};
            const readyData = readyRes?.ok ? await readyRes.json() : {};

            setHealth({
                status: healthData.status ?? 'down',
                uptime_s: healthData.uptime_s ?? 0,
                timescaledb: readyData.timescaledb ?? false,
                redis: readyData.redis ?? false,
                nats: readyData.nats ?? false,
            });
        } catch {
            setHealth(prev => ({ ...prev, status: 'down' }));
        }
    }, []);

    useEffect(() => {
        poll();
        const id = setInterval(poll, intervalMs);
        return () => clearInterval(id);
    }, [poll, intervalMs]);

    return health;
}
