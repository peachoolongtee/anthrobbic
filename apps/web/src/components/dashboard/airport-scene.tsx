"use client";

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { Run, RunOverrides } from "@/lib/api-types";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { landingFact } from "@/components/dashboard/plan-summary";

/*
 * An illustrative 3D model of the arrival airport: the run's runways and gates,
 * a taxiway, a terminal, and the delayed aircraft on its way to the assigned
 * gate. It holds first only when the plan's action is a hold. Built from plain
 * shapes in code, so it needs no downloads and works offline. The IDs and how
 * many there are come from the run; positions are evenly spaced slots, and the
 * scene says so. Select a runway or gate to close it.
 */

const NIGHT = "#0b1222";
const ASPHALT = "#2a3550";
const ASPHALT_HOVER = "#36446a";
const MARKING = "#c9d4e8";
const BEACON = "#f5b544";
const DANGER = "#ef5a4c";
const HULL = "#dfe6f2";

const RUNWAY_HALF = 32;
const TAXI_Z = 14;
const GATE_Z = 21;

/** Evenly spaced slots between two ends, centred when there is only one. */
function slot(i: number, count: number, from: number, to: number) {
  return count <= 1 ? (from + to) / 2 : from + (i * (to - from)) / (count - 1);
}
const rz = (i: number, count: number) => slot(i, count, -12, 7);
const gx = (i: number, count: number) => slot(i, count, -20, 14);

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
          <meshStandardMaterial color="#8592a8" />
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
  holds,
  label,
  moving,
}: {
  runwayZ: number | null;
  gateX: number | null;
  /** True only when the plan's action really is a hold. */
  holds: boolean;
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
      // No recovery plan: no path to fly, so it just waits off the field.
      return new THREE.CatmullRomCurve3([hold[0], hold[0].clone().setX(hold[0].x + 0.01)], false, "catmullrom", 0.5);
    }
    const pts = [
      ...(holds ? hold : []),
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
  }, [runwayZ, gateX, holds]);

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
  const color = closed ? "#3a1a1f" : hover && !disabled ? ASPHALT_HOVER : ASPHALT;
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
  disabled,
  onToggle,
}: {
  id: string;
  x: number;
  closed: boolean;
  assigned: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const [hover, setHover] = useState(false);
  const color = closed ? DANGER : assigned ? BEACON : hover && !disabled ? "#3b4a68" : "#2a3550";
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
        <meshStandardMaterial color="#3a4660" />
      </mesh>
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
  // No invented IDs: with no run yet, no runways or gates are drawn.
  const runways = run?.airport?.runways ?? [];
  const gates = run?.airport?.gates ?? [];
  const deal = run?.decision.kind === "DEAL" ? run.decision.package : null;
  const arrival = landingFact(run?.card)?.clock;
  const holds = run?.card?.action_facts.find((f) => f.key === "action")?.value === "hold";
  const runwayIdx = deal ? runways.findIndex((r) => r.id === deal.runway_id) : -1;
  const gateIdx = deal ? gates.findIndex((g) => g.id === deal.gate_id) : -1;

  return (
    <div className="relative size-full">
      <Canvas
        dpr={[1, 1.5]}
        shadows
        camera={{ position: [6, 70, 112], fov: 34, near: 1, far: 500 }}
        gl={{ antialias: true }}
        aria-label="3D model of the arrival airport"
      >
        <color attach="background" args={[NIGHT]} />
        <fog attach="fog" args={[NIGHT, 130, 260]} />
        <ambientLight intensity={0.9} />
        <hemisphereLight args={["#9fb7ff", "#0b1222", 0.5]} />
        <directionalLight position={[30, 60, 40]} intensity={1.9} castShadow />

        {/* Ground and a faint grid */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[400, 400]} />
          <meshStandardMaterial color="#111c31" />
        </mesh>
        <gridHelper args={[200, 50, "#1c2a45", "#142038"]} position={[0, 0.01, 0]} />

        {/* Taxiway and links */}
        <mesh position={[-2, 0.04, TAXI_Z]}>
          <boxGeometry args={[RUNWAY_HALF * 2 - 4, 0.06, 1.6]} />
          <meshStandardMaterial color="#202b40" />
        </mesh>
        {[-22, 18].map((x) => (
          <mesh key={x} position={[x, 0.04, (rz(0, runways.length) + TAXI_Z) / 2]}>
            <boxGeometry args={[1.6, 0.06, TAXI_Z - rz(0, runways.length)]} />
            <meshStandardMaterial color="#202b40" />
          </mesh>
        ))}

        {/* Terminal */}
        <mesh position={[-3, 1.4, GATE_Z + 4.5]} castShadow>
          <boxGeometry args={[42, 2.8, 5]} />
          <meshStandardMaterial color="#1f2a40" metalness={0.3} roughness={0.6} />
        </mesh>

        {runways.map((r, i) => (
          <Runway
            key={r.id}
            id={r.id}
            z={rz(i, runways.length)}
            closed={r.closed}
            assigned={deal?.runway_id === r.id}
            disabled={disabled || (r.closed && !closedRunways.includes(r.id))}
            onToggle={() => onRunway(r.id)}
          />
        ))}
        {gates.map((g, i) => (
          <Gate
            key={g.id}
            id={g.id}
            x={gx(i, gates.length)}
            closed={g.closed}
            assigned={deal?.gate_id === g.id}
            disabled={disabled}
            onToggle={() => onGate(g.id)}
          />
        ))}

        <DelayedFlight
          key={`${deal?.runway_id}-${deal?.gate_id}`}
          runwayZ={deal ? rz(runwayIdx, runways.length) : null}
          gateX={deal ? gx(gateIdx, gates.length) : null}
          holds={holds}
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
                  <span className="text-destructive"> no recovery plan</span>
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
      <p className="pointer-events-none absolute right-3 bottom-3 rounded bg-warning-soft px-1.5 py-0.5 text-[11px] font-medium text-warning lg:right-[24.5rem]">
        Illustrative layout, not to scale: only the runway and gate IDs are from this run. Drag to turn.
      </p>
    </div>
  );
}

export default AirportScene;
