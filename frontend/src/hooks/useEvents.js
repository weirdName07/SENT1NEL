import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_EVENTS_URL, API_BASE } from '../constants';

/**
 * Hook to receive real-time events via WebSocket + REST fallback.
 */
export function useEvents(maxEvents = 100) {
    const [events, setEvents] = useState([]);
    const wsRef = useRef(null);
    const reconnectTimer = useRef(null);

    const connectWs = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(WS_EVENTS_URL);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setEvents(prev => [data, ...prev].slice(0, maxEvents));
            } catch { /* ignore parse errors */ }
        };

        ws.onclose = () => {
            reconnectTimer.current = setTimeout(connectWs, 3000);
        };

        ws.onerror = () => ws.close();
    }, [maxEvents]);

    // Fetch recent events on mount
    const fetchRecent = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/events?limit=50`);
            if (res.ok) {
                const data = await res.json();
                if (data.events) {
                    setEvents(data.events);
                }
            }
        } catch { /* API not available yet */ }
    }, []);

    useEffect(() => {
        connectWs();
        fetchRecent();

        return () => {
            clearTimeout(reconnectTimer.current);
            wsRef.current?.close();
        };
    }, [connectWs, fetchRecent]);

    return { events };
}
