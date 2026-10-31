"use client"

import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { Airliner } from "@/components/landing/airliner"

const SEEN_KEY = "arrival-recovery:intro-seen"
const FLIGHT_MS = 2200
const FADE_MS = 500

function alreadySeen(): boolean {
  try {
    return sessionStorage.getItem(SEEN_KEY) === "1"
  } catch {
    return false
  }
}

function markSeen() {
  try {
    sessionStorage.setItem(SEEN_KEY, "1")
  } catch {
    // Storage can be blocked; the intro then plays on every visit.
  }
}

/**
 * Opening shot: an airliner crosses the screen from bottom left to top right,
 * drawing a contrail, then the cover fades to reveal the home page beneath.
 * Plays once per browser tab, never with reduced motion, and any click or key
 * skips it.
 */
export function FlyIn() {
  const [phase, setPhase] = useState<"flying" | "leaving" | "gone">("flying")
  const decision = useRef<"play" | "skip" | null>(null)
  const coverRef = useRef<HTMLDivElement>(null)
  const planeRef = useRef<HTMLDivElement>(null)
  const trailRef = useRef<HTMLDivElement>(null)

  // A layout effect, so a skipped cover is hidden before the browser paints:
  // coming back to the overview from another page must not flash it.
  useLayoutEffect(() => {
    // Decide once per mount: React runs effects twice in development, and the
    // second run would otherwise find the flag the first one just set.
    if (decision.current === null) {
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      decision.current = reduced || alreadySeen() ? "skip" : "play"
      if (decision.current === "play") markSeen()
    }
    if (decision.current === "skip") {
      // Hide the cover at once, then unmount it on the next frame.
      if (coverRef.current) coverRef.current.style.display = "none"
      const id = requestAnimationFrame(() => setPhase("gone"))
      return () => cancelAnimationFrame(id)
    }

    const w = window.innerWidth
    const h = window.innerHeight
    const from = { x: -0.12 * w, y: 1.12 * h }
    const to = { x: 1.12 * w, y: -0.12 * h }
    const angle = Math.atan2(to.y - from.y, to.x - from.x)
    const length = Math.hypot(to.x - from.x, to.y - from.y)
    const timing = { duration: FLIGHT_MS, easing: "cubic-bezier(0.35, 0, 0.65, 1)", fill: "forwards" } as const

    const animations: Animation[] = []
    if (planeRef.current) {
      animations.push(
        planeRef.current.animate(
          [
            { transform: `translate(${from.x}px, ${from.y}px) rotate(${angle}rad) scale(0.8)` },
            { transform: `translate(${to.x}px, ${to.y}px) rotate(${angle}rad) scale(1.15)` },
          ],
          timing,
        ),
      )
    }
    if (trailRef.current) {
      trailRef.current.style.width = `${length}px`
      // The trail grows with the same timing as the plane, so its tip stays
      // under the aircraft; it fades on a separate animation.
      animations.push(
        trailRef.current.animate(
          [
            { transform: `translate(${from.x}px, ${from.y}px) rotate(${angle}rad) scaleX(0)` },
            { transform: `translate(${from.x}px, ${from.y}px) rotate(${angle}rad) scaleX(1)` },
          ],
          timing,
        ),
        trailRef.current.animate([{ opacity: 1 }, { opacity: 1, offset: 0.7 }, { opacity: 0.4 }], {
          duration: FLIGHT_MS,
          fill: "forwards",
        }),
      )
    }

    const leave = window.setTimeout(() => setPhase("leaving"), FLIGHT_MS - 250)
    return () => {
      window.clearTimeout(leave)
      animations.forEach((a) => a.cancel())
    }
  }, [])

  useEffect(() => {
    if (phase !== "leaving") return
    const done = window.setTimeout(() => setPhase("gone"), FADE_MS)
    return () => window.clearTimeout(done)
  }, [phase])

  useEffect(() => {
    if (phase !== "flying") return
    const skip = () => setPhase("leaving")
    window.addEventListener("keydown", skip)
    return () => window.removeEventListener("keydown", skip)
  }, [phase])

  if (phase === "gone") return null

  return (
    <div
      ref={coverRef}
      aria-hidden
      onClick={() => setPhase("leaving")}
      className="fixed inset-0 z-50 overflow-hidden bg-background transition-opacity ease-out motion-reduce:hidden"
      style={{ opacity: phase === "leaving" ? 0 : 1, transitionDuration: `${FADE_MS}ms` }}
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_30%,color-mix(in_oklch,var(--primary)_14%,transparent),transparent_60%)]" />
      <div
        ref={trailRef}
        className="absolute top-0 left-0 h-[3px] origin-left -translate-y-1/2 rounded-full bg-gradient-to-r from-transparent via-foreground/25 to-foreground/80 blur-[0.5px]"
        style={{ transform: "scaleX(0)" }}
      />
      <div ref={planeRef} className="absolute top-0 left-0" style={{ transform: "translate(-200px, -200px)" }}>
        <Airliner className="size-[clamp(4.5rem,9vw,8rem)] -translate-x-1/2 -translate-y-1/2 text-foreground drop-shadow-[0_0_18px_color-mix(in_oklch,var(--beacon)_45%,transparent)]" />
      </div>
    </div>
  )
}
