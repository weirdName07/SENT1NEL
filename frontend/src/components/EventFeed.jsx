import { useMemo } from 'react';

const SEVERITY_BADGE = {
    critical: { label: 'ALERT', cls: 'badge-critical' },
    high: { label: 'ALERT', cls: 'badge-high' },
    medium: { label: 'INTEL', cls: 'badge-medium' },
    low: { label: 'INFO', cls: 'badge-low' },
};

function timeAgo(ts) {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

export default function EventFeed({ events }) {
    // Deduplicate by reason (headline) and keep most recent
    const deduped = useMemo(() => {
        if (!events?.length) return [];
        const seen = new Map();
        for (const ev of events) {
            const key = ev.reason || ev.event_id;
            if (!seen.has(key)) seen.set(key, ev);
        }
        return Array.from(seen.values());
    }, [events]);

    if (deduped.length === 0) {
        return (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                Monitoring feeds…
            </div>
        );
    }

    return (
        <div className="intel-feed">
            <div className="intel-feed-header">
                <span className="intel-feed-title">INTEL FEED</span>
                <span className="intel-feed-live">LIVE</span>
                <span className="intel-feed-count">{deduped.length}</span>
            </div>

            {deduped.map((event, idx) => {
                const severity = SEVERITY_BADGE[event.severity] || SEVERITY_BADGE.low;
                const category = event.metadata?.category || event.event_type?.split('.')[0] || 'INTEL';
                const region = event.metadata?.region || '';
                const source = event.metadata?.source_url;
                const sourceDomain = source
                    ? new URL(source).hostname.replace('www.', '').toUpperCase()
                    : 'SENTINEL';
                const headline = event.reason || 'Breaking intelligence update';
                const ago = timeAgo(event.timestamp);

                return (
                    <div key={event.event_id ?? idx} className="intel-card fade-in">
                        {/* Source + Badge row */}
                        <div className="intel-card-top">
                            <span className="intel-source">{sourceDomain}</span>
                            <span className={`intel-badge ${severity.cls}`}>{severity.label}</span>
                            {category && <span className="intel-category">{category.toUpperCase()}</span>}
                        </div>

                        {/* Headline */}
                        {source ? (
                            <a
                                href={source}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="intel-headline-link"
                            >
                                {headline}
                            </a>
                        ) : (
                            <div className="intel-headline">{headline}</div>
                        )}

                        {/* Footer: time + region */}
                        <div className="intel-card-footer">
                            <span className="intel-time">{ago}</span>
                            {region && <span className="intel-region">{region}</span>}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
