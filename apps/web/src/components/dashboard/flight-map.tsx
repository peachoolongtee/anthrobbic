"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState, type RefObject } from "react";
import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import type { ScenarioSummary } from "@/lib/api-types";
import { AIRPORTS, routeCodes } from "@/lib/airports";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { cn } from "@/lib/utils";

/*
 * The dashboard's backdrop: a dark basemap of the US with every delayed
 * flight's route, the selected one lit in amber, and its aircraft circling a
 * hold on its way in, short of the destination. Tiles come from CARTO's free
 * Dark Matter style, so the map needs a network connection; without one the
 * dotted backdrop underneath stays visible and nothing else on the dashboard
 * changes.
 */

const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const NIGHT = "#111215";
const DEEP_WATER = "#0a0a0d";
const BEACON = "#a48bfa";
const ROUTE_DIM = "rgba(180, 180, 200, 0.28)";

type LngLat = [number, number];

/** Airport [lat, lon] to MapLibre [lon, lat]. */
function lngLat(code: string): LngLat | null {
  const at = AIRPORTS[code];
  return at ? [at[1], at[0]] : null;
}

/** Points along the great circle between two places, for a curved route. */
function greatCircle(a: LngLat, b: LngLat, steps = 64): LngLat[] {
  const rad = Math.PI / 180;
  const [l1, p1] = [a[0] * rad, a[1] * rad];
  const [l2, p2] = [b[0] * rad, b[1] * rad];
  const d =
    2 * Math.asin(Math.sqrt(Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin((l2 - l1) / 2) ** 2));
  if (d === 0) return [a, b];
  const out: LngLat[] = [];
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(p1) * Math.cos(l1) + B * Math.cos(p2) * Math.cos(l2);
    const y = A * Math.cos(p1) * Math.sin(l1) + B * Math.cos(p2) * Math.sin(l2);
    const z = A * Math.sin(p1) + B * Math.sin(p2);
    out.push([Math.atan2(y, x) / rad, Math.atan2(z, Math.hypot(x, y)) / rad]);
  }
  return out;
}

/**
 * Where the aircraft holds: the point on its route roughly half a degree
 * before the destination, so the hold sits on the way in. Returns the index
 * into the route.
 */
function holdIndex(route: LngLat[]): number {
  const end = route[route.length - 1];
  for (let i = route.length - 1; i > 0; i--) {
    const [lon, lat] = route[i];
    const dLon = (lon - end[0]) * Math.cos((lat * Math.PI) / 180);
    if (Math.hypot(dLon, lat - end[1]) >= 0.5) return i;
  }
  return 0;
}

/** A racetrack hold around a fix, its long side along the inbound track. */
function holdRing(fix: LngLat, track: number, steps = 72): LngLat[] {
  const [lon, lat] = fix;
  const k = 1 / Math.cos((lat * Math.PI) / 180);
  const rad = (track * Math.PI) / 180;
  // Along-track unit in [east, north] degrees, then the cross-track unit.
  const along: LngLat = [Math.sin(rad), Math.cos(rad)];
  const across: LngLat = [Math.cos(rad), -Math.sin(rad)];
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = (i / steps) * 2 * Math.PI;
    const a = 0.14 * Math.cos(t);
    const c = 0.05 * Math.sin(t);
    return [lon + (a * along[0] + c * across[0]) * k, lat + a * along[1] + c * across[1]] as LngLat;
  });
}

function bearing(a: LngLat, b: LngLat) {
  const rad = Math.PI / 180;
  const y = Math.sin((b[0] - a[0]) * rad) * Math.cos(b[1] * rad);
  const x =
    Math.cos(a[1] * rad) * Math.sin(b[1] * rad) - Math.sin(a[1] * rad) * Math.cos(b[1] * rad) * Math.cos((b[0] - a[0]) * rad);
  return Math.atan2(y, x) / rad;
}

function line(coords: LngLat[]) {
  return { type: "Feature" as const, properties: {}, geometry: { type: "LineString" as const, coordinates: coords } };
}

function collection(features: ReturnType<typeof line>[]) {
  return { type: "FeatureCollection" as const, features };
}

/** Origin in white, destination in amber with a halo, others muted. */
function airportLabel(code: string, role: "from" | "to" | "other") {
  const el = document.createElement("div");
  el.className = cn(
    "flex items-center gap-1.5 font-display text-sm font-semibold pointer-events-none",
    role === "to" ? "text-[var(--beacon)]" : role === "from" ? "text-foreground" : "text-muted-foreground",
  );
  const dot =
    role === "to"
      ? "bg-[var(--beacon)] shadow-[0_0_0_4px_color-mix(in_oklch,var(--beacon)_25%,transparent)]"
      : role === "from"
        ? "bg-foreground"
        : "bg-muted-foreground";
  el.innerHTML = `<span class="size-2 rounded-full ${dot}"></span>${code}`;
  return el;
}

const PLANE_SVG = `<svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" style="filter:drop-shadow(0 0 6px color-mix(in oklch, var(--beacon) 60%, transparent))"><g transform="rotate(90 12 12)"><path d="M12 1.2c.85 0 1.35 1.3 1.35 2.8v16.6c0 .9-.6 1.8-1.35 1.8s-1.35-.9-1.35-1.8V4c0-1.5.5-2.8 1.35-2.8z"/><path d="M12.9 8.6 22.6 13.4v1.5l-9.7-2.3zM11.1 8.6 1.4 13.4v1.5l9.7-2.3z"/><path d="M12.6 18.4 16.8 20.6v1.1l-4.2-.9zM11.4 18.4 7.2 20.6v1.1l4.2-.9z"/></g></svg>`;

/** Padding that leaves only the frame's rectangle for the route. */
function framePadding(map: HTMLElement, frame: HTMLElement | null) {
  const m = map.getBoundingClientRect();
  const f = frame?.getBoundingClientRect();
  const edge = 32;
  if (!f || f.width < 120 || f.height < 120) return { top: edge, right: edge, bottom: edge, left: edge };
  return {
    top: Math.max(edge, f.top - m.top + edge),
    left: Math.max(edge, f.left - m.left + edge),
    right: Math.max(edge, m.right - f.right + edge),
    bottom: Math.max(edge, m.bottom - f.bottom + edge),
  };
}

export function FlightMap({
  flights,
  selected,
  frame: frameRef,
  className,
}: {
  flights: ScenarioSummary[];
  selected: ScenarioSummary | undefined;
  /**
   * The clear part of the screen, between the panels. The route is framed
   * inside it; without one, or when it is hidden, the whole map is used.
   */
  frame?: RefObject<HTMLElement | null>;
  className?: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const reduced = useReducedMotion();

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;
    void import("maplibre-gl").then(({ Map, setWorkerUrl }) => {
      if (cancelled || !box.current) return;
      // Served from public/; see scripts/copy-maplibre-worker.mjs.
      setWorkerUrl("/maplibre-gl-worker.mjs");
      map = new Map({
        container: box.current,
        style: STYLE_URL,
        center: [-95, 38],
        zoom: 3.4,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
      });
      mapRef.current = map;
      map.once("style.load", () => {
        if (!map) return;
        try {
          map.setPaintProperty("background", "background-color", NIGHT);
          map.setPaintProperty("water", "fill-color", DEEP_WATER);
          // Quieter place names, so the routes read first.
          for (const layer of map.getStyle().layers) {
            if (layer.type === "symbol") map.setPaintProperty(layer.id, "text-opacity", 0.45);
          }
        } catch {
          // The basemap changed its layer names; its own colours are fine.
        }
        map.addSource("routes", { type: "geojson", data: collection([]) });
        map.addSource("active", { type: "geojson", data: collection([]) });
        map.addSource("hold", { type: "geojson", data: collection([]) });
        map.addSource("final", { type: "geojson", data: collection([]) });
        map.addLayer({
          id: "routes",
          type: "line",
          source: "routes",
          paint: { "line-color": ROUTE_DIM, "line-width": 1.2, "line-dasharray": [2, 3] },
        });
        map.addLayer({
          id: "active-glow",
          type: "line",
          source: "active",
          paint: { "line-color": BEACON, "line-width": 10, "line-opacity": 0.12, "line-blur": 6 },
        });
        map.addLayer({
          id: "active",
          type: "line",
          source: "active",
          layout: { "line-cap": "round" },
          paint: { "line-color": BEACON, "line-width": 2.5 },
        });
        map.addLayer({
          id: "final",
          type: "line",
          source: "final",
          paint: { "line-color": BEACON, "line-width": 2, "line-opacity": 0.6, "line-dasharray": [2, 2] },
        });
        map.addLayer({
          id: "hold",
          type: "line",
          source: "hold",
          paint: { "line-color": BEACON, "line-width": 1.5, "line-opacity": 0.7, "line-dasharray": [1.5, 2] },
        });
        setReady(true);
      });
    });
    return () => {
      cancelled = true;
      markers.current.forEach((m) => m.remove());
      markers.current = [];
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  // Draw routes and frame the selected flight whenever the data changes.
  // Re-frame when the clear area changes size, such as a window resize.
  const [frameSize, setFrameSize] = useState("");
  useEffect(() => {
    const el = frameRef?.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setFrameSize(`${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`));
    ro.observe(el);
    return () => ro.disconnect();
  }, [frameRef]);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    let frame = 0;
    let cancelled = false;

    void import("maplibre-gl").then(({ Marker, LngLatBounds }) => {
      if (cancelled) return;
      markers.current.forEach((m) => m.remove());
      markers.current = [];

      const routes = flights
        .map((f) => routeCodes(f.route))
        .map((c) => (c ? [lngLat(c[0]), lngLat(c[1])] : [null, null]))
        .filter((p): p is [LngLat, LngLat] => p[0] !== null && p[1] !== null);
      (map.getSource("routes") as GeoJSONSource | undefined)?.setData(
        collection(routes.map(([a, b]) => line(greatCircle(a, b)))),
      );

      const codes = selected ? routeCodes(selected.route) : null;
      const from = codes ? lngLat(codes[0]) : null;
      const to = codes ? lngLat(codes[1]) : null;
      // Flown so far: origin to the hold. Still to fly: hold to destination.
      const full = from && to ? greatCircle(from, to) : [];
      const fixAt = full.length ? holdIndex(full) : 0;
      const active = full.slice(0, fixAt + 1);
      const final = full.slice(fixAt);
      const ring = full.length ? holdRing(full[fixAt], bearing(full[Math.max(fixAt - 1, 0)], full[fixAt])) : [];
      (map.getSource("active") as GeoJSONSource | undefined)?.setData(
        collection(active.length ? [line(active)] : []),
      );
      (map.getSource("final") as GeoJSONSource | undefined)?.setData(
        collection(final.length > 1 ? [line(final)] : []),
      );
      (map.getSource("hold") as GeoJSONSource | undefined)?.setData(
        collection(ring.length ? [line(ring)] : []),
      );

      // Airport labels: every endpoint, the selected pair highlighted.
      const seen = new Set<string>();
      for (const f of flights) {
        for (const code of routeCodes(f.route) ?? []) {
          const at = lngLat(code);
          if (!at || seen.has(code)) continue;
          seen.add(code);
          const role = codes?.[1] === code ? "to" : codes?.[0] === code ? "from" : "other";
          markers.current.push(new Marker({ element: airportLabel(code, role), anchor: "left", offset: [-4, 0] }).setLngLat(at).addTo(map));
        }
      }

      if (!from || !to) return;

      // The delayed aircraft, circling its hold.
      const plane = document.createElement("div");
      plane.style.color = BEACON;
      plane.innerHTML = PLANE_SVG;
      const marker = new Marker({ element: plane, rotationAlignment: "map" }).setLngLat(ring[0]).addTo(map);
      markers.current.push(marker);
      const n = ring.length;
      const place = (i: number) => {
        // The first frame's timestamp can precede t0, so wrap negatives too.
        const a = ring[((i % n) + n) % n];
        const b = ring[(((i + 1) % n) + n) % n];
        marker.setLngLat(a).setRotation(bearing(a, b) - 90);
      };
      if (reduced) {
        place(Math.floor(ring.length / 2));
      } else {
        const t0 = performance.now();
        const tick = (now: number) => {
          place(Math.floor(((now - t0) / 9000) * ring.length));
          frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
      }

      const bounds = new LngLatBounds(from, from);
      for (const p of [...full, ...ring]) bounds.extend(p);
      map.fitBounds(bounds, { padding: framePadding(map.getContainer(), frameRef?.current ?? null), maxZoom: 7, duration: reduced ? 0 : 1200 });
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [ready, flights, selected, frameRef, frameSize, reduced]);

  return (
    <div className={cn("overflow-hidden", className)}>
      <div
        aria-hidden
        className="absolute inset-0 opacity-60 [background-image:radial-gradient(color-mix(in_oklch,var(--foreground)_10%,transparent)_1px,transparent_1px)] [background-size:22px_22px]"
      />
      <div
        ref={box}
        role="img"
        aria-label={selected ? `Map of ${selected.flight_id}, ${selected.route}, holding near the destination` : "Map of delayed flights"}
        className={cn("absolute inset-0 transition-opacity duration-700", ready ? "opacity-100" : "opacity-0")}
      />
    </div>
  );
}
