"use client";

import type { KeyboardEvent } from "react";
import type { Run, RunOverrides } from "@/lib/api-types";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

/*
 * A schematic of the arrival airport, drawn in an 800 x 520 box and cropped
 * to the runways and gates. It sits as an inset over the flight map. It is a
 * diagram, not a chart: runways 27L and 27R land westbound, so arrivals come
 * in from the right. Only the runway and gate ids come from the API;
 * positions are fixed slots for the demo airport.
 */

const RUNWAY_Y: Record<string, number> = { "27L": 170, "27R": 250 };
const RUNWAY_X0 = 150;
const RUNWAY_X1 = 640;
const TAXI_Y = 320;
const GATE_X: Record<string, number> = { B12: 270, B14: 390, C3: 530 };
const GATE_Y = 372;

function fallbackY(i: number) {
  return 170 + i * 80;
}
function fallbackGateX(i: number) {
  return 270 + i * 130;
}

function routePath(runwayY: number, gateX: number) {
  return [
    "M700 92",
    `C790 104 800 ${runwayY} 770 ${runwayY}`,
    `L300 ${runwayY}`,
    `Q282 ${runwayY} 282 ${runwayY + 18}`,
    `L282 ${TAXI_Y - 12}`,
    `Q282 ${TAXI_Y} 294 ${TAXI_Y}`,
    `L${gateX - 12} ${TAXI_Y}`,
    `Q${gateX} ${TAXI_Y} ${gateX} ${TAXI_Y + 12}`,
    `L${gateX} ${GATE_Y + 6}`,
  ].join(" ");
}

function onActivate(fn: () => void) {
  return (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fn();
    }
  };
}

export function AirportMap({
  run,
  overrides,
  disabled,
  onRunway,
  onGate,
}: {
  run: Run | null;
  overrides: RunOverrides;
  disabled: boolean;
  onRunway: (id: string) => void;
  onGate: (id: string) => void;
}) {
  const moving = !useReducedMotion();

  const closedRunways = overrides.closed_runways ?? [];
  const closedGates = overrides.closed_gates ?? [];
  const runways = run?.airport?.runways ?? Object.keys(RUNWAY_Y).map((id) => ({ id, closed: closedRunways.includes(id) }));
  const gates = run?.airport?.gates ?? Object.keys(GATE_X).map((id) => ({ id, closed: closedGates.includes(id) }));
  const deal = run?.decision.kind === "DEAL" ? run.decision.package : null;
  const arrival = run?.card?.action_facts.find((f) => f.key === "arrival")?.value;
  const ry = (id: string, i: number) => RUNWAY_Y[id] ?? fallbackY(i);
  const gx = (id: string, i: number) => GATE_X[id] ?? fallbackGateX(i);
  const assignedY = deal ? ry(deal.runway_id, runways.findIndex((r) => r.id === deal.runway_id)) : null;
  const assignedX = deal ? gx(deal.gate_id, gates.findIndex((g) => g.id === deal.gate_id)) : null;

  return (
    <svg
      viewBox="130 140 610 300"
      role="group"
      aria-label="Arrival airport. Select a runway or gate to close it."
      className="size-full select-none"
    >
      <defs>
        <pattern id="closed-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="8" height="8" className="fill-destructive/25" />
          <line x1="0" y1="0" x2="0" y2="8" strokeWidth="4" className="stroke-destructive/70" />
        </pattern>
        <linearGradient id="approach-fade" x1="1" x2="0" y1="0" y2="0">
          <stop offset="0" stopColor="var(--beacon)" stopOpacity="0.15" />
          <stop offset="0.25" stopColor="var(--beacon)" stopOpacity="1" />
        </linearGradient>
      </defs>

      {/* Taxiway and exit links */}
      <g className="stroke-muted-foreground/25" fill="none" strokeWidth="6" strokeLinecap="round">
        <path d={`M${RUNWAY_X0} ${TAXI_Y} H${RUNWAY_X1}`} />
        <path d={`M282 ${RUNWAY_Y["27L"]} V${TAXI_Y}`} />
        <path d={`M470 ${RUNWAY_Y["27L"]} V${TAXI_Y}`} />
        {gates.map((g, i) => (
          <path key={g.id} d={`M${gx(g.id, i)} ${TAXI_Y} V${GATE_Y}`} />
        ))}
      </g>

      {/* Terminal */}
      <rect x="200" y="400" width="400" height="34" rx="6" className="fill-secondary stroke-border" />


      {/* Planned route */}
      {assignedY !== null && assignedX !== null && (
        <path
          d={routePath(assignedY, assignedX)}
          fill="none"
          stroke="url(#approach-fade)"
          strokeWidth="2.5"
          strokeDasharray="6 5"
          strokeLinecap="round"
        >
          {moving && <animate attributeName="stroke-dashoffset" from="22" to="0" dur="1.2s" repeatCount="indefinite" />}
        </path>
      )}

      {/* Runways */}
      {runways.map((r, i) => {
        const y = ry(r.id, i);
        const assigned = deal?.runway_id === r.id;
        const toggle = () => !disabled && onRunway(r.id);
        return (
          <g
            key={r.id}
            role="button"
            tabIndex={disabled ? -1 : 0}
            aria-pressed={r.closed}
            aria-disabled={disabled}
            aria-label={`Runway ${r.id}, ${r.closed ? "closed" : "open"}${assigned ? ", assigned" : ""}. ${r.closed ? "Reopen" : "Close"} it.`}
            onClick={toggle}
            onKeyDown={onActivate(toggle)}
            className={cn("group outline-none", disabled ? "cursor-not-allowed" : "cursor-pointer")}
          >
            <rect x={RUNWAY_X0 - 6} y={y - 18} width={RUNWAY_X1 - RUNWAY_X0 + 12} height={36} fill="transparent" />
            <rect
              x={RUNWAY_X0}
              y={y - 9}
              width={RUNWAY_X1 - RUNWAY_X0}
              height={18}
              rx="3"
              className={cn(
                "transition-colors",
                r.closed ? "fill-[url(#closed-hatch)]" : "fill-[oklch(0.3_0.03_262)] group-hover:fill-[oklch(0.35_0.035_262)]",
                assigned && !r.closed && "stroke-beacon",
                "group-focus-visible:stroke-ring",
              )}
              strokeWidth={assigned || r.closed ? 1.5 : 0}
            />
            {!r.closed && (
              <line
                x1={RUNWAY_X0 + 24}
                x2={RUNWAY_X1 - 24}
                y1={y}
                y2={y}
                strokeDasharray="14 10"
                strokeWidth="1.5"
                className="stroke-foreground/35"
              />
            )}
            <text
              x={RUNWAY_X1 + 14}
              y={y + 6}
              className={cn(
                "font-display text-[18px] font-semibold",
                r.closed ? "fill-destructive" : assigned ? "fill-beacon" : "fill-muted-foreground",
              )}
            >
              {r.id}
            </text>
            {assigned && arrival && !r.closed && (
              <text x={RUNWAY_X1 + 14} y={y + 24} className="fill-foreground font-display text-[13px] tabular-nums">
                {arrival}
              </text>
            )}
          </g>
        );
      })}

      {/* Gates */}
      {gates.map((g, i) => {
        const x = gx(g.id, i);
        const assigned = deal?.gate_id === g.id;
        const toggle = () => !disabled && onGate(g.id);
        return (
          <g
            key={g.id}
            role="button"
            tabIndex={disabled ? -1 : 0}
            aria-pressed={g.closed}
            aria-disabled={disabled}
            aria-label={`Gate ${g.id}, ${g.closed ? "blocked" : "free"}${assigned ? ", assigned" : ""}. ${g.closed ? "Free" : "Block"} it.`}
            onClick={toggle}
            onKeyDown={onActivate(toggle)}
            className={cn("group outline-none", disabled ? "cursor-not-allowed" : "cursor-pointer")}
          >
            <rect
              x={x - 22}
              y={GATE_Y - 4}
              width={44}
              height={28}
              rx="4"
              strokeWidth="1.5"
              className={cn(
                "transition-colors group-focus-visible:stroke-ring",
                g.closed
                  ? "fill-[url(#closed-hatch)] stroke-destructive"
                  : assigned
                    ? "fill-beacon/20 stroke-beacon"
                    : "fill-card stroke-border group-hover:fill-accent",
              )}
            />
            <text
              x={x}
              y={GATE_Y + 15}
              textAnchor="middle"
              className={cn(
                "font-display text-[15px] font-semibold",
                g.closed ? "fill-destructive" : assigned ? "fill-beacon" : "fill-muted-foreground",
              )}
            >
              {g.id}
            </text>
          </g>
        );
      })}

    </svg>
  );
}
