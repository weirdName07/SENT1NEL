/* ── Constants ─────────────────────────────────────────────── */

// Entity type → RGBA color (used by deck.gl and UI chips)
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

// Severity → UI class
export const SEVERITY_CLASSES = {
    critical: 'severity-critical',
    high: 'severity-high',
    medium: 'severity-medium',
    low: 'severity-low',
};

// Globe constants
export const EARTH_RADIUS = 1.0;

export const GLOBE_CAMERA_INITIAL = {
    position: [0, 0, 2.8],
    fov: 45,
};

// Earth texture paths (served from /public/textures/)
export const EARTH_TEXTURES = {
    day: '/textures/earth_day.jpg',
    normal: '/textures/earth_normal.jpg',
    specular: '/textures/earth_specular.jpg',
};

// API config
export const API_BASE = '/api/v1';
const _wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
export const WS_ENTITIES_URL = `${_wsProto}//${window.location.host}/api/v1/ws/entities`;
export const WS_EVENTS_URL = `${_wsProto}//${window.location.host}/api/v1/ws/events`;
