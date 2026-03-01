import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Map } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, IconLayer, TextLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import MapOverlays from './components/MapOverlays';
import { useEntities } from './hooks/useEntities';
import { useEvents } from './hooks/useEvents';
import { useHealth } from './hooks/useHealth';
import {
    ENTITY_COLORS,
    ENTITY_ICONS,
    INITIAL_VIEW_STATE,
    MAP_STYLE,
    AIRPLANE_ICON_ATLAS,
    AIRPLANE_ICON_MAPPING
} from './constants';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function App() {
    const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
    const [activeTab, setActiveTab] = useState('events');
    const [selectedTypes, setSelectedTypes] = useState(new Set([
        'aircraft', 'vessel', 'satellite', 'earthquake', 'weather'
    ]));
    const [hoveredEntity, setHoveredEntity] = useState(null);

    const { entities, counts } = useEntities(selectedTypes, viewState.longitude, viewState.latitude);
    const { events } = useEvents();
    const health = useHealth();

    const toggleType = useCallback((type) => {
        setSelectedTypes(prev => {
            const next = new Set(prev);
            if (next.has(type)) next.delete(type);
            else next.add(type);
            return next;
        });
    }, []);

    // ── Deck.gl Layers ──────────────────────────────────────

    const zoomBucket = Math.floor(viewState.zoom);

    const layers = useMemo(() => {
        const activeEntities = entities.filter(e => selectedTypes.has(e.entity_type));

        let aircraft = activeEntities.filter(e => e.entity_type === 'aircraft');
        const weather = activeEntities.filter(e => e.entity_type === 'weather');

        // LOD Filtering to prevent React/WebGL thread crashing globally
        if (zoomBucket < 4) {
            aircraft = aircraft.slice(0, 1500);
        } else if (zoomBucket < 6) {
            aircraft = aircraft.slice(0, 5000);
        } else if (zoomBucket < 8) {
            aircraft = aircraft.slice(0, 20000);
        }

        return [
            // Cyberpunk Airplane IconLayer
            new IconLayer({
                id: 'aircraft-icons',
                data: aircraft,
                pickable: true,
                iconAtlas: AIRPLANE_ICON_ATLAS,
                iconMapping: AIRPLANE_ICON_MAPPING,
                getIcon: d => 'marker',
                sizeScale: 1,
                getPosition: d => [d.position?.longitude ?? d.lon ?? 0, d.position?.latitude ?? d.lat ?? 0],
                getSize: d => (zoomBucket > 5 ? 24 : 16),
                getColor: d => [0, 212, 255, 255],
                getAngle: d => (d.velocity?.heading_deg ?? d.heading ?? 0),
                autoHighlight: true,
                highlightColor: [255, 255, 255, 200],
                onHover: info => setHoveredEntity(info.object ?? null),
                transitions: {
                    getPosition: { duration: 2000, type: 'interpolation' },
                    getAngle: { duration: 2000, type: 'interpolation' }
                }
            }),

            // Weather Scatterplot
            new ScatterplotLayer({
                id: 'weather-dots',
                data: weather,
                getPosition: d => [d.position?.longitude ?? d.lon ?? 0, d.position?.latitude ?? d.lat ?? 0],
                getRadius: 15000,
                getFillColor: d => {
                    const intensity = d.metadata?.precipitation_mm || 0;
                    return intensity > 0 ? [59, 130, 246, 180] : [16, 185, 129, 80]; // Blue if raining, green otherwise
                },
                pickable: true,
                radiusMinPixels: 4,
                radiusMaxPixels: 60,
                onHover: info => setHoveredEntity(info.object ?? null),
                transitions: {
                    getPosition: { duration: 5000, type: 'interpolation' }
                },
                visible: selectedTypes.has('weather')
            }),
        ];
    }, [entities, selectedTypes, zoomBucket]);

    // ── Tooltip ─────────────────────────────────────────────

    const getTooltip = useCallback(({ object }) => {
        if (!object) return null;
        const pos = object.position || {};
        const vel = object.velocity || {};
        const meta = object.metadata || {};

        const rows = [
            ['Type', object.entity_type],
            ['Source ID', object.source_id],
            ['Lat', (pos.latitude ?? object.lat)?.toFixed(4)],
            ['Lon', (pos.longitude ?? object.lon)?.toFixed(4)],
        ];

        if (vel.speed_mps != null) rows.push(['Speed', `${vel.speed_mps.toFixed(1)} m/s`]);
        if (vel.heading_deg != null) rows.push(['Heading', `${vel.heading_deg.toFixed(0)}°`]);
        if (pos.altitude_m != null) rows.push(['Alt', `${(pos.altitude_m / 1000).toFixed(1)} km`]);
        if (meta.callsign) rows.push(['Flight', meta.callsign]);
        if (meta.airline) rows.push(['Airline', meta.airline]);
        if (meta.origin && meta.destination) rows.push(['Route', `${meta.origin} → ${meta.destination}`]);
        if (meta.name) rows.push(['Name', meta.name]);
        if (meta.magnitude != null) rows.push(['Magnitude', meta.magnitude]);
        if (object.lifecycle) rows.push(['Status', object.lifecycle]);

        return {
            html: `
        <div class="map-tooltip">
          <div class="tooltip-title">${meta.callsign || meta.name || object.source_id}</div>
          ${rows.map(([k, v]) => `
            <div class="tooltip-row">
              <span>${k}</span>
              <span class="tooltip-value">${v ?? '—'}</span>
            </div>
          `).join('')}
        </div>
      `,
            style: { background: 'none', border: 'none', padding: 0 },
        };
    }, []);

    return (
        <div className="app">
            <Header counts={counts} health={health} />

            <div className="map-container" style={{ marginTop: 'var(--header-height)' }}>
                <DeckGL
                    viewState={viewState}
                    onViewStateChange={({ viewState }) => setViewState(viewState)}
                    controller={true}
                    layers={layers}
                    getTooltip={getTooltip}
                >
                    <Map mapStyle={MAP_STYLE} />
                </DeckGL>

                <MapOverlays counts={counts} entities={entities} />
            </div>

            <Sidebar
                activeTab={activeTab}
                onTabChange={setActiveTab}
                entities={entities}
                events={events}
                selectedTypes={selectedTypes}
                onToggleType={toggleType}
            />
        </div>
    );
}
