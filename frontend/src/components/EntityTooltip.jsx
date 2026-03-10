import { Html } from '@react-three/drei';

export function EntityTooltip({ entity, position }) {
    if (!entity || !position) return null;

    const pos = entity.position || {};
    const vel = entity.velocity || {};
    const meta = entity.metadata || {};

    const rows = [
        ['Type', entity.entity_type],
        ['ID', entity.source_id?.slice(0, 16)],
        pos.latitude != null && ['Lat', pos.latitude.toFixed(4)],
        pos.longitude != null && ['Lon', pos.longitude.toFixed(4)],
        vel.speed_mps != null && ['Speed', `${vel.speed_mps.toFixed(1)} m/s`],
        vel.heading_deg != null && ['Hdg', `${vel.heading_deg.toFixed(0)}°`],
        pos.altitude_m != null && ['Alt', `${(pos.altitude_m / 1000).toFixed(1)} km`],
        meta.callsign && ['Flight', meta.callsign],
        meta.airline && ['Airline', meta.airline],
        meta.origin && meta.destination && ['Route', `${meta.origin} → ${meta.destination}`],
        meta.name && ['Name', meta.name],
        meta.magnitude != null && ['Mag', `M${meta.magnitude}`],
        entity.lifecycle && ['Status', entity.lifecycle],
    ].filter(Boolean);

    const title = meta.callsign || meta.name || entity.source_id?.slice(0, 12) || '—';

    return (
        <Html
            position={position}
            style={{ pointerEvents: 'none' }}
            distanceFactor={2.5}
            occlude={false}
            zIndexRange={[50, 0]}
        >
            <div className="globe-tooltip">
                <div className="globe-tooltip-title">{title}</div>
                {rows.map(([k, v]) => (
                    <div key={k} className="globe-tooltip-row">
                        <span className="globe-tooltip-key">{k}</span>
                        <span className="globe-tooltip-val">{v ?? '—'}</span>
                    </div>
                ))}
            </div>
        </Html>
    );
}
