"use client"

import { useEffect, useMemo, useRef } from "react"
import { Globe } from "@/components/ui/cobe-globe"
import { Airliner } from "@/components/landing/airliner"
import { VisualBoundary, VisualFallback } from "@/components/dashboard/visual-boundary"
import { useWebGL } from "@/hooks/use-webgl"

export interface GlobeRoute {
  id: string
  from: [number, number]
  to: [number, number]
}

const NIGHT_BASE: [number, number, number] = [0.24, 0.24, 0.24]
const ROUTE: [number, number, number] = [0.85, 0.55, 0.7]
const BEACON: [number, number, number] = [1, 0.24, 0.62]
const HALO: [number, number, number] = [0.22, 0.08, 0.15]
// Starts with North America facing the viewer.
const START_PHI = Math.PI - ((-95 * Math.PI) / 180 - Math.PI / 2)

// The contiguous US, where every route in the data lies.
const US_CENTRE: [number, number] = [39, -97]

type Layout = "square" | "horizon"

/**
 * Orbits are ellipses centred at (cx, cy). Every value is a fraction of the
 * box: x values of its width, y values of its height, so the same numbers
 * suit any size. `tilt` turns the ellipse; `period` is seconds per lap.
 */
type Orbit = { cx: number; cy: number; rx: number; ry: number; tilt: number; period: number; planes: number[] }

const ORBITS: Record<Layout, Orbit[]> = {
  square: [
    { cx: 0.5, cy: 0.5, rx: 0.47, ry: 0.12, tilt: -14, period: 22, planes: [0, 0.5] },
    { cx: 0.5, cy: 0.5, rx: 0.43, ry: 0.17, tilt: 24, period: 30, planes: [0.2] },
    { cx: 0.5, cy: 0.5, rx: 0.49, ry: 0.08, tilt: 5, period: 38, planes: [0.65, 0.9] },
  ],
  // Wide, flat orbits over the curve of the globe: the far half crosses the
  // sky above it, the near half sweeps across its face.
  horizon: [
    { cx: 0.5, cy: 0.6, rx: 0.47, ry: 0.34, tilt: -3, period: 32, planes: [0, 0.5] },
    { cx: 0.5, cy: 0.66, rx: 0.36, ry: 0.46, tilt: 4, period: 44, planes: [0.25, 0.75] },
    { cx: 0.5, cy: 0.56, rx: 0.49, ry: 0.18, tilt: 1, period: 52, planes: [0.1, 0.6] },
  ],
}

const planesOf = (orbits: Orbit[]) => orbits.flatMap((orbit, o) => orbit.planes.map((phase) => ({ orbit: o, phase })))

function halfEllipse(o: Orbit, front: boolean) {
  const cx = o.cx * 100
  const cy = o.cy * 100
  const x0 = cx - o.rx * 100
  const x1 = cx + o.rx * 100
  const r = `${o.rx * 100} ${o.ry * 100}`
  return front ? `M ${x1} ${cy} A ${r} 0 0 1 ${x0} ${cy}` : `M ${x0} ${cy} A ${r} 0 0 1 ${x1} ${cy}`
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
          d={halfEllipse(o, front)}
          transform={`rotate(${o.tilt} ${o.cx * 100} ${o.cy * 100})`}
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
 * A spinning globe with small airliners circling it on tilted orbits. Routes
 * are drawn as arcs; the active one is lit and turned to face the viewer.
 * `horizon` makes the globe far wider than the box so only its top curve
 * shows, fading into the page. `framed` holds it on the US instead of
 * spinning.
 */
export function OrbitingGlobe({
  routes,
  activeId = null,
  layout = "square",
  framed = false,
  className = "",
}: {
  routes: GlobeRoute[]
  activeId?: string | null
  layout?: Layout
  framed?: boolean
  className?: string
}) {
  const webgl = useWebGL()
  const horizon = layout === "horizon"
  const orbits = ORBITS[layout]
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
        const x = (o.cx + lx * cos - ly * sin) * w
        const y = (o.cy + lx * sin + ly * cos) * h
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
    <div
      ref={boxRef}
      className={`relative isolate w-full ${horizon ? "overflow-hidden" : "aspect-square"} ${className}`}
    >
      {horizon ? (
        <div className="pointer-events-none absolute top-[4%] left-1/2 h-[70%] w-[80%] -translate-x-1/2 rounded-[50%] bg-[radial-gradient(ellipse_at_50%_60%,color-mix(in_oklch,var(--primary)_22%,transparent),transparent_65%)] blur-3xl" />
      ) : (
        <div className="pointer-events-none absolute top-1/2 left-1/2 aspect-square h-[90%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,color-mix(in_oklch,var(--primary)_16%,transparent)_30%,transparent_70%)] blur-2xl" />
      )}
      <OrbitLines front={false} orbits={orbits} />
      {/* The globe: 72% of a square box; on the horizon, 86% of the box's
          width with only its top curve inside the box. */}
      <div
        className={
          horizon
            ? "absolute top-[16%] left-1/2 z-[1] aspect-square w-[86%] -translate-x-1/2"
            : "absolute top-1/2 left-1/2 z-[1] aspect-square h-[72%] -translate-x-1/2 -translate-y-1/2"
        }
      >
        {!webgl ? (
          <VisualFallback label="Globe" className="rounded-full" />
        ) : (
        <VisualBoundary label="Globe" className="rounded-full">
        <Globe
          markers={markers}
          showLabels={false}
          arcs={routes}
          highlightArc={active ? active.id : null}
          highlightColor={BEACON}
          focus={focus}
          focusScale={horizon ? (active ? 1.6 : 1.15) : active ? 2.4 : 1.7}
          // On the horizon only the top of the globe shows, so a focused
          // place is tilted up into that part instead of the centre.
          focusLift={horizon ? 0.55 : 0}
          className={horizon ? "w-full" : "h-full"}
          dark={1}
          diffuse={1.2}
          mapSamples={horizon ? 40000 : 20000}
          mapBrightness={7}
          baseColor={NIGHT_BASE}
          markerColor={BEACON}
          arcColor={ROUTE}
          glowColor={HALO}
          markerSize={horizon ? 0.012 : 0.02}
          arcHeight={0.2}
          arcWidth={horizon ? 0.4 : 0.6}
          phi={START_PHI}
          theta={horizon ? 0.12 : 0.3}
          speed={horizon ? 0.0016 : 0.0025}
        />
        </VisualBoundary>
        )}
      </div>
      {planes.map((p, i) => (
        <div
          key={`${p.orbit}-${p.phase}`}
          ref={(el) => {
            planeRefs.current[i] = el
          }}
          aria-hidden
          className="pointer-events-none absolute top-0 left-0 -mt-3 -ml-3 size-6 text-beacon will-change-transform"
        >
          <Airliner className="size-full drop-shadow-[0_0_6px_color-mix(in_oklch,var(--beacon)_60%,transparent)]" />
        </div>
      ))}
      <OrbitLines front orbits={orbits} />
      {horizon && (
        // Fade the globe's lower edge into the page.
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[3] h-2/5 bg-gradient-to-t from-background via-background/70 to-transparent" />
      )}
    </div>
  )
}
