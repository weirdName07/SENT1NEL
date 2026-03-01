export default function MapOverlays({ counts, entities }) {
    const anomalyCount = entities.filter(e =>
        e.anomalies && e.anomalies.length > 0
    ).length;

    return (
        <div className="map-overlay-bottom">
            <div className="overlay-card">
                <div className="overlay-label">Tracked</div>
                <div className="overlay-value cyan">{counts.total ?? 0}</div>
            </div>
            <div className="overlay-card">
                <div className="overlay-label">Anomalies</div>
                <div className="overlay-value orange">{anomalyCount}</div>
            </div>
            <div className="overlay-card">
                <div className="overlay-label">Sources</div>
                <div className="overlay-value green">5</div>
            </div>
        </div>
    );
}
