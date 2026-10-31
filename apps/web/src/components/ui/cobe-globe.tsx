"use client"

import { useEffect, useRef, useCallback } from "react"
import createGlobe from "cobe"

type RGB = [number, number, number]

interface Marker {
  id: string
  location: [number, number]
  label: string
}

interface Arc {
  id: string
  from: [number, number]
  to: [number, number]
  label?: string
}

interface GlobeProps {
  markers?: Marker[]
  arcs?: Arc[]
  className?: string
  markerColor?: RGB
  baseColor?: RGB
  arcColor?: RGB
  glowColor?: RGB
  dark?: number
  mapBrightness?: number
  markerSize?: number
  markerElevation?: number
  arcWidth?: number
  arcHeight?: number
  speed?: number
  phi?: number
  theta?: number
  diffuse?: number
  mapSamples?: number
  showLabels?: boolean
  /** Arc drawn in `highlightColor`; the others dim. */
  highlightArc?: string | null
  highlightColor?: RGB
  /** [lat, lon] to turn towards. Spinning stops while it is set. */
  focus?: [number, number] | null
  /** Zoom applied while `focus` is set. */
  focusScale?: number
  /** Radians to tilt a focused place up from the centre, for a cropped view. */
  focusLift?: number
}

const tagStyle = {
  position: "absolute",
  bottom: "anchor(top)",
  left: "anchor(center)",
  translate: "-50% 0",
  marginBottom: 8,
  padding: "2px 6px",
  borderRadius: 4,
  fontSize: "0.65rem",
  whiteSpace: "nowrap",
  pointerEvents: "none",
  transition: "opacity 0.8s, filter 0.8s",
} as const

const dim = (c: RGB): RGB => [c[0] * 0.45, c[1] * 0.45, c[2] * 0.45]

/** Shortest signed difference between two angles, in radians. */
function angleDelta(from: number, to: number) {
  const d = (to - from) % (2 * Math.PI)
  return d > Math.PI ? d - 2 * Math.PI : d < -Math.PI ? d + 2 * Math.PI : d
}

// Adapted from a cobe v2 example: labels use theme tokens, markers and arcs
// update without rebuilding the globe, one arc can be highlighted, the globe
// can turn to a location, and spinning stops for people who ask for reduced
// motion.
export function Globe({
  markers = [],
  arcs = [],
  className = "",
  markerColor = [0.3, 0.45, 0.85],
  baseColor = [1, 1, 1],
  arcColor = [0.3, 0.45, 0.85],
  glowColor = [0.94, 0.93, 0.91],
  dark = 0,
  mapBrightness = 10,
  markerSize = 0.025,
  markerElevation = 0.01,
  arcWidth = 0.5,
  arcHeight = 0.25,
  speed = 0.003,
  phi: startPhi = 0,
  theta = 0.2,
  diffuse = 1.5,
  mapSamples = 16000,
  showLabels = true,
  highlightArc = null,
  highlightColor = [0.72, 0.6, 1],
  focus = null,
  focusScale = 1,
  focusLift = 0,
}: GlobeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pointerInteracting = useRef<{ x: number; y: number } | null>(null)
  const lastPointer = useRef<{ x: number; y: number; t: number } | null>(null)
  const dragOffset = useRef({ phi: 0, theta: 0 })
  const velocity = useRef({ phi: 0, theta: 0 })
  const phiOffsetRef = useRef(0)
  const thetaOffsetRef = useRef(0)
  const isPausedRef = useRef(false)

  // Read by the render loop, so changing them never rebuilds the globe.
  const focusRef = useRef(focus)
  const focusScaleRef = useRef(focusScale)
  const focusLiftRef = useRef(focusLift)
  const shapesRef = useRef<{ markers: ReturnType<typeof toMarkers>; arcs: ReturnType<typeof toArcs> } | null>(null)

  function toMarkers() {
    return markers.map((m) => ({ location: m.location, size: markerSize, id: m.id }))
  }
  function toArcs() {
    return arcs.map((a) => ({
      from: a.from,
      to: a.to,
      id: a.id,
      color: highlightArc === null ? arcColor : a.id === highlightArc ? highlightColor : dim(arcColor),
    }))
  }

  useEffect(() => {
    focusRef.current = focus
    focusScaleRef.current = focusScale
    focusLiftRef.current = focusLift
  }, [focus, focusScale, focusLift])

  useEffect(() => {
    shapesRef.current = { markers: toMarkers(), arcs: toArcs() }
    // toMarkers and toArcs only read the props listed here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markers, arcs, markerSize, highlightArc, arcColor, highlightColor])

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    pointerInteracting.current = { x: e.clientX, y: e.clientY }
    if (canvasRef.current) canvasRef.current.style.cursor = "grabbing"
    isPausedRef.current = true
  }, [])

  const handlePointerMove = useCallback((e: PointerEvent) => {
    if (pointerInteracting.current !== null) {
      const deltaX = e.clientX - pointerInteracting.current.x
      const deltaY = e.clientY - pointerInteracting.current.y
      dragOffset.current = { phi: deltaX / 300, theta: deltaY / 1000 }
      const now = Date.now()
      if (lastPointer.current) {
        const dt = Math.max(now - lastPointer.current.t, 1)
        const maxVelocity = 0.15
        velocity.current = {
          phi: Math.max(-maxVelocity, Math.min(maxVelocity, ((e.clientX - lastPointer.current.x) / dt) * 0.3)),
          theta: Math.max(-maxVelocity, Math.min(maxVelocity, ((e.clientY - lastPointer.current.y) / dt) * 0.08)),
        }
      }
      lastPointer.current = { x: e.clientX, y: e.clientY, t: now }
    }
  }, [])

  const handlePointerUp = useCallback(() => {
    if (pointerInteracting.current !== null) {
      phiOffsetRef.current += dragOffset.current.phi
      thetaOffsetRef.current += dragOffset.current.theta
      dragOffset.current = { phi: 0, theta: 0 }
      lastPointer.current = null
    }
    pointerInteracting.current = null
    if (canvasRef.current) canvasRef.current.style.cursor = "grab"
    isPausedRef.current = false
  }, [])

  useEffect(() => {
    window.addEventListener("pointermove", handlePointerMove, { passive: true })
    window.addEventListener("pointerup", handlePointerUp, { passive: true })
    return () => {
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup", handlePointerUp)
    }
  }, [handlePointerMove, handlePointerUp])

  useEffect(() => {
    if (!canvasRef.current) return
    const canvas = canvasRef.current
    let globe: ReturnType<typeof createGlobe> | null = null
    let animationId = 0
    let ro: ResizeObserver | null = null
    let phi = startPhi
    let scale = 1
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const spin = reduced ? 0 : speed
    let drawn: typeof shapesRef.current = null

    function init() {
      const width = canvas.offsetWidth
      if (width === 0 || globe) return

      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      drawn = shapesRef.current
      const g = createGlobe(canvas, {
        devicePixelRatio: dpr,
        width,
        height: width,
        phi,
        theta,
        dark,
        diffuse,
        mapSamples,
        mapBrightness,
        baseColor,
        markerColor,
        glowColor,
        markerElevation,
        markers: drawn?.markers ?? [],
        arcs: drawn?.arcs ?? [],
        arcColor,
        arcWidth,
        arcHeight,
        opacity: 1,
      })
      globe = g

      function animate() {
        const target = focusRef.current
        if (target && !isPausedRef.current) {
          // Ease towards the location: phi turns its longitude to the front,
          // theta tilts its latitude towards the viewer.
          const goalPhi = Math.PI - ((target[1] * Math.PI) / 180 - Math.PI / 2)
          const goalTheta = (target[0] * Math.PI) / 180 - theta - focusLiftRef.current
          const ease = reduced ? 1 : 0.08
          phi += angleDelta(phi + phiOffsetRef.current, goalPhi) * ease
          thetaOffsetRef.current += (Math.max(-0.4, Math.min(0.4, goalTheta)) - thetaOffsetRef.current) * ease
          velocity.current = { phi: 0, theta: 0 }
        } else if (!isPausedRef.current) {
          phi += spin
          if (Math.abs(velocity.current.phi) > 0.0001 || Math.abs(velocity.current.theta) > 0.0001) {
            phiOffsetRef.current += velocity.current.phi
            thetaOffsetRef.current += velocity.current.theta
            velocity.current.phi *= 0.95
            velocity.current.theta *= 0.95
          }
          const thetaMin = -0.4
          const thetaMax = 0.4
          if (thetaOffsetRef.current < thetaMin) {
            thetaOffsetRef.current += (thetaMin - thetaOffsetRef.current) * 0.1
          } else if (thetaOffsetRef.current > thetaMax) {
            thetaOffsetRef.current += (thetaMax - thetaOffsetRef.current) * 0.1
          }
        }
        const goalScale = target ? focusScaleRef.current : 1
        scale += (goalScale - scale) * (reduced ? 1 : 0.08)
        const shapes = shapesRef.current
        const changed = shapes !== drawn
        drawn = shapes
        g.update({
          scale,
          phi: phi + phiOffsetRef.current + dragOffset.current.phi,
          theta: theta + thetaOffsetRef.current + dragOffset.current.theta,
          ...(changed && shapes ? { markers: shapes.markers, arcs: shapes.arcs } : {}),
        })
        animationId = requestAnimationFrame(animate)
      }
      animate()
      setTimeout(() => (canvas.style.opacity = "1"))
    }

    if (canvas.offsetWidth > 0) {
      init()
    } else {
      ro = new ResizeObserver((entries) => {
        if (entries[0]?.contentRect.width > 0) {
          ro?.disconnect()
          init()
        }
      })
      ro.observe(canvas)
    }

    return () => {
      ro?.disconnect()
      if (animationId) cancelAnimationFrame(animationId)
      if (globe) globe.destroy()
    }
  }, [markerColor, baseColor, arcColor, glowColor, dark, mapBrightness, markerElevation, arcWidth, arcHeight, speed, startPhi, theta, diffuse, mapSamples])

  return (
    <div className={`relative aspect-square select-none ${className}`}>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        aria-hidden
        style={{
          width: "100%",
          height: "100%",
          cursor: "grab",
          opacity: 0,
          transition: "opacity 1.2s ease",
          borderRadius: "50%",
          touchAction: "none",
        }}
      />
      {showLabels &&
        markers.map((m) => (
          <div
            key={m.id}
            className="bg-popover text-popover-foreground ring-1 ring-border"
            style={{
              ...tagStyle,
              positionAnchor: `--cobe-${m.id}`,
              opacity: `var(--cobe-visible-${m.id}, 0)`,
              filter: `blur(calc((1 - var(--cobe-visible-${m.id}, 0)) * 8px))`,
            }}
          >
            {m.label}
          </div>
        ))}
      {arcs
        .filter((a) => a.label)
        .map((a) => (
          <div
            key={a.id}
            className="bg-primary font-medium text-primary-foreground"
            style={{
              ...tagStyle,
              positionAnchor: `--cobe-arc-${a.id}`,
              opacity: `var(--cobe-visible-arc-${a.id}, 0)`,
              filter: `blur(calc((1 - var(--cobe-visible-arc-${a.id}, 0)) * 8px))`,
            }}
          >
            {a.label}
          </div>
        ))}
    </div>
  )
}
