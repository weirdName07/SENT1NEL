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
} from './constants';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function App() {
    const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
    const [activeTab, setActiveTab] = useState('events');
    const [selectedTypes, setSelectedTypes] = useState(new Set([
        'aircraft', 'vessel', 'satellite', 'earthquake', 'weather'
    ]));
    const [hoveredEntity, setHoveredEntity] = useState(null);

    const { entities, counts } = useEntities(selectedTypes);
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

    const layers = useMemo(() => {
        const filtered = entities.filter(e => selectedTypes.has(e.entity_type));

        return [
            // Main entity scatterplot
            new ScatterplotLayer({
                id: 'entities',
                data: filtered,
                getPosition: d => [d.position?.longitude ?? d.lon ?? 0, d.position?.latitude ?? d.lat ?? 0],
                getRadius: d => {
                    if (d.entity_type === 'earthquake') return Math.max(3000, (d.metadata?.magnitude ?? 3) * 8000);
                    if (d.entity_type === 'satellite') return 6000;
                    return 3000;
                },
                getFillColor: d => ENTITY_COLORS[d.entity_type] ?? [100, 100, 100],
                getLineColor: d => ENTITY_COLORS[d.entity_type] ?? [100, 100, 100],
                lineWidthMinPixels: 1,
                stroked: true,
                filled: true,
                opacity: 0.7,
                radiusMinPixels: 3,
                radiusMaxPixels: 15,
                pickable: true,
                autoHighlight: true,
                highlightColor: [255, 255, 255, 80],
                onHover: info => setHoveredEntity(info.object ?? null),
                transitions: {
                    getPosition: 500,
                    getRadius: 300,
                },
            }),

            // Earthquake heatmap for clusters
            new HeatmapLayer({
                id: 'earthquake-heat',
                data: filtered.filter(e => e.entity_type === 'earthquake'),
                getPosition: d => [d.position?.longitude ?? d.lon ?? 0, d.position?.latitude ?? d.lat ?? 0],
                getWeight: d => d.metadata?.magnitude ?? 3,
                radiusPixels: 60,
                intensity: 1.5,
                threshold: 0.1,
                colorRange: [
                    [255, 255, 178], [254, 204, 92], [253, 141, 60],
                    [240, 59, 32], [189, 0, 38],
                ],
                visible: selectedTypes.has('earthquake'),
            }),
        ];
    }, [entities, selectedTypes]);

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
        if (meta.callsign) rows.push(['Callsign', meta.callsign]);
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
