import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_ENTITIES_URL, API_BASE } from '../constants';

/**
 * Hook to fetch and maintain live entity state via WebSocket + REST fallback.
 */
export function useEntities(selectedTypes) {
    const [entities, setEntities] = useState([]);
    const [counts, setCounts] = useState({
        aircraft: 0, vessel: 0, satellite: 0, earthquake: 0, weather: 0, total: 0,
    });
    const wsRef = useRef(null);
    const reconnectTimer = useRef(null);

    const connectWs = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(WS_ENTITIES_URL + '?interval_ms=2000');
        wsRef.current = ws;

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'entities' && Array.isArray(msg.data)) {
                    setEntities(msg.data);

                    // Count by type
                    const c = { aircraft: 0, vessel: 0, satellite: 0, earthquake: 0, weather: 0, total: 0 };
                    msg.data.forEach(e => {
                        const t = e.entity_type;
                        if (c[t] !== undefined) c[t]++;
                        c.total++;
                    });
                    setCounts(c);
                }
            } catch { /* ignore parse errors */ }
        };

        ws.onclose = () => {
            reconnectTimer.current = setTimeout(connectWs, 3000);
        };

        ws.onerror = () => ws.close();
    }, []);

    // Fallback: poll REST if WS unavailable
    const pollRest = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/entities/live?radius_km=20000&count=500`);
            if (res.ok) {
                const data = await res.json();
                if (data.entities) {
                    setEntities(data.entities);
                    const c = { aircraft: 0, vessel: 0, satellite: 0, earthquake: 0, weather: 0, total: 0 };
                    data.entities.forEach(e => {
                        const t = e.entity_type;
                        if (c[t] !== undefined) c[t]++;
                        c.total++;
                    });
                    setCounts(c);
                }
            }
        } catch { /* API not available yet */ }
    }, []);

    useEffect(() => {
        connectWs();

        // Fallback polling every 5s if WS fails
        const fallback = setInterval(() => {
            if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
                pollRest();
            }
        }, 5000);

        // Initial REST fetch
        pollRest();

        return () => {
            clearInterval(fallback);
            clearTimeout(reconnectTimer.current);
            wsRef.current?.close();
        };
    }, [connectWs, pollRest]);

    return { entities, counts };
}
