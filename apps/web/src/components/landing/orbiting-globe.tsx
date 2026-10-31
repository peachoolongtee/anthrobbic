"use client"

import { useEffect, useMemo, useRef } from "react"
import { Globe } from "@/components/ui/cobe-globe"
import { Airliner } from "@/components/landing/airliner"

export interface GlobeRoute {
  id: string
  from: [number, number]
  to: [number, number]
}

const NIGHT_BASE: [number, number, number] = [0.22, 0.29, 0.45]
const SKY: [number, number, number] = [0.42, 0.72, 1]
const BEACON: [number, number, number] = [1, 0.74, 0.32]
const HALO: [number, number, number] = [0.16, 0.24, 0.42]
// Starts with North America facing the viewer.
const START_PHI = Math.PI - ((-95 * Math.PI) / 180 - Math.PI / 2)

// The contiguous US, where every route in the data lies.
const US_CENTRE: [number, number] = [39, -97]

type Orbit = { rx: number; ry: number; tilt: number; period: number; planes: number[] }

/**
 * Orbits are ellipses around the centre. rx is a fraction of the box width
 * and ry of its height, so the same numbers fit a square box or a wide band.
 * `tilt` turns the ellipse; `period` is seconds per lap.
 */
const SQUARE_ORBITS: Orbit[] = [
  { rx: 0.47, ry: 0.12, tilt: -14, period: 22, planes: [0, 0.5] },
  { rx: 0.43, ry: 0.17, tilt: 24, period: 30, planes: [0.2] },
  { rx: 0.49, ry: 0.08, tilt: 5, period: 38, planes: [0.65, 0.9] },
]
const WIDE_ORBITS: Orbit[] = [
  { rx: 0.44, ry: 0.3, tilt: -4, period: 26, planes: [0, 0.5] },
  { rx: 0.33, ry: 0.44, tilt: 6, period: 34, planes: [0.2, 0.7] },
  { rx: 0.48, ry: 0.16, tilt: 2, period: 42, planes: [0.4, 0.9] },
]

const planesOf = (orbits: Orbit[]) => orbits.flatMap((orbit, o) => orbit.planes.map((phase) => ({ orbit: o, phase })))

function halfEllipse(rx: number, ry: number, front: boolean) {
  const x0 = 50 - rx * 100
  const x1 = 50 + rx * 100
  return front
    ? `M ${x1} 50 A ${rx * 100} ${ry * 100} 0 0 1 ${x0} 50`
    : `M ${x0} 50 A ${rx * 100} ${ry * 100} 0 0 1 ${x1} 50`
}

function OrbitLines({ front, orbits }: { front: boolean; orbits: Orbit[] }) {
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden
      className="pointer-events-none absolute inset-0 size-full overflow-visible"
      style={{ zIndex: front ? 2 : 0 }}
    >
      {orbits.map((o, i) => (
        <path
          key={i}
          d={halfEllipse(o.rx, o.ry, front)}
          transform={`rotate(${o.tilt} 50 50)`}
          fill="none"
          stroke="currentColor"
          strokeWidth={1}
          strokeDasharray="2 6"
          vectorEffect="non-scaling-stroke"
          className={front ? "text-primary/45" : "text-primary/20"}
        />
      ))}
    </svg>
  )
}

/**
 * The landing globe with small airliners circling it on tilted orbits. Routes
 * are drawn as arcs; the active one is lit and turned to face the viewer.
 * `wide` lays it out as a band, with the globe filling the height. `framed`
 * holds the globe on the US instead of spinning, since every route is there.
 */
export function OrbitingGlobe({
  routes,
  activeId = null,
  wide = false,
  framed = false,
  className = "",
}: {
  routes: GlobeRoute[]
  activeId?: string | null
  wide?: boolean
  framed?: boolean
  className?: string
}) {
  const orbits = wide ? WIDE_ORBITS : SQUARE_ORBITS
  const planes = useMemo(() => planesOf(orbits), [orbits])
  const active = routes.find((r) => r.id === activeId)
  const focus = useMemo<[number, number] | null>(
    () =>
      active
        ? [(active.from[0] + active.to[0]) / 2, (active.from[1] + active.to[1]) / 2]
        : framed
          ? US_CENTRE
          : null,
    [active, framed],
  )
  // A dot at each end of every route.
  const markers = useMemo(() => {
    const seen = new Map<string, [number, number]>()
    for (const r of routes) {
      seen.set(r.from.join(","), r.from)
      seen.set(r.to.join(","), r.to)
    }
    return [...seen].map(([id, at], i) => ({ id: `m${i}`, location: at, label: id }))
  }, [routes])

  const boxRef = useRef<HTMLDivElement>(null)
  const planeRefs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    const box = boxRef.current
    if (!box) return
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    let w = box.offsetWidth
    let h = box.offsetHeight
    const ro = new ResizeObserver(([entry]) => {
      w = entry.contentRect.width
      h = entry.contentRect.height
    })
    ro.observe(box)

    let frame = 0
    const t0 = performance.now()

    function place(now: number) {
      const seconds = (now - t0) / 1000
      planes.forEach((p, i) => {
        const el = planeRefs.current[i]
        if (!el) return
        const o = orbits[p.orbit]
        const theta = 2 * Math.PI * (p.phase + (reduced ? 0 : seconds / o.period))
        const tilt = (o.tilt * Math.PI) / 180
        const cos = Math.cos(tilt)
        const sin = Math.sin(tilt)
        // Point on the ellipse in box fractions, turned by the tilt, then
        // stretched to the box, exactly as the SVG orbit lines are. y grows
        // downward, so the lower half (sin theta > 0) is nearer the viewer.
        const lx = o.rx * Math.cos(theta)
        const ly = o.ry * Math.sin(theta)
        const x = (lx * cos - ly * sin) * w
        const y = (lx * sin + ly * cos) * h
        const dx = -o.rx * Math.sin(theta)
        const dy = o.ry * Math.cos(theta)
        const heading = Math.atan2((dx * sin + dy * cos) * h, (dx * cos - dy * sin) * w)
        const depth = Math.sin(theta) // -1 far side, 1 near side
        const scale = 0.72 + 0.28 * ((depth + 1) / 2)
        el.style.transform = `translate(${x}px, ${y}px) rotate(${heading}rad) scale(${scale})`
        el.style.zIndex = depth > 0 ? "2" : "0"
        el.style.opacity = String(0.55 + 0.45 * ((depth + 1) / 2))
      })
      if (!reduced) frame = requestAnimationFrame(place)
    }
    frame = requestAnimationFrame(place)

    return () => {
      cancelAnimationFrame(frame)
      ro.disconnect()
    }
  }, [orbits, planes])

  return (
    <div ref={boxRef} className={`relative isolate w-full ${wide ? "" : "aspect-square"} ${className}`}>
      <div
        className="pointer-events-none absolute top-1/2 left-1/2 aspect-square h-[90%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,color-mix(in_oklch,var(--primary)_16%,transparent)_30%,transparent_70%)] blur-2xl"
      />
      <OrbitLines front={false} orbits={orbits} />
      {/* The globe: 72% of a square box, or 84% of a band's height. */}
      <div
        className="absolute top-1/2 left-1/2 z-[1] aspect-square -translate-x-1/2 -translate-y-1/2"
        style={{ height: wide ? "84%" : "72%" }}
      >
        <Globe
          markers={markers}
          showLabels={false}
          arcs={routes}
          highlightArc={active ? active.id : null}
          highlightColor={BEACON}
          focus={focus}
          focusScale={active ? 2.4 : 1.7}
          className="h-full"
          dark={1}
          diffuse={1.2}
          mapSamples={20000}
          mapBrightness={7}
          baseColor={NIGHT_BASE}
          markerColor={BEACON}
          arcColor={SKY}
          glowColor={HALO}
          markerSize={0.02}
          arcHeight={0.2}
          arcWidth={0.6}
          phi={START_PHI}
          theta={0.3}
          speed={0.0025}
        />
      </div>
      {planes.map((p, i) => (
        <div
          key={`${p.orbit}-${p.phase}`}
          ref={(el) => {
            planeRefs.current[i] = el
          }}
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-1/2 -mt-3 -ml-3 size-6 text-beacon will-change-transform"
        >
          <Airliner className="size-full drop-shadow-[0_0_6px_color-mix(in_oklch,var(--beacon)_60%,transparent)]" />
        </div>
      ))}
      <OrbitLines front orbits={orbits} />
    </div>
  )
}
