import { useRef, useMemo, useCallback } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// Geo to 3D cartesian
function latLonToVec3(lat, lon, radius = 1.0) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    return new THREE.Vector3(
        -radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta),
    );
}

// color per entity type [r,g,b] 0-255
const TYPE_COLORS = {
    aircraft: [0, 212, 255],
    vessel: [59, 130, 246],
    satellite: [180, 140, 255],
    earthquake: [255, 60, 60],
    weather: [16, 230, 140],
};

// altitude above globe surface (normalized units)
const TYPE_ALTITUDE = {
    aircraft: 0.008,
    vessel: 0.002,
    satellite: 0.06,
    earthquake: 0.003,
    weather: 0.004,
};

// Size multiplier per entity type
const TYPE_SCALE = {
    aircraft: 0.7,
    vessel: 1.0,
    satellite: 1.4,
    earthquake: 1.3,
    weather: 1.1,
};

const EARTH_RADIUS = 1.0;
const MAX_ENTITIES = 50000;

/* ── Separate layer per entity type for differentiation ─── */

function EntityTypeLayer({ entities, type, selectedTypes, onHover }) {
    const meshRef = useRef();
    const dummy = useMemo(() => new THREE.Object3D(), []);

    const visible = useMemo(() => {
        if (!selectedTypes.has(type)) return [];
        return entities.filter(e => e.entity_type === type).slice(0, MAX_ENTITIES);
    }, [entities, selectedTypes, type]);

    const color = useMemo(() => {
        const c = TYPE_COLORS[type] || [200, 200, 200];
        return new THREE.Color(c[0] / 255, c[1] / 255, c[2] / 255);
    }, [type]);

    const scale = TYPE_SCALE[type] || 1.0;

    // Update instance transforms
    useFrame(() => {
        if (!meshRef.current || visible.length === 0) return;
        for (let i = 0; i < visible.length; i++) {
            const e = visible[i];
            const pos = e.position || {};
            const lat = pos.latitude ?? e.lat ?? 0;
            const lon = pos.longitude ?? e.lon ?? 0;
            const alt = TYPE_ALTITUDE[type] || 0.005;
            const r = EARTH_RADIUS + alt;
            const v = latLonToVec3(lat, lon, r);
            dummy.position.copy(v);

            // Orient normal to surface + heading for aircraft
            dummy.lookAt(0, 0, 0);
            if (type === 'aircraft') {
                const hdg = (e.velocity?.heading_deg ?? 0) * (Math.PI / 180);
                dummy.rotateZ(hdg);
            }

            dummy.scale.setScalar(scale);
            dummy.updateMatrix();
            meshRef.current.setMatrixAt(i, dummy.matrix);
        }
        meshRef.current.count = visible.length;
        meshRef.current.instanceMatrix.needsUpdate = true;
    });

    const handlePointerMove = useCallback((e) => {
        if (e.instanceId === undefined || e.instanceId >= visible.length) return;
        const entity = visible[e.instanceId];
        if (!entity) return;
        const pos = entity.position || {};
        const lat = pos.latitude ?? entity.lat ?? 0;
        const lon = pos.longitude ?? entity.lon ?? 0;
        const alt = TYPE_ALTITUDE[type] || 0.005;
        const vec = latLonToVec3(lat, lon, EARTH_RADIUS + alt + 0.02);
        onHover?.({ entity, position: [vec.x, vec.y, vec.z] });
    }, [visible, onHover, type]);

    const handlePointerOut = useCallback(() => {
        onHover?.(null);
    }, [onHover]);

    // Geometry must be defined before any conditional return — Rules of Hooks
    const geometry = useMemo(() => {
        switch (type) {
            case 'aircraft':
                // Cone pointing up = directional marker
                return <coneGeometry args={[0.003, 0.008, 4]} />;
            case 'vessel':
                // Wider, flatter shape
                return <boxGeometry args={[0.005, 0.002, 0.007]} />;
            case 'satellite':
                // Diamond/octahedron — distinct and larger
                return <octahedronGeometry args={[0.004, 0]} />;
            case 'earthquake':
                // Ring/torus for pulsing effect
                return <torusGeometry args={[0.004, 0.0015, 6, 8]} />;
            case 'weather':
                // Small flat circle
                return <circleGeometry args={[0.004, 8]} />;
            default:
                return <sphereGeometry args={[0.003, 6, 6]} />;
        }
    }, [type]);

    return (
        <instancedMesh
            ref={meshRef}
            args={[undefined, undefined, MAX_ENTITIES]}
            onPointerMove={handlePointerMove}
            onPointerOut={handlePointerOut}
            frustumCulled={false}
        >
            {geometry}
            <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={1.2}
                roughness={0.2}
                metalness={0.1}
                transparent
                opacity={0.9}
                depthWrite={false}
            />
        </instancedMesh>
    );
}

const ENTITY_TYPES = ['aircraft', 'vessel', 'satellite', 'earthquake', 'weather'];

export function EntityPoints({ entities, onHover, selectedTypes }) {
    return (
        <group>
            {ENTITY_TYPES.map(type => (
                <EntityTypeLayer
                    key={type}
                    type={type}
                    entities={entities}
                    selectedTypes={selectedTypes}
                    onHover={onHover}
                />
            ))}
        </group>
    );
}
