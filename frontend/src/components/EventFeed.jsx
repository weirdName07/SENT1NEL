export default function EventFeed({ events }) {
    if (!events || events.length === 0) {
        return (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                Waiting for events…
            </div>
        );
    }

    return (
        <div>
            {events.map((event, idx) => {
                const category = (event.event_type ?? '').split('.')[0];
                const time = event.timestamp
                    ? new Date(event.timestamp).toLocaleTimeString()
                    : '';

                return (
                    <div key={event.event_id ?? idx} className="event-card fade-in">
                        <div className="event-header">
                            <span className={`event-type ${category}`}>
                                {event.event_type ?? 'unknown'}
                            </span>
                            <span className="event-time">{time}</span>
                        </div>
                        <div className="event-reason">
                            {event.reason || 'No details'}
                        </div>
                        <div className="event-meta">
                            {event.source_id && <span>ID: {event.source_id}</span>}
                            {event.severity && <span>Sev: {event.severity}</span>}
                            {event.entity_type && <span>{event.entity_type}</span>}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
