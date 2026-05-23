"use client";

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, MeshDistortMaterial, OrbitControls, Environment, ContactShadows, SpotLight } from "@react-three/drei";
import * as THREE from "three";

interface HoloCoreProps {
  isSpeaking: boolean;
  audioLevel: number; // 0 to 1
  isThinking: boolean;
}

function CoreGeometry({ isSpeaking, audioLevel, isThinking }: HoloCoreProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<any>(null);
  const outerMeshRef = useRef<THREE.Mesh>(null);

  // Animate the core based on state
  useFrame((state, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.x += delta * 0.2;
      meshRef.current.rotation.y += delta * 0.3;
      
      // Target scale based on audio
      const targetScale = isSpeaking ? 1.2 + (audioLevel * 0.8) : (isThinking ? 1.0 + Math.sin(state.clock.elapsedTime * 3) * 0.1 : 1.0);
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
    }
    
    if (outerMeshRef.current) {
      outerMeshRef.current.rotation.x -= delta * 0.1;
      outerMeshRef.current.rotation.y -= delta * 0.15;
      
      const targetScaleOuter = isSpeaking ? 1.5 + (audioLevel * 0.5) : (isThinking ? 1.4 : 1.3);
      outerMeshRef.current.scale.lerp(new THREE.Vector3(targetScaleOuter, targetScaleOuter, targetScaleOuter), 0.05);
    }

    if (materialRef.current) {
      materialRef.current.distort = THREE.MathUtils.lerp(
        materialRef.current.distort,
        isSpeaking ? 0.6 + audioLevel : (isThinking ? 0.4 : 0.2),
        0.1
      );
      materialRef.current.speed = THREE.MathUtils.lerp(
        materialRef.current.speed,
        isSpeaking ? 5 + (audioLevel * 10) : (isThinking ? 3 : 1),
        0.1
      );
      
      // Change color slightly when speaking/thinking
      const targetColor = isSpeaking 
        ? new THREE.Color("#8b5cf6") // Purple when speaking
        : isThinking 
          ? new THREE.Color("#0ea5e9") // Light blue when thinking
          : new THREE.Color("#3b82f6"); // Default blue
          
      materialRef.current.color.lerp(targetColor, 0.1);
    }
  });

  return (
    <group>
      {/* Inner glowing core */}
      <Float speed={2} rotationIntensity={1} floatIntensity={1}>
        <mesh ref={meshRef}>
          <icosahedronGeometry args={[1, 4]} />
          <MeshDistortMaterial
            ref={materialRef}
            color="#3b82f6"
            emissive="#1e3a8a"
            emissiveIntensity={2}
            envMapIntensity={1}
            clearcoat={1}
            clearcoatRoughness={0.1}
            metalness={0.8}
            roughness={0.2}
            distort={0.2}
            speed={1}
          />
        </mesh>
      </Float>

      {/* Outer wireframe shell */}
      <Float speed={1.5} rotationIntensity={0.5} floatIntensity={0.5}>
        <mesh ref={outerMeshRef}>
          <icosahedronGeometry args={[1, 2]} />
          <meshBasicMaterial 
            color="#60a5fa" 
            wireframe 
            transparent 
            opacity={0.15} 
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      </Float>

      {/* Particle dust */}
      <Particles isSpeaking={isSpeaking} />
    </group>
  );
}

// Simple floating particles around the core
function Particles({ isSpeaking }: { isSpeaking: boolean }) {
  const count = 100;
  const mesh = useRef<THREE.InstancedMesh>(null);
  
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const particles = useMemo(() => {
    const temp = [];
    for (let i = 0; i < count; i++) {
      const t = Math.random() * 100;
      const factor = 20 + Math.random() * 100;
      const speed = 0.01 + Math.random() / 200;
      const xFactor = -50 + Math.random() * 100;
      const yFactor = -50 + Math.random() * 100;
      const zFactor = -50 + Math.random() * 100;
      temp.push({ t, factor, speed, xFactor, yFactor, zFactor, mx: 0, my: 0 });
    }
    return temp;
  }, [count]);

  useFrame((state) => {
    if (!mesh.current) return;
    const time = state.clock.getElapsedTime();
    const speedMult = isSpeaking ? 3 : 1;
    
    particles.forEach((particle, i) => {
      let { t, factor, speed, xFactor, yFactor, zFactor } = particle;
      t = particle.t += speed * speedMult / 2;
      const a = Math.cos(t) + Math.sin(t * 1) / 10;
      const b = Math.sin(t) + Math.cos(t * 2) / 10;
      const s = Math.cos(t);
      
      dummy.position.set(
        (particle.mx / 10) * a + xFactor + Math.cos((t / 10) * factor) + (Math.sin(t * 1) * factor) / 10,
        (particle.my / 10) * b + yFactor + Math.sin((t / 10) * factor) + (Math.cos(t * 2) * factor) / 10,
        (particle.my / 10) * b + zFactor + Math.cos((t / 10) * factor) + (Math.sin(t * 3) * factor) / 10
      );
      
      // Keep particles somewhat near the center
      dummy.position.normalize().multiplyScalar(3 + Math.sin(time + i) * 1.5);
      
      dummy.scale.setScalar(s * 0.05);
      dummy.updateMatrix();
      mesh.current!.setMatrixAt(i, dummy.matrix);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, count]}>
      <sphereGeometry args={[0.2, 8, 8]} />
      <meshBasicMaterial color="#93c5fd" transparent opacity={0.4} blending={THREE.AdditiveBlending} />
    </instancedMesh>
  );
}

export default function HoloCore({ isSpeaking = false, audioLevel = 0, isThinking = false }: HoloCoreProps) {
  return (
    <div className="w-full h-full relative">
      <Canvas camera={{ position: [0, 0, 8], fov: 45 }} dpr={[1, 2]} gl={{ alpha: true }}>
        
        <ambientLight intensity={0.5} />
        <SpotLight 
          position={[10, 10, 10]} 
          angle={0.15} 
          penumbra={1} 
          intensity={2} 
          color="#8b5cf6" 
        />
        <SpotLight 
          position={[-10, -10, -10]} 
          angle={0.15} 
          penumbra={1} 
          intensity={2} 
          color="#3b82f6" 
        />
        
        <CoreGeometry isSpeaking={isSpeaking} audioLevel={audioLevel} isThinking={isThinking} />
        
        <ContactShadows 
          position={[0, -3.5, 0]} 
          opacity={0.4} 
          scale={10} 
          blur={2.5} 
          far={4} 
          color={isSpeaking ? "#8b5cf6" : "#3b82f6"} 
        />
        
        {/* Environment map for realistic reflections */}
        <Environment preset="city" />
        <OrbitControls 
          enableZoom={false} 
          enablePan={false} 
          autoRotate 
          autoRotateSpeed={0.5} 
          maxPolarAngle={Math.PI / 2 + 0.2}
          minPolarAngle={Math.PI / 2 - 0.2}
        />
      </Canvas>
    </div>
  );
}
