import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const EARTH_RADIUS = 1.0;

function latLonToVec3(lat, lon, radius = 1.0) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    return new THREE.Vector3(
        -radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta),
    );
}

// Build a smooth curve approximating the orbital path for a satellite
function buildOrbitLine(lat, lon, altNorm, steps = 180) {
    const points = [];
    // Use inclination hint from lat to draw rough orbital ring
    const inclination = Math.abs(lat) * (Math.PI / 180);
    const r = EARTH_RADIUS + altNorm;
    for (let i = 0; i <= steps; i++) {
        const angle = (i / steps) * Math.PI * 2;
        const x = r * Math.cos(angle);
        const y = r * Math.sin(angle) * Math.sin(inclination);
        const z = r * Math.sin(angle) * Math.cos(inclination);
        points.push(new THREE.Vector3(x, y, z));
    }
    return points;
}

export function SatelliteOrbits({ entities, selectedSatellite, visible }) {
    const satellites = useMemo(
        () => entities.filter(e => e.entity_type === 'satellite'),
        [entities]
    );

    if (!visible || satellites.length === 0) return null;

    return (
        <group>
            {satellites.map((sat) => {
                const isSelected = selectedSatellite?.source_id === sat.source_id;
                if (!isSelected) return null; // Only render orbit for selected sat

                const pos = sat.position || {};
                const lat = pos.latitude ?? 0;
                const lon = pos.longitude ?? 0;
                const altNorm = 0.06;
                const points = buildOrbitLine(lat, lon, altNorm);
                const curve = new THREE.CatmullRomCurve3(points, true);
                const tubePoints = curve.getPoints(360);
                const geom = new THREE.BufferGeometry().setFromPoints(tubePoints);

                return (
                    <line key={sat.source_id} geometry={geom}>
                        <lineBasicMaterial
                            color="#8b5cf6"
                            transparent
                            opacity={0.5}
                            depthWrite={false}
                        />
                    </line>
                );
            })}
        </group>
    );
}
