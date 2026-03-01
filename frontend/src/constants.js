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
