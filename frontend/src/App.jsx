import { useState, useCallback } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import { GlobeScene } from './components/GlobeScene';
import { useEntities } from './hooks/useEntities';
import { useEvents } from './hooks/useEvents';
import { useHealth } from './hooks/useHealth';

export default function App() {
    const [activeTab, setActiveTab] = useState('events');
    const [selectedTypes, setSelectedTypes] = useState(new Set([
        'aircraft', 'vessel', 'satellite', 'earthquake', 'weather',
    ]));

    // Use globe center as the spatial query anchor (world coverage)
    const { entities, counts } = useEntities(selectedTypes, 0, 0);
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

    return (
        <div className="app">
            <Header counts={counts} health={health} />

            {/* 3D Globe fills the background */}
            <div className="globe-container">
                <GlobeScene entities={entities} selectedTypes={selectedTypes} />
            </div>

            {/* Intelligence Sidebar */}
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
