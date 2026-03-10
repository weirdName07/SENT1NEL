import { Suspense, useState, useCallback, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { EffectComposer, Bloom, Vignette, ChromaticAberration } from '@react-three/postprocessing';
import { BlendFunction } from 'postprocessing';
import * as THREE from 'three';

import { Globe } from './Globe';
import { EntityPoints } from './EntityPoints';
import { SatelliteOrbits } from './SatelliteOrbits';
import { EntityTooltip } from './EntityTooltip';

function GlobeContent({ entities, selectedTypes }) {
    const [hoveredInfo, setHoveredInfo] = useState(null);
    const [selectedSatellite, setSelectedSatellite] = useState(null);
    const [isInteracting, setIsInteracting] = useState(false);

    const handleHover = useCallback((info) => {
        setHoveredInfo(info);
    }, []);

    return (
        <>
            {/* ── Lighting ───────────────────────────────────────── */}
            <ambientLight intensity={0.15} color="#1a2a4a" />
            <directionalLight
                position={[5, 3, 5]}
                intensity={2.2}
                color="#fff5d0"
                castShadow={false}
            />
            {/* Soft fill from the opposite side */}
            <directionalLight position={[-5, -2, -3]} intensity={0.08} color="#4488ff" />

            {/* ── Camera Controls ────────────────────────────────── */}
            <OrbitControls
                enablePan={false}
                minDistance={1.4}
                maxDistance={5}
                rotateSpeed={0.5}
                zoomSpeed={0.7}
                onStart={() => setIsInteracting(true)}
                onEnd={() => setIsInteracting(false)}
                makeDefault
            />

            {/* ── Globe ──────────────────────────────────────────── */}
            <Globe isInteracting={isInteracting} />

            {/* ── Entities ───────────────────────────────────────── */}
            <EntityPoints
                entities={entities}
                selectedTypes={selectedTypes}
                onHover={handleHover}
            />

            {/* ── Satellite Orbits ───────────────────────────────── */}
            <SatelliteOrbits
                entities={entities}
                selectedSatellite={selectedSatellite}
                visible={selectedTypes.has('satellite')}
            />

            {/* ── Tooltip ────────────────────────────────────────── */}
            {hoveredInfo && (
                <EntityTooltip
                    entity={hoveredInfo.entity}
                    position={hoveredInfo.position}
                />
            )}

            {/* ── Post-processing ────────────────────────────────── */}
            <EffectComposer multisampling={4}>
                <Bloom
                    intensity={1.8}
                    luminanceThreshold={0.3}
                    luminanceSmoothing={0.4}
                    radius={0.7}
                    blendFunction={BlendFunction.ADD}
                />
                <Vignette
                    offset={0.35}
                    darkness={0.85}
                    blendFunction={BlendFunction.NORMAL}
                />
                <ChromaticAberration
                    offset={[0.0008, 0.0008]}
                    blendFunction={BlendFunction.NORMAL}
                />
            </EffectComposer>
        </>
    );
}

export function GlobeScene({ entities, selectedTypes }) {
    return (
        <div className="globe-canvas-wrapper">
            <Canvas
                camera={{
                    position: [0, 0, 2.8],
                    fov: 45,
                    near: 0.1,
                    far: 1000,
                }}
                gl={{
                    antialias: true,
                    toneMapping: THREE.ACESFilmicToneMapping,
                    toneMappingExposure: 1.1,
                    outputColorSpace: THREE.SRGBColorSpace,
                }}
                dpr={[1, 2]}
            >
                <Suspense fallback={null}>
                    <GlobeContent entities={entities} selectedTypes={selectedTypes} />
                </Suspense>
            </Canvas>
        </div>
    );
}
