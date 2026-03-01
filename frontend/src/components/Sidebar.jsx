import { ENTITY_ICONS } from '../constants';
import EventFeed from './EventFeed';
import EntityList from './EntityList';

export default function Sidebar({
    activeTab,
    onTabChange,
    entities,
    events,
    selectedTypes,
    onToggleType,
}) {
    return (
        <aside className="sidebar">
            <div className="sidebar-tabs">
                <button
                    className={`sidebar-tab ${activeTab === 'events' ? 'active' : ''}`}
                    onClick={() => onTabChange('events')}
                >
                    Events
                </button>
                <button
                    className={`sidebar-tab ${activeTab === 'entities' ? 'active' : ''}`}
                    onClick={() => onTabChange('entities')}
                >
                    Entities
                </button>
            </div>

            {/* Type filter chips */}
            <div className="filter-bar">
                {Object.entries(ENTITY_ICONS).map(([type, icon]) => (
                    <button
                        key={type}
                        className={`filter-chip ${selectedTypes.has(type) ? 'active' : ''}`}
                        onClick={() => onToggleType(type)}
                    >
                        <span className={`dot ${type}`} style={{
                            backgroundColor: selectedTypes.has(type)
                                ? `var(--entity-${type})` : 'var(--text-muted)',
                        }} />
                        {icon} {type}
                    </button>
                ))}
            </div>

            <div className="sidebar-content">
                {activeTab === 'events' && <EventFeed events={events} />}
                {activeTab === 'entities' && (
                    <EntityList entities={entities} selectedTypes={selectedTypes} />
                )}
            </div>
        </aside>
    );
}
