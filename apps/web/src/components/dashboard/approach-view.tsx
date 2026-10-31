"use client";

import { useEffect, useRef, type RefObject } from "react";
import type { Run, RunOverrides, ScenarioSummary } from "@/lib/api-types";
import { planActionFromLabel, type FlightPlanAction } from "@/lib/plan-action";
import { routeCodes } from "@/lib/airports";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { landingFact } from "@/components/dashboard/plan-summary";

/*
 * The arrival airport's approach, drawn as point merge: arrivals fly a
 * sequencing arc until given a slot, then turn to the merge point and onto
 * final for a runway. The selected flight's plan sets its runway, how far it
 * flies along the arc, and whether it holds.
 *
 * What comes from the run: runway IDs, which are closed, the plan's runway,
 * landing time and action, and whether there is a plan at all. Everything
 * else is illustrative: the geometry, the other traffic and the sim clock.
 * The canvas says so.
 */

// The part of the world that is drawn, fitted into the clear area.
const VIEW = { x: 330, y: 36, w: 980, h: 540 };
const D = Math.PI / 180;
const M = { x: 740, y: 300 };
const THR_X = 1080;
const RWY_LEN = 120;
const V_FINAL = 40; // world units per sim minute, merge point to threshold
const V_ARC = 16; // world units per sim minute along the arc
const LOOP = 60; // sim minutes before the picture repeats
const RATE = 1.5; // sim minutes per real second
const OUR_LAND = 30; // when our flight lands within the loop
const MAX_ABSORB = 34; // minutes the arc can show; more than that holds

type StreamId = "N" | "S";
interface Stream {
  r: number;
  a0: number;
  dir: 1 | -1;
  span: number;
  fix: { x: number; y: number; name: string };
  len: number;
  entry: { x: number; y: number; a: number };
  feed: number;
}

function arcPt(st: Pick<Stream, "r" | "a0" | "dir">, s: number) {
  const a = st.a0 + (st.dir * s) / st.r;
  return { x: M.x + st.r * Math.cos(a), y: M.y + st.r * Math.sin(a), a };
}

function makeStream(r: number, a0: number, dir: 1 | -1, fix: Stream["fix"]): Stream {
  const st = { r, a0, dir, span: 135 * D, fix } as Stream;
  st.len = st.r * st.span;
  st.entry = arcPt(st, 0);
  st.feed = Math.hypot(fix.x - st.entry.x, fix.y - st.entry.y);
  return st;
}

const STREAMS: Record<StreamId, Stream> = {
  N: makeStream(230, -40 * D, -1, { x: 1250, y: 70, name: "NORTH FIX" }),
  S: makeStream(196, 40 * D, 1, { x: 1250, y: 540, name: "SOUTH FIX" }),
};

interface Flight {
  cs: string;
  land: number; // sim minute it lands
  absorb: number; // minutes flown on the arc
  st: StreamId;
  heavy?: boolean;
  ours?: boolean;
  runway: number; // index into the open runways
}

// Illustrative traffic: one arrival every few minutes, repeating each loop.
const ABSORB = [5, 9, 4, 12, 7, 15, 10, 18, 6, 20, 11, 22, 14, 24, 16, 26, 19, 28];
const TRAFFIC: Omit<Flight, "runway">[] = ABSORB.map((absorb, k) => ({
  cs: `TFC${String(k + 1).padStart(2, "0")}`,
  land: 1 + (k * LOOP) / ABSORB.length,
  absorb,
  st: k % 2 ? "N" : "S",
  heavy: k % 5 === 2,
}));

interface Scene {
  runways: { id: string; closed: boolean }[];
  assigned: number; // index into runways, -1 when there is no plan
  absorb: number;
  action: FlightPlanAction | undefined;
  noGo: boolean;
  callsign: string;
  arrival: string | null;
  dest: string;
  delay: number | null;
  hasRun: boolean;
  pending: boolean;
}

function minutes(clock: string | null | undefined) {
  const m = clock ? /^(\d\d):(\d\d)/.exec(clock) : null;
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

function sceneFrom(
  run: Run | null,
  selected: ScenarioSummary | undefined,
  overrides: RunOverrides,
  pending: boolean,
): Scene {
  const closedByUser = overrides.closed_runways ?? [];
  const runways = (run?.airport?.runways ?? []).map((r) => ({ id: r.id, closed: r.closed || closedByUser.includes(r.id) }));
  const deal = run?.decision.kind === "DEAL" ? run.decision.package : null;
  const arrival = landingFact(run?.card)?.clock ?? null;
  const sched = minutes(selected?.scheduled_arrival);
  const lands = minutes(arrival);
  const delay = sched !== null && lands !== null ? (lands - sched + 1440) % 1440 : (selected?.delay_minutes ?? null);
  const action = planActionFromLabel(run?.card?.action_facts.find((f) => f.key === "action")?.value ?? deal?.label);
  return {
    runways,
    assigned: deal ? runways.findIndex((r) => r.id === deal.runway_id) : -1,
    absorb: action === "direct" || action === "ground_delay" ? 0 : Math.max(0, delay ?? 0),
    action,
    noGo: run?.decision.kind === "NO_GO",
    callsign: selected?.flight_id ?? "Selected flight",
    arrival,
    dest: (selected && routeCodes(selected.route)?.[1]) ?? "Arrival airport",
    delay,
    hasRun: run !== null,
    pending,
  };
}

/** Reads a theme colour once, falling back when canvas cannot parse it. */
function themeColour(el: Element, name: string, fallback: string) {
  const v = getComputedStyle(el).getPropertyValue(name).trim();
  if (!v) return fallback;
  const probe = document.createElement("canvas").getContext("2d");
  if (!probe) return fallback;
  probe.fillStyle = "#010203";
  probe.fillStyle = v;
  return probe.fillStyle === "#010203" ? fallback : v;
}

export function ApproachView({
  run,
  selected,
  overrides,
  pending = false,
  frame,
  className,
}: {
  run: Run | null;
  selected: ScenarioSummary | undefined;
  overrides: RunOverrides;
  /** True while a new plan is being made. */
  pending?: boolean;
  /** The clear area between the panels; the drawing fits inside it. */
  frame?: RefObject<HTMLElement | null>;
  className?: string;
}) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const reduced = useReducedMotion();
  const current = sceneFrom(run, selected, overrides, pending);
  const scene = useRef<Scene>(current);
  // Values the drawing eases towards, so a new plan slides rather than jumps.
  const shown = useRef({ absorb: current.absorb, finalY: 0, born: 0 });

  useEffect(() => {
    scene.current = current;
  });

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d");
    if (!ctx) return;

    const ink = themeColour(el, "--foreground", "#eeeef2");
    const muted = themeColour(el, "--muted-foreground", "#a4a6b0");
    const beacon = themeColour(el, "--beacon", "#a78bfa");
    const danger = themeColour(el, "--destructive", "#f87171");
    const hair = themeColour(el, "--border", "#2a2a33");
    const family = getComputedStyle(el).fontFamily || "sans-serif";
    const font = (w: number, s: number) => `${w} ${s}px ${family}`;

    let raf = 0;
    let last = performance.now();
    let sim = 0;
    shown.current.born = performance.now();

    const draw = (now: number) => {
      const sc = scene.current;
      const dt = Math.min(100, now - last);
      last = now;
      if (!reduced) sim = (sim + (dt / 1000) * RATE) % LOOP;
      else sim = 18;

      // Size and fit the world into the clear area.
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const cw = el.clientWidth, ch = el.clientHeight;
      if (!cw || !ch) {
        raf = requestAnimationFrame(draw);
        return;
      }
      if (el.width !== Math.round(cw * dpr) || el.height !== Math.round(ch * dpr)) {
        el.width = Math.round(cw * dpr);
        el.height = Math.round(ch * dpr);
      }
      const box = el.getBoundingClientRect();
      const f = frame?.current?.getBoundingClientRect();
      const fx = f && f.width > 200 ? f.left - box.left : 0;
      const fy = f && f.height > 160 ? f.top - box.top : 0;
      const fw = f && f.width > 200 ? f.width : cw;
      const fh = f && f.height > 160 ? f.height : ch;
      const s = Math.min(fw / VIEW.w, fh / VIEW.h);
      const ox = fx + (fw - VIEW.w * s) / 2 - VIEW.x * s, oy = fy + (fh - VIEW.h * s) / 2 - VIEW.y * s;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, el.width, el.height);
      ctx.setTransform(dpr * s, 0, 0, dpr * s, dpr * ox, dpr * oy);

      const intro = reduced ? 1 : Math.min(1, (now - shown.current.born) / 1600);
      const ease = 1 - Math.pow(1 - intro, 3);

      // Runways: stacked thresholds to the right of the merge point.
      const n = Math.max(1, sc.runways.length);
      const gap = n > 3 ? 38 : 52;
      const rwyY = (i: number) => M.y + (i - (n - 1) / 2) * gap;
      const open = sc.runways.map((r, i) => (r.closed ? -1 : i)).filter((i) => i >= 0);
      const allClosed = sc.runways.length > 0 && open.length === 0;

      // Ease our final towards the assigned runway, and our arc distance towards the plan.
      const targetY = sc.assigned >= 0 ? rwyY(sc.assigned) : M.y;
      if (!shown.current.finalY) shown.current.finalY = targetY;
      shown.current.finalY += (targetY - shown.current.finalY) * 0.08;
      shown.current.absorb += (sc.absorb - shown.current.absorb) * 0.08;

      const finalTime = (y: number) => Math.hypot(THR_X - M.x, y - M.y) / V_FINAL;

      const timing = (fl: Flight, y: number) => {
        const st = STREAMS[fl.st];
        const tl = fl.land;
        const tm = tl - finalTime(y);
        let tt = tm - st.r / V_FINAL;
        const te = tt - fl.absorb;
        const tf0 = te - st.feed / V_FINAL;
        // Nobody may turn in when no runway is open: the arcs fill, then hold.
        if (allClosed || (fl.ours && sc.noGo)) tt = Infinity;
        return { tl, tm, tt, te, tf0 };
      };
      const onArc = (st: Stream, d: number) => {
        if (d <= st.len) return { ...arcPt(st, d), hold: false };
        const e = arcPt(st, st.len), R = 15;
        const cx = e.x + Math.cos(e.a) * R, cy = e.y + Math.sin(e.a) * R;
        const phi = e.a + Math.PI + (st.dir * (d - st.len)) / R;
        return { x: cx + R * Math.cos(phi), y: cy + R * Math.sin(phi), a: e.a, hold: true };
      };
      const where = (fl: Flight, t: number, y: number) => {
        const T = timing(fl, y), st = STREAMS[fl.st];
        if (t < T.tf0 || t >= T.tl) return null;
        if (t < T.te) {
          const k = (t - T.tf0) / (T.te - T.tf0);
          return { x: st.fix.x + (st.entry.x - st.fix.x) * k, y: st.fix.y + (st.entry.y - st.fix.y) * k, hold: false };
        }
        if (t < T.tt) return onArc(st, V_ARC * (t - T.te));
        const P = onArc(st, V_ARC * (T.tt - T.te));
        if (t < T.tm) {
          const k = (t - T.tt) / (T.tm - T.tt);
          return { x: P.x + (M.x - P.x) * k, y: P.y + (M.y - P.y) * k, hold: false };
        }
        const k = (t - T.tm) / (T.tl - T.tm);
        return { x: M.x + (THR_X - M.x) * k, y: M.y + (y - M.y) * k, hold: false };
      };

      // Faint range rings round the airport.
      ctx.save();
      ctx.strokeStyle = hair;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 6]);
      [150, 300, 450, 600].forEach((r) => {
        ctx.beginPath();
        ctx.arc(THR_X, M.y, r, Math.PI * 0.5, Math.PI * 0.5 + Math.PI * ease);
        ctx.stroke();
      });
      ctx.restore();

      // Feeders, sequencing arcs with distance ticks, and holds.
      (["N", "S"] as const).forEach((k) => {
        const st = STREAMS[k];
        ctx.strokeStyle = muted;
        ctx.globalAlpha = 0.7;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(st.fix.x, st.fix.y);
        ctx.lineTo(st.fix.x + (st.entry.x - st.fix.x) * ease, st.fix.y + (st.entry.y - st.fix.y) * ease);
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.moveTo(st.fix.x, st.fix.y - 8);
        ctx.lineTo(st.fix.x - 7, st.fix.y + 5);
        ctx.lineTo(st.fix.x + 7, st.fix.y + 5);
        ctx.closePath();
        ctx.stroke();
        ctx.fillStyle = muted;
        ctx.font = font(600, 14);
        ctx.textAlign = "right";
        ctx.fillText(st.fix.name, st.fix.x - 14, st.fix.y + 4);
        ctx.textAlign = "left";

        ctx.strokeStyle = ink;
        ctx.globalAlpha = 0.55;
        ctx.lineWidth = 1.5;
        const a1 = st.a0, a2 = st.a0 + st.dir * st.span * ease;
        ctx.beginPath();
        ctx.arc(M.x, M.y, st.r, Math.min(a1, a2), Math.max(a1, a2));
        ctx.stroke();
        ctx.lineWidth = 1;
        for (let d = 0; d <= st.len * ease; d += 32) {
          const q = arcPt(st, d), L = Math.round(d / 32) % 5 === 0 ? 9 : 4;
          ctx.beginPath();
          ctx.moveTo(q.x, q.y);
          ctx.lineTo(q.x + Math.cos(q.a) * L, q.y + Math.sin(q.a) * L);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        if (ease > 0.95) {
          const e = arcPt(st, st.len);
          ctx.setLineDash([3, 3]);
          ctx.strokeStyle = allClosed ? danger : muted;
          ctx.beginPath();
          ctx.arc(e.x + Math.cos(e.a) * 15, e.y + Math.sin(e.a) * 15, 15, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = allClosed ? danger : muted;
          ctx.font = font(600, 13);
          ctx.fillText("HOLD", e.x + Math.cos(e.a) * 15 - 13, e.y + Math.sin(e.a) * 15 + (k === "N" ? -22 : 30));
        }
      });

      // Merge point.
      ctx.fillStyle = ink;
      ctx.beginPath();
      ctx.moveTo(M.x, M.y - 8);
      ctx.lineTo(M.x + 8, M.y);
      ctx.lineTo(M.x, M.y + 8);
      ctx.lineTo(M.x - 8, M.y);
      ctx.closePath();
      ctx.fill();
      ctx.font = font(700, 17);
      ctx.fillText("MERGE", M.x - 24, M.y + 26);

      // Finals and runways, from the run.
      sc.runways.forEach((r, i) => {
        const y = rwyY(i);
        const mine = i === sc.assigned && !r.closed;
        ctx.save();
        ctx.strokeStyle = r.closed ? muted : mine ? beacon : ink;
        ctx.globalAlpha = r.closed ? 0.35 : mine ? 0.9 : 0.4;
        ctx.lineWidth = mine ? 2.5 : 1.5;
        if (r.closed) ctx.setLineDash([6, 6]);
        ctx.beginPath();
        ctx.moveTo(M.x, M.y);
        ctx.lineTo(M.x + (THR_X - M.x) * ease, M.y + (y - M.y) * ease);
        ctx.stroke();
        ctx.restore();

        const len = RWY_LEN * ease;
        ctx.fillStyle = r.closed ? danger : mine ? beacon : ink;
        ctx.globalAlpha = r.closed ? 0.25 : mine ? 1 : 0.8;
        ctx.fillRect(THR_X, y - 7, len, 14);
        ctx.globalAlpha = 1;
        if (r.closed) {
          ctx.save();
          ctx.beginPath();
          ctx.rect(THR_X, y - 7, len, 14);
          ctx.clip();
          ctx.strokeStyle = danger;
          ctx.lineWidth = 3;
          for (let x = THR_X - 20; x < THR_X + RWY_LEN + 20; x += 10) {
            ctx.beginPath();
            ctx.moveTo(x, y + 9);
            ctx.lineTo(x + 16, y - 9);
            ctx.stroke();
          }
          ctx.restore();
        } else {
          ctx.save();
          ctx.strokeStyle = mine ? "#ffffff" : "rgba(0,0,0,0.55)";
          ctx.lineWidth = 1.2;
          ctx.setLineDash([7, 5]);
          ctx.beginPath();
          ctx.moveTo(THR_X + 6, y);
          ctx.lineTo(THR_X + len - 4, y);
          ctx.stroke();
          ctx.restore();
        }
        ctx.fillStyle = r.closed ? danger : mine ? beacon : muted;
        ctx.font = font(700, 21);
        ctx.fillText(r.id, THR_X + RWY_LEN + 12, y + 6);
        if (r.closed) {
          ctx.font = font(700, 13);
          ctx.fillText("CLSD", THR_X + RWY_LEN + 12, y + 20);
        } else if (mine && sc.arrival) {
          ctx.font = font(600, 14);
          ctx.fillStyle = ink;
          ctx.fillText(sc.arrival, THR_X + RWY_LEN + 12, y + 21);
        }
      });

      // Traffic, routed to open runways in turn.
      const fadeIn = Math.max(0, Math.min(1, (intro - 0.55) / 0.45));
      ctx.globalAlpha = fadeIn;
      const flights: Flight[] = TRAFFIC.map((t, k) => ({ ...t, runway: open.length ? open[k % open.length] : 0 }));
      const ours: Flight | null = sc.hasRun
        ? {
            cs: sc.callsign,
            land: OUR_LAND,
            absorb: Math.min(MAX_ABSORB + 6, shown.current.absorb),
            st: "N",
            ours: true,
            runway: sc.assigned,
          }
        : null;

      // Our flight's absorbed stretch and turn, drawn under the aircraft.
      if (ours) {
        const st = STREAMS.N;
        const T = timing(ours, shown.current.finalY);
        const dTurn = Math.min(st.len, V_ARC * ours.absorb);
        if (sim > T.tf0 && sim < T.tm) {
          ctx.save();
          ctx.strokeStyle = beacon;
          ctx.globalAlpha = 0.25 * fadeIn;
          ctx.lineWidth = 9;
          ctx.lineCap = "round";
          const aA = st.a0, aB = st.a0 + (st.dir * dTurn) / st.r;
          ctx.beginPath();
          ctx.arc(M.x, M.y, st.r, Math.min(aA, aB), Math.max(aA, aB));
          ctx.stroke();
          ctx.restore();
          const P = arcPt(st, dTurn);
          if (isFinite(T.tt)) {
            ctx.save();
            ctx.strokeStyle = beacon;
            ctx.setLineDash([5, 4]);
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(P.x, P.y);
            ctx.lineTo(M.x, M.y);
            ctx.stroke();
            ctx.restore();
          }
        }
      }

      // The picture repeats, so each flight is also drawn one loop early or late.
      const instances = (ours ? [...flights, ours] : flights).flatMap((fl) =>
        [0, LOOP, -LOOP].map((shift) => ({ ...fl, land: fl.land + shift })),
      );
      for (const fl of instances) {
        const y = fl.ours ? shown.current.finalY : rwyY(fl.runway);
        const pos = where(fl, sim, y);
        if (!pos) continue;
        const col = fl.ours ? beacon : ink;
        for (let k = 1; k <= 6; k++) {
          const q = where(fl, sim - k * 0.25, y);
          if (!q) break;
          ctx.fillStyle = col;
          ctx.globalAlpha = fadeIn * (fl.ours ? 0.55 - k * 0.08 : 0.3 - k * 0.045);
          ctx.beginPath();
          ctx.arc(q.x, q.y, fl.ours ? 2 : 1.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = fadeIn;
        const q = where(fl, sim - 0.05, y) ?? pos;
        let hd = Math.atan2(pos.y - q.y, pos.x - q.x);
        if (!isFinite(hd)) hd = 0;
        const sz = fl.ours ? 11 : 7;
        ctx.save();
        ctx.translate(pos.x, pos.y);
        ctx.rotate(hd);
        ctx.beginPath();
        ctx.moveTo(sz, 0);
        ctx.lineTo(-sz * 0.8, -sz * 0.7);
        ctx.lineTo(-sz * 0.35, 0);
        ctx.lineTo(-sz * 0.8, sz * 0.7);
        ctx.closePath();
        ctx.fillStyle = col;
        ctx.globalAlpha = fadeIn * (fl.ours ? 1 : 0.75);
        ctx.fill();
        ctx.restore();
        ctx.fillStyle = col;
        ctx.globalAlpha = fadeIn * (fl.ours ? 1 : 0.6);
        ctx.font = fl.ours ? font(700, 17) : font(500, 13);
        ctx.fillText(fl.cs + (fl.heavy ? " H" : ""), pos.x + 10, pos.y - 9);
      }
      ctx.globalAlpha = 1;

      // Header and caption.
      ctx.fillStyle = ink;
      ctx.font = font(700, 26);
      ctx.fillText(`${sc.dest} arrivals`, VIEW.x, VIEW.y + 26);
      ctx.fillStyle = muted;
      ctx.font = font(500, 15);
      const openText = sc.pending
        ? "Making a recovery plan…"
        : sc.runways.length
          ? `${open.length} of ${sc.runways.length} runways open`
          : "Pick a flight to load its airport";
      ctx.fillText(openText, VIEW.x, VIEW.y + 48);

      // What the plan does with our flight, in words, under the header.
      if (sc.hasRun) {
        let how: string;
        if (sc.noGo) how = "No-go: no legal plan, holding until the duty manager decides";
        else if (allClosed) how = "No runway open: holding";
        else if (sc.action === "ground_delay") how = "Ground delay at origin";
        else if (sc.action === "direct") how = "Direct to the merge point";
        else if (sc.action === "hold") how = "Holds at a fix, then turns in";
        else if (sc.action === "vector") how = `Flies ${Math.round(shown.current.absorb)} min along the arc, then turns in`;
        else how = "Flies the arc, then turns in";
        const rwy = sc.assigned >= 0 ? sc.runways[sc.assigned]?.id : null;
        ctx.fillStyle = beacon;
        ctx.font = font(700, 16);
        ctx.fillText(`${sc.callsign}${rwy ? ` · runway ${rwy}` : ""}`, VIEW.x, VIEW.y + 78);
        ctx.font = font(500, 14);
        ctx.fillText(how, VIEW.x, VIEW.y + 97);
        if (sc.arrival) ctx.fillText(`Lands ${sc.arrival}${sc.delay !== null ? `, +${sc.delay} min on schedule` : ""}`, VIEW.x, VIEW.y + 115);
      }
      ctx.fillStyle = muted;
      ctx.font = font(500, 13);
      ctx.fillText(
        "Runway IDs, closures and the plan are from this run. Geometry, other traffic and the clock are illustrative.",
        VIEW.x,
        VIEW.y + VIEW.h - 4,
      );

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [frame, reduced]);

  return (
    <canvas
      ref={canvas}
      role="img"
      aria-label={`Approach to ${current.dest}: ${current.runways.length} runways, ${
        current.runways.filter((r) => r.closed).map((r) => `runway ${r.id} closed`).join(", ") || "none closed"
      }${current.assigned >= 0 ? `, plan uses runway ${current.runways[current.assigned]?.id}` : ""}.`}
      className={className}
    />
  );
}
