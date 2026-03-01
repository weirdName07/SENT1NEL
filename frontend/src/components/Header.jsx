import { ENTITY_ICONS } from '../constants';

export default function Header({ counts, health }) {
    const statusClass = health.status === 'healthy' ? 'healthy'
        : health.status === 'down' ? 'down' : 'degraded';

    const uptime = health.uptime_s > 3600
        ? `${(health.uptime_s / 3600).toFixed(1)}h`
        : health.uptime_s > 60
            ? `${Math.floor(health.uptime_s / 60)}m`
            : `${Math.floor(health.uptime_s)}s`;

    return (
        <header className="header">
            <div className="header-brand">
                <span className="logo">SENTINEL</span>
                <span className="subtitle">World Awareness Engine</span>
            </div>

            <div className="header-stats">
                {Object.entries(ENTITY_ICONS).map(([type, icon]) => (
                    <div key={type} className="stat-item">
                        <span className={`stat-dot ${type}`} />
                        <span className="stat-value">{counts[type] ?? 0}</span>
                        <span className="stat-label">{type}</span>
                    </div>
                ))}
            </div>

            <div className="header-status">
                <div className={`status-badge ${statusClass}`}>
                    <span className="status-indicator" />
                    {health.status === 'healthy' ? 'LIVE' : health.status === 'down' ? 'OFFLINE' : 'DEGRADED'}
                </div>
                <span style={{ fontSize: 10, color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                    ↑ {uptime}
                </span>
            </div>
        </header>
    );
}
