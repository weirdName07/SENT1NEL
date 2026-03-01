import { ENTITY_ICONS } from '../constants';

export default function EntityList({ entities, selectedTypes }) {
    const filtered = entities
        .filter(e => selectedTypes.has(e.entity_type))
        .slice(0, 200);

    if (filtered.length === 0) {
        return (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                No entities tracked
            </div>
        );
    }

    return (
        <div>
            {filtered.map((entity, idx) => {
                const pos = entity.position || {};
                const vel = entity.velocity || {};
                const meta = entity.metadata || {};
                const name = meta.callsign || meta.name || entity.source_id;

                const speed = vel.speed_mps != null
                    ? vel.speed_mps > 100
                        ? `${(vel.speed_mps * 3.6).toFixed(0)} km/h`
                        : `${vel.speed_mps.toFixed(1)} m/s`
                    : '';

                return (
                    <div key={entity.entity_id ?? entity.source_id ?? idx} className="entity-card">
                        <div className={`entity-type-icon ${entity.entity_type}`}>
                            {ENTITY_ICONS[entity.entity_type] ?? '?'}
                        </div>
                        <div className="entity-info">
                            <div className="entity-name">{name}</div>
                            <div className="entity-detail">
                                {(pos.latitude ?? entity.lat)?.toFixed(3)}°, {(pos.longitude ?? entity.lon)?.toFixed(3)}°
                                {pos.altitude_m != null && ` · ${(pos.altitude_m / 1000).toFixed(1)}km`}
                            </div>
                        </div>
                        {speed && <div className="entity-speed">{speed}</div>}
                    </div>
                );
            })}
        </div>
    );
}
