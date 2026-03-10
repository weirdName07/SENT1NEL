import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Stars, useTexture } from '@react-three/drei';
import * as THREE from 'three';
import { AtmosphereShader } from './AtmosphereShader';

export function Globe({ isInteracting }) {
    const earthRef = useRef();
    const cloudsRef = useRef();

    const [dayMap, normalMap, specularMap] = useTexture([
        '/textures/earth_day.jpg',
        '/textures/earth_normal.jpg',
        '/textures/earth_specular.jpg',
    ]);

    // Auto-rotate when user is idle
    useFrame((_, delta) => {
        if (!isInteracting && earthRef.current) {
            earthRef.current.rotation.y += delta * 0.04;
        }
        if (!isInteracting && cloudsRef.current) {
            cloudsRef.current.rotation.y += delta * 0.043; // slightly faster than earth
        }
    });

    return (
        <group>
            {/* ── Stars ─────────────────────────────────────── */}
            <Stars
                radius={80}
                depth={60}
                count={8000}
                factor={3}
                saturation={0.1}
                fade
                speed={0.3}
            />

            {/* ── Earth ──────────────────────────────────────── */}
            <mesh ref={earthRef}>
                <sphereGeometry args={[1, 96, 96]} />
                <meshPhongMaterial
                    map={dayMap}
                    normalMap={normalMap}
                    specularMap={specularMap}
                    specular={new THREE.Color(0x333333)}
                    shininess={18}
                    normalScale={new THREE.Vector2(0.6, 0.6)}
                />
            </mesh>

            {/* ── Cloud layer ───────────────────────────────── */}
            <mesh ref={cloudsRef}>
                <sphereGeometry args={[1.005, 64, 64]} />
                <meshPhongMaterial
                    color={0xffffff}
                    transparent
                    opacity={0.12}
                    depthWrite={false}
                    side={THREE.FrontSide}
                />
            </mesh>

            {/* ── Atmosphere glow ───────────────────────────── */}
            <AtmosphereShader radius={1.06} intensity={1.5} color={[0.05, 0.35, 0.9]} />

            {/* ── Outer haze ────────────────────────────────── */}
            <AtmosphereShader radius={1.12} intensity={0.8} color={[0.02, 0.15, 0.6]} />
        </group>
    );
}
