/* ── Constants ─────────────────────────────────────────────── */

// Entity type → RGBA color
export const ENTITY_COLORS = {
    aircraft: [0, 212, 255, 200],
    vessel: [59, 130, 246, 200],
    satellite: [139, 92, 246, 200],
    earthquake: [239, 68, 68, 200],
    weather: [16, 185, 129, 200],
};

// Entity type → emoji icon
export const ENTITY_ICONS = {
    aircraft: '✈',
    vessel: '🚢',
    satellite: '🛰',
    earthquake: '🌍',
    weather: '🌤',
};

// DeckGL Airplane Icon Atlas (stealth / passenger jet style pointing North)
export const AIRPLANE_ICON_ATLAS = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
<svg viewBox="0 0 512 512" width="128" height="128" xmlns="http://www.w3.org/2000/svg">
<path d="M394.22 258.91l-149.52-84v-92a52 52 0 0 0-104 0v92l-149.52 84A24 24 0 0 0 0 279.79v30.59a24 24 0 0 0 35.84 20.84l104.83-59v120.5l-42.5 31.9a24 24 0 0 0-9.6 20.1v23.85a24 24 0 0 0 38.3 19.3L256 464l129.13 93.84a24 24 0 0 0 38.3-19.3v-23.85a24 24 0 0 0-9.6-20.1l-42.5-31.9v-120.5l104.83 59A24 24 0 0 0 512 310.38v-30.59a24 24 0 0 0-11.23-20.88z" fill="#000000"/>
</svg>
`);

export const AIRPLANE_ICON_MAPPING = {
    marker: { x: 0, y: 0, width: 128, height: 128, mask: true }
};

// Initial map view — global, slightly tilted
export const INITIAL_VIEW_STATE = {
    longitude: 20,
    latitude: 25,
    zoom: 2.5,
    pitch: 15,
    bearing: 0,
    transitionDuration: 500,
};

// OpenFreeMap dark style — completely free, no API key
export const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json';

// Severity → UI class
export const SEVERITY_CLASSES = {
    critical: 'severity-critical',
    high: 'severity-high',
    medium: 'severity-medium',
    low: 'severity-low',
};

// API config
export const API_BASE = '/api/v1';
export const WS_ENTITIES_URL = `ws://${window.location.host}/api/v1/ws/entities`;
export const WS_EVENTS_URL = `ws://${window.location.host}/api/v1/ws/events`;
