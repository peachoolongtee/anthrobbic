"use client";

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { Run, RunOverrides } from "@/lib/api-types";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

/*
 * A 3D model of the demo airport: two parallel runways landing westbound
 * (27L, 27R), a taxiway, a terminal with three gates, and the delayed
 * aircraft flying its hold, approach and taxi to the assigned gate. Built
 * from plain shapes in code, so it needs no downloads and works offline.
 * The layout and the parked aircraft are synthetic, like the diagram, and
 * the scene says so. Select a runway or gate to close it.
 */

const NIGHT = "#111215";
const ASPHALT = "#2b2d34";
const ASPHALT_HOVER = "#3a3c46";
const MARKING = "#d6d7de";
const BEACON = "#a48bfa";
const DANGER = "#f87171";
const HULL = "#e6e7ec";

const RUNWAY_Z: Record<string, number> = { "27L": -7, "27R": 5 };
const RUNWAY_HALF = 32;
const TAXI_Z = 14;
const GATE_X: Record<string, number> = { B12: -16, B14: -4, C3: 10 };
const GATE_Z = 21;

const rz = (id: string, i: number) => RUNWAY_Z[id] ?? -7 + i * 12;
const gx = (id: string, i: number) => GATE_X[id] ?? -16 + i * 13;

function cursor(on: boolean) {
  document.body.style.cursor = on ? "pointer" : "";
}

/** A low-poly airliner, nose along +x, about 6 units long. */
function Airliner({ accent = HULL, glow = false }: { accent?: string; glow?: boolean }) {
  const emissive = glow ? BEACON : "#000000";
  return (
    <group>
      {/* Fuselage */}
      <mesh rotation={[0, 0, -Math.PI / 2]} castShadow>
        <capsuleGeometry args={[0.38, 4.6, 4, 12]} />
        <meshStandardMaterial color={HULL} metalness={0.2} roughness={0.5} />
      </mesh>
      {/* Wings, swept back */}
      {[1, -1].map((side) => (
        <mesh key={side} position={[-0.2, -0.05, side * 1.55]} rotation={[0, side * 0.45, 0]} castShadow>
          <boxGeometry args={[1.1, 0.08, 2.8]} />
          <meshStandardMaterial color={accent} emissive={emissive} emissiveIntensity={glow ? 0.35 : 0} />
        </mesh>
      ))}
      {/* Engines */}
      {[1, -1].map((side) => (
        <mesh key={side} position={[0.25, -0.32, side * 1.25]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.2, 0.22, 0.8, 10]} />
          <meshStandardMaterial color="#8c8e99" />
        </mesh>
      ))}
      {/* Tailplane */}
      {[1, -1].map((side) => (
        <mesh key={side} position={[-2.45, 0.05, side * 0.65]} rotation={[0, side * 0.5, 0]}>
          <boxGeometry args={[0.55, 0.06, 1.2]} />
          <meshStandardMaterial color={accent} />
        </mesh>
      ))}
      {/* Fin */}
      <mesh position={[-2.4, 0.6, 0]} rotation={[0, 0, 0.35]}>
        <boxGeometry args={[0.8, 1.1, 0.07]} />
        <meshStandardMaterial color={accent} emissive={emissive} emissiveIntensity={glow ? 0.5 : 0} />
      </mesh>
    </group>
  );
}

/** The delayed flight: hold, approach, landing roll, taxi to the gate, then again. */
function DelayedFlight({
  runwayZ,
  gateX,
  label,
  moving,
}: {
  runwayZ: number | null;
  gateX: number | null;
  label: React.ReactNode;
  moving: boolean;
}) {
  const ref = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Mesh>(null);

  const path = useMemo(() => {
    const hold = [
      new THREE.Vector3(18, 10, -34),
      new THREE.Vector3(28, 10, -28),
      new THREE.Vector3(18, 10, -22),
      new THREE.Vector3(8, 10, -28),
    ];
    if (runwayZ === null || gateX === null) {
      // No recovery plan: keep holding.
      return new THREE.CatmullRomCurve3(hold, true, "catmullrom", 0.5);
    }
    const pts = [
      ...hold,
      new THREE.Vector3(38, 9, -20),
      new THREE.Vector3(44, 6, runwayZ - 2),
      new THREE.Vector3(40, 3.5, runwayZ),
      new THREE.Vector3(RUNWAY_HALF, 0.6, runwayZ),
      new THREE.Vector3(0, 0.6, runwayZ),
      new THREE.Vector3(-18, 0.6, runwayZ),
      new THREE.Vector3(-22, 0.6, (runwayZ + TAXI_Z) / 2),
      new THREE.Vector3(-20, 0.6, TAXI_Z),
      new THREE.Vector3(gateX, 0.6, TAXI_Z),
      new THREE.Vector3(gateX, 0.6, GATE_Z - 3.5),
    ];
    return new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.3);
  }, [runwayZ, gateX]);

  const t = useRef(0);
  const ahead = useMemo(() => new THREE.Vector3(), []);
  useFrame((_, dt) => {
    const g = ref.current;
    if (!g) return;
    if (moving) t.current = (t.current + dt / 22) % 1;
    const u = moving ? t.current : 0.15;
    const p = path.getPointAt(u);
    path.getPointAt(Math.min(u + 0.002, 1), ahead);
    g.position.copy(p);
    if (ahead.distanceToSquared(p) > 1e-6) {
      g.lookAt(ahead);
      g.rotateY(-Math.PI / 2);
    }
    if (ring.current) {
      const s = 1 + 0.25 * Math.sin(performance.now() / 300);
      ring.current.scale.set(s, s, s);
    }
  });

  return (
    <group ref={ref}>
      <Airliner accent={BEACON} glow />
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]}>
        <ringGeometry args={[3.2, 3.4, 48]} />
        <meshBasicMaterial color={BEACON} transparent opacity={0.6} side={THREE.DoubleSide} />
      </mesh>
      <Html position={[0, 2.4, 0]} center zIndexRange={[5, 0]}>
        {label}
      </Html>
    </group>
  );
}

function Runway({
  id,
  z,
  closed,
  assigned,
  disabled,
  onToggle,
}: {
  id: string;
  z: number;
  closed: boolean;
  assigned: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const [hover, setHover] = useState(false);
  const color = closed ? "#3a1d22" : hover && !disabled ? ASPHALT_HOVER : ASPHALT;
  const handlers = {
    onPointerOver: (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      setHover(true);
      cursor(!disabled);
    },
    onPointerOut: () => {
      setHover(false);
      cursor(false);
    },
    onClick: (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      if (!disabled) onToggle();
    },
  };
  return (
    <group position={[0, 0, z]}>
      {/* Edge glow: amber when assigned, red when closed */}
      {(assigned || closed) && (
        <mesh position={[0, 0.02, 0]}>
          <boxGeometry args={[RUNWAY_HALF * 2 + 1, 0.05, 5.2]} />
          <meshBasicMaterial color={closed ? DANGER : BEACON} transparent opacity={0.55} />
        </mesh>
      )}
      <mesh position={[0, 0.06, 0]} receiveShadow {...handlers}>
        <boxGeometry args={[RUNWAY_HALF * 2, 0.1, 4.4]} />
        <meshStandardMaterial color={color} roughness={0.9} />
      </mesh>
      {/* Centreline */}
      {!closed &&
        Array.from({ length: 14 }, (_, i) => (
          <mesh key={i} position={[-RUNWAY_HALF + 4 + i * 4.4, 0.12, 0]}>
            <boxGeometry args={[2, 0.02, 0.15]} />
            <meshBasicMaterial color={MARKING} />
          </mesh>
        ))}
      {/* Closed: crosses at both ends and the middle */}
      {closed &&
        [-RUNWAY_HALF + 5, 0, RUNWAY_HALF - 5].map((x) => (
          <group key={x} position={[x, 0.13, 0]}>
            {[0.6, -0.6].map((r) => (
              <mesh key={r} rotation={[0, r, 0]}>
                <boxGeometry args={[4.4, 0.02, 0.35]} />
                <meshBasicMaterial color={DANGER} />
              </mesh>
            ))}
          </group>
        ))}
      <Html position={[RUNWAY_HALF + 3, 0.2, 0]} center zIndexRange={[4, 0]}>
        <button
          type="button"
          disabled={disabled}
          onClick={onToggle}
          aria-pressed={closed}
          aria-label={`Runway ${id}, ${closed ? "closed" : "open"}${assigned ? ", assigned" : ""}. ${closed ? "Reopen" : "Close"} it.`}
          className={`rounded-md px-1.5 py-0.5 font-display text-sm font-semibold whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            closed ? "bg-destructive/20 text-destructive" : assigned ? "bg-beacon/15 text-beacon" : "bg-card/70 text-muted-foreground"
          }`}
        >
          {id}
        </button>
      </Html>
    </group>
  );
}

function Gate({
  id,
  x,
  closed,
  assigned,
  parked,
  disabled,
  onToggle,
}: {
  id: string;
  x: number;
  closed: boolean;
  assigned: boolean;
  parked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const [hover, setHover] = useState(false);
  const color = closed ? DANGER : assigned ? BEACON : hover && !disabled ? "#3d3f49" : "#2b2d34";
  return (
    <group position={[x, 0, GATE_Z]}>
      <mesh
        position={[0, 0.08, -1.5]}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover(true);
          cursor(!disabled);
        }}
        onPointerOut={() => {
          setHover(false);
          cursor(false);
        }}
        onClick={(e) => {
          e.stopPropagation();
          if (!disabled) onToggle();
        }}
      >
        <boxGeometry args={[6, 0.12, 6]} />
        <meshStandardMaterial
          color={color}
          emissive={assigned || closed ? color : "#000000"}
          emissiveIntensity={assigned || closed ? 0.25 : 0}
          transparent
          opacity={0.85}
        />
      </mesh>
      {/* Jet bridge */}
      <mesh position={[0, 1, 1.4]}>
        <boxGeometry args={[0.6, 0.6, 2.4]} />
        <meshStandardMaterial color="#3a3b44" />
      </mesh>
      {parked && !closed && (
        <group position={[0, 0.6, -2]} rotation={[0, Math.PI / 2, 0]} scale={0.8}>
          <Airliner accent="#7d7f8a" />
        </group>
      )}
      <Html position={[0, 0.2, 2.6]} center zIndexRange={[4, 0]}>
        <button
          type="button"
          disabled={disabled}
          onClick={onToggle}
          aria-pressed={closed}
          aria-label={`Gate ${id}, ${closed ? "blocked" : "free"}${assigned ? ", assigned" : ""}. ${closed ? "Free" : "Block"} it.`}
          className={`rounded-md px-1.5 py-0.5 font-display text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            closed ? "bg-destructive/20 text-destructive" : assigned ? "bg-beacon/15 text-beacon" : "bg-card/70 text-muted-foreground"
          }`}
        >
          {id}
        </button>
      </Html>
    </group>
  );
}

export function AirportScene({
  run,
  flightId,
  overrides,
  disabled,
  onRunway,
  onGate,
}: {
  run: Run | null;
  flightId: string | null;
  overrides: RunOverrides;
  disabled: boolean;
  onRunway: (id: string) => void;
  onGate: (id: string) => void;
}) {
  const moving = !useReducedMotion();
  const closedRunways = overrides.closed_runways ?? [];
  const closedGates = overrides.closed_gates ?? [];
  const runways = run?.airport?.runways ?? Object.keys(RUNWAY_Z).map((id) => ({ id, closed: closedRunways.includes(id) }));
  const gates = run?.airport?.gates ?? Object.keys(GATE_X).map((id) => ({ id, closed: closedGates.includes(id) }));
  const deal = run?.decision.kind === "DEAL" ? run.decision.package : null;
  const arrival = run?.card?.action_facts.find((f) => f.key === "arrival")?.value;
  const runwayIdx = deal ? runways.findIndex((r) => r.id === deal.runway_id) : -1;
  const gateIdx = deal ? gates.findIndex((g) => g.id === deal.gate_id) : -1;

  return (
    <div className="relative size-full">
      <Canvas
        dpr={[1, 1.75]}
        shadows
        camera={{ position: [6, 70, 112], fov: 34, near: 1, far: 500 }}
        gl={{ antialias: true }}
        aria-label="3D model of the arrival airport"
      >
        <color attach="background" args={[NIGHT]} />
        <fog attach="fog" args={[NIGHT, 130, 260]} />
        <ambientLight intensity={0.9} />
        <hemisphereLight args={["#d9d4ff", "#111215", 0.5]} />
        <directionalLight position={[30, 60, 40]} intensity={1.9} castShadow />

        {/* Ground and a faint grid */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[400, 400]} />
          <meshStandardMaterial color="#16171b" />
        </mesh>
        <gridHelper args={[200, 50, "#26272e", "#1c1d22"]} position={[0, 0.01, 0]} />

        {/* Taxiway and links */}
        <mesh position={[-2, 0.04, TAXI_Z]}>
          <boxGeometry args={[RUNWAY_HALF * 2 - 4, 0.06, 1.6]} />
          <meshStandardMaterial color="#23252b" />
        </mesh>
        {[-22, 18].map((x) => (
          <mesh key={x} position={[x, 0.04, (RUNWAY_Z["27L"] + TAXI_Z) / 2]}>
            <boxGeometry args={[1.6, 0.06, TAXI_Z - RUNWAY_Z["27L"]]} />
            <meshStandardMaterial color="#23252b" />
          </mesh>
        ))}

        {/* Terminal */}
        <mesh position={[-3, 1.4, GATE_Z + 4.5]} castShadow>
          <boxGeometry args={[42, 2.8, 5]} />
          <meshStandardMaterial color="#202127" metalness={0.3} roughness={0.6} />
        </mesh>

        {runways.map((r, i) => (
          <Runway
            key={r.id}
            id={r.id}
            z={rz(r.id, i)}
            closed={r.closed}
            assigned={deal?.runway_id === r.id}
            disabled={disabled}
            onToggle={() => onRunway(r.id)}
          />
        ))}
        {gates.map((g, i) => (
          <Gate
            key={g.id}
            id={g.id}
            x={gx(g.id, i)}
            closed={g.closed}
            assigned={deal?.gate_id === g.id}
            parked={deal?.gate_id !== g.id && i % 2 === 1}
            disabled={disabled}
            onToggle={() => onGate(g.id)}
          />
        ))}

        <DelayedFlight
          key={`${deal?.runway_id}-${deal?.gate_id}`}
          runwayZ={deal ? rz(deal.runway_id, runwayIdx) : null}
          gateX={deal ? gx(deal.gate_id, gateIdx) : null}
          moving={moving}
          label={
            flightId && (
              <div className="pointer-events-none rounded-lg border border-beacon/50 bg-card/85 px-2 py-1 text-xs whitespace-nowrap backdrop-blur">
                <span className="font-display font-semibold">{flightId}</span>
                {deal ? (
                  <span className="text-muted-foreground">
                    {" "}
                    {deal.runway_id} {arrival ? `at ${arrival}` : ""}, gate {deal.gate_id}
                  </span>
                ) : (
                  <span className="text-destructive"> holding, no recovery plan</span>
                )}
              </div>
            )
          }
        />

        <OrbitControls
          enablePan={false}
          minDistance={45}
          maxDistance={200}
          minPolarAngle={0.25}
          maxPolarAngle={1.25}
          target={[2, 2, 2]}
        />
      </Canvas>
      <p className="pointer-events-none absolute right-3 bottom-3 rounded border border-dashed border-muted-foreground/60 bg-card/70 px-1.5 py-0.5 text-xs text-muted-foreground lg:right-[24.5rem]">
        Synthetic airport layout. Drag to turn.
      </p>
    </div>
  );
}

export default AirportScene;
