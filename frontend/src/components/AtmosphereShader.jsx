import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// Fresnel-based atmosphere that creates the blue glow around the Earth's limb
const atmosVert = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const atmosFrag = /* glsl */ `
  uniform vec3 uColor;
  uniform float uIntensity;
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vec3 viewDir = normalize(-vPosition);
    float fresnel = pow(1.0 - abs(dot(viewDir, vNormal)), 3.5);
    fresnel = clamp(fresnel * uIntensity, 0.0, 1.0);
    gl_FragColor = vec4(uColor, fresnel * 0.85);
  }
`;

export function AtmosphereShader({ radius = 1.03, color = [0.1, 0.5, 1.0], intensity = 1.4 }) {
    const matRef = useRef();

    // Subtle pulse
    useFrame(({ clock }) => {
        if (matRef.current) {
            matRef.current.uniforms.uIntensity.value =
                intensity + Math.sin(clock.getElapsedTime() * 0.4) * 0.08;
        }
    });

    return (
        <mesh scale={[radius, radius, radius]}>
            <sphereGeometry args={[1, 64, 64]} />
            <shaderMaterial
                ref={matRef}
                vertexShader={atmosVert}
                fragmentShader={atmosFrag}
                uniforms={{
                    uColor: { value: new THREE.Vector3(...color) },
                    uIntensity: { value: intensity },
                }}
                transparent
                side={THREE.FrontSide}
                depthWrite={false}
                blending={THREE.AdditiveBlending}
            />
        </mesh>
    );
}
