"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Database, PlayCircle } from "lucide-react";
import { motion } from "motion/react";
import { api } from "@/lib/api";
import type { Run, ScenarioSummary } from "@/lib/api-types";
import { OUTCOME, outcomeOf, type Outcome } from "@/lib/outcome";
import { AIRPORTS, routeCodes } from "@/lib/airports";
import { EASE_OUT, RISE, STAGGER } from "@/lib/motion";
import { cn } from "@/lib/utils";
import stats from "@/lib/flight-stats.json";
import { AppNav } from "@/components/app-nav";
import { CountUp } from "@/components/count-up";
import { Skeleton } from "@/components/ui/skeleton";
import { OrbitingGlobe, type GlobeRoute } from "@/components/landing/orbiting-globe";
import { ArrivalsTable } from "@/components/overview/arrivals-table";

const CAUSES: { key: keyof typeof stats.causeMinutes; label: string }[] = [
  { key: "late_aircraft", label: "Late aircraft" },
  { key: "weather", label: "Weather" },
  { key: "airline", label: "Airline" },
  { key: "air_system", label: "Air system" },
  { key: "security", label: "Security" },
];

const fmt = new Intl.NumberFormat("en-US");

function Panel({
  title,
  action,
  source,
  className,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  source?: "real" | "demo" | "runs";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      variants={RISE}
      aria-label={title}
      className={cn("flex min-w-0 flex-col rounded-2xl border border-white/10 bg-card/70 p-5 backdrop-blur-xl backdrop-saturate-150 [box-shadow:inset_0_1px_0_0_rgb(255_255_255/0.06)]", className)}
    >
      <header className="mb-4 flex items-center gap-2">
        <h2 className="font-display text-lg font-medium">{title}</h2>
        {source && (
          <span
            title={
              source === "real"
                ? "Counted from the US DOT on-time records for 2015"
                : source === "runs"
                  ? "From one recorded run of each demo flight: saved answers replay, no model is called"
                  : "From the demo flight list, not from the 2015 counts"
            }
            className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground"
          >
            {source === "real" ? <Database aria-hidden className="size-3.5" /> : <PlayCircle aria-hidden className="size-3.5" />}
            {source === "real" ? "US DOT 2015" : source === "runs" ? "Recorded runs" : "Demo flights"}
          </span>
        )}
        <div className="ml-auto">{action}</div>
      </header>
      {children}
    </motion.section>
  );
}

/** A ring split into labelled parts, drawn with stroke dashes on one circle. */
function Donut({ parts, total }: { parts: { label: string; n: number; stroke: string }[]; total: number }) {
  const r = 64;
  const c = 2 * Math.PI * r;
  // Each segment starts where the ones before it end.
  const segments = parts.map((p, i) => ({
    ...p,
    len: total ? (p.n / total) * c : 0,
    start: parts.slice(0, i).reduce((sum, q) => sum + (total ? (q.n / total) * c : 0), 0),
  }));
  return (
    <svg viewBox="0 0 160 160" className="size-44" role="img" aria-label={parts.map((p) => `${p.label} ${p.n}`).join(", ")}>
      <circle cx="80" cy="80" r={r} fill="none" strokeWidth="16" className="stroke-muted" />
      {/* Each segment draws itself round the ring, after the ones before it. */}
      {segments.map(({ label, n, len, start, stroke }, i) =>
        n === 0 ? null : (
          <motion.circle
            key={label}
            cx="80"
            cy="80"
            r={r}
            fill="none"
            strokeWidth="16"
            initial={{ strokeDasharray: `0 ${c}` }}
            animate={{ strokeDasharray: `${Math.max(len - 3, 0)} ${c}` }}
            transition={{ ...EASE_OUT, duration: 0.9, delay: 0.25 + i * 0.15 }}
            strokeDashoffset={-start}
            transform="rotate(-90 80 80)"
            className={stroke}
          />
        ),
      )}
      <text x="80" y="78" textAnchor="middle" className="fill-foreground font-display text-[34px] font-semibold">
        <CountUp value={total} as="tspan" />
      </text>
      <text x="80" y="100" textAnchor="middle" className="fill-muted-foreground text-[11px]">
        flights
      </text>
    </svg>
  );
}

function Bar({ label, value, max, tone = "bg-primary", suffix }: { label: string; value: number; max: number; tone?: string; suffix?: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="truncate">{label}</span>
        <span className="font-display font-semibold tabular-nums">
          <CountUp value={value} />
          {suffix}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        {/* Grows from the left when it scrolls into view. */}
        <motion.div
          className={cn("h-full origin-left rounded-full", tone)}
          style={{ width: `${max ? (value / max) * 100 : 0}%` }}
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true }}
          transition={{ ...EASE_OUT, duration: 0.8 }}
        />
      </div>
    </div>
  );
}

export function Overview() {
  const [flights, setFlights] = useState<ScenarioSummary[] | null>(null);
  const [runs, setRuns] = useState<Record<string, Run | null>>({});
  const [failed, setFailed] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const router = useRouter();
  const pressAt = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    let live = true;
    // The system document asks for each flight's outcome here. Each flight runs
    // once in recorded mode: saved answers replay, so no model is called, but
    // each run writes its evidence log like any other run.
    api
      .listScenarios({ limit: 12 })
      .then((list) => {
        if (!live) return;
        setFlights(list);
        for (const flight of list) {
          api
            .createRun({ scenario_id: flight.scenario_id, mode: "recorded", overrides: {} })
            .then((run) => live && setRuns((r) => ({ ...r, [flight.scenario_id]: run })))
            .catch(() => live && setRuns((r) => ({ ...r, [flight.scenario_id]: null })));
        }
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);

  const outcomes = useMemo(
    () => Object.fromEntries(Object.entries(runs).map(([id, run]) => [id, run ? outcomeOf(run) : "failed"])) as Record<string, Outcome>,
    [runs],
  );
  const finished = flights !== null && flights.every((f) => f.scenario_id in runs);

  // Outcomes in the document's order, leaving out ones no flight had.
  const outcomeParts = useMemo(
    () =>
      (["agreed", "fallback", "no_go", "fault", "failed"] as Outcome[])
        .map((o) => ({ key: o, label: OUTCOME[o].label, n: Object.values(outcomes).filter((x) => x === o).length, stroke: OUTCOME[o].stroke, dot: OUTCOME[o].dot }))
        .filter((p) => p.n > 0 || p.key === "agreed" || p.key === "fallback" || p.key === "no_go"),
    [outcomes],
  );

  // Every rule that removed a plan, most often first.
  const removedByRule = useMemo(() => {
    const m = new Map<string, { label: string; count: number }>();
    for (const run of Object.values(runs)) {
      run?.removed_packages.forEach((p) =>
        p.violations.forEach((v) => {
          const cur = m.get(v.rule_id) ?? { label: v.label ?? v.rule_id, count: 0 };
          cur.count++;
          m.set(v.rule_id, cur);
        }),
      );
    }
    return [...m.entries()].sort((a, b) => b[1].count - a[1].count).slice(0, 5);
  }, [runs]);

  const routes = useMemo<GlobeRoute[]>(
    () =>
      (flights ?? []).flatMap((flight) => {
        const codes = routeCodes(flight.route);
        const from = codes && AIRPORTS[codes[0]];
        const to = codes && AIRPORTS[codes[1]];
        return from && to ? [{ id: flight.scenario_id, from, to }] : [];
      }),
    [flights],
  );

  const causeMax = Math.max(...CAUSES.map((c) => stats.causeMinutes[c.key]));
  const destMax = stats.topDestinations[0]?.count ?? 0;
  const routeMax = stats.topRoutes[0]?.count ?? 0;
  const pct = (n: number) => Math.round((n / stats.eligible) * 100);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/70 px-4 backdrop-blur sm:px-6">
        <AppNav />
      </header>

      {/* The globe and each panel rise into place one after another. */}
      <motion.main
        variants={STAGGER}
        initial="hidden"
        animate="shown"
        className="mx-auto grid max-w-[100rem] gap-4 p-4 sm:p-6 lg:grid-cols-12"
      >
        {/* Centre stage: the globe across the full width. Clicking it opens the flights page. */}
        <motion.section variants={RISE} aria-label="Demo flights on the globe" className="relative lg:col-span-12">
          <div className="pointer-events-none absolute top-1 left-1 z-10">
            <h1 className="font-display text-2xl font-medium">Demo flights</h1>
            <p className="text-sm text-muted-foreground tabular-nums">
              {flights ? `${flights.length} flights, ${flights.reduce((n, f) => n + f.delay_minutes, 0)} min of delay in all` : "\u00a0"}
            </p>
          </div>
          <div
            className="relative cursor-pointer"
            onPointerDown={(e) => (pressAt.current = { x: e.clientX, y: e.clientY })}
            onClick={(e) => {
              // A drag spins the globe; only a still click opens the flights page.
              const p = pressAt.current;
              if (p && Math.hypot(e.clientX - p.x, e.clientY - p.y) < 6) router.push("/dashboard/flights");
            }}
          >
            <OrbitingGlobe
              routes={routes}
              activeId={activeId}
              layout="horizon"
              className="h-[22rem] sm:h-[28rem] lg:h-[min(62vh,40rem)]"
            />
          </div>
          <p className="pointer-events-none absolute right-1 bottom-2 z-10 max-w-48 text-right text-[11px] text-muted-foreground sm:max-w-none">
            Illustration. The planes circle the routes for show; they are not live positions.
          </p>
          <div className="absolute inset-x-0 bottom-2 z-10 flex justify-center">
            <Link
              href="/dashboard/flights"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/80 px-4 py-2 text-sm backdrop-blur outline-none transition-colors hover:border-beacon hover:text-beacon focus-visible:ring-2 focus-visible:ring-ring"
            >
              Open flights
              <ArrowUpRight aria-hidden className="size-4" />
            </Link>
          </div>
        </motion.section>

        {/* The demo flights, in order. Pointing at one lights it on the globe. */}
        <Panel title="Arrivals" source="demo" className="lg:col-span-12">
          {failed ? (
            <p className="text-sm text-muted-foreground">The planning service did not answer.</p>
          ) : !flights ? (
            <Skeleton className="h-64 w-full" />
          ) : flights.length === 0 ? (
            <p className="text-sm text-muted-foreground">There are no demo flights.</p>
          ) : (
            <ArrivalsTable flights={flights} outcomes={outcomes} activeId={activeId} onActive={setActiveId} />
          )}
        </Panel>

        {/* Outcome mix across the demo flights, filled in as each run finishes */}
        <Panel title="Outcomes" source="runs" className="lg:col-span-4">
          {failed ? (
            <p className="text-sm text-muted-foreground">The planning service did not answer.</p>
          ) : !flights || !finished ? (
            <Skeleton className="mx-auto size-44 rounded-full" />
          ) : flights.length === 0 ? (
            <p className="text-sm text-muted-foreground">There are no demo flights.</p>
          ) : (
            <div className="flex flex-1 flex-col items-center gap-4">
              <Donut parts={outcomeParts} total={flights.length} />
              <ul className="grid w-full gap-1.5">
                {outcomeParts.map((c) => (
                  <li key={c.key} className="flex items-center gap-2 rounded-xl border border-border bg-background/40 px-3 py-2 text-sm">
                    <span aria-hidden className={cn("size-2.5 rounded-full", c.dot)} />
                    <span className="truncate text-muted-foreground">{c.label}</span>
                    <span className="ml-auto font-display text-base font-semibold tabular-nums">{c.n}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>

        {/* Runs: what the safety rules removed */}
        <Panel title="Rules that removed plans" source="runs" className="lg:col-span-4">
          {failed ? (
            <p className="text-sm text-muted-foreground">The planning service did not answer.</p>
          ) : !finished ? (
            <Skeleton className="h-32 w-full" />
          ) : removedByRule.length === 0 ? (
            <p className="text-sm text-muted-foreground">No plan broke a rule on these flights.</p>
          ) : (
            <ul className="space-y-4">
              {removedByRule.map(([id, r]) => (
                <li key={id}>
                  <Bar label={r.label} value={r.count} max={removedByRule[0][1].count} tone="bg-destructive/80" />
                  <span className="mt-1 block font-mono text-xs text-muted-foreground">{id}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-auto pt-4 text-xs text-muted-foreground">Plans removed per rule, across these flights&apos; runs</p>
        </Panel>

        {/* Real: where delays are */}
        <Panel title="Routes with most delayed arrivals" source="real" className="lg:col-span-4">
          <ul className="space-y-4">
            {stats.topRoutes.map((r, i) => (
              <li key={r.key}>
                <Bar label={r.key.replace("-", " → ")} value={r.count} max={routeMax} tone={i === 0 ? "bg-beacon" : "bg-primary/70"} />
              </li>
            ))}
          </ul>
          <p className="mt-auto pt-4 text-xs text-muted-foreground">Delayed arrivals per route, US DOT 2015</p>
        </Panel>

        <Panel title="Airports with most delayed arrivals" source="real" className="lg:col-span-4">
          <ul className="space-y-4">
            {stats.topDestinations.map((d, i) => (
              <li key={d.key}>
                <Bar label={d.key} value={d.count} max={destMax} tone={i === 0 ? "bg-beacon" : "bg-primary/70"} />
              </li>
            ))}
          </ul>
          <p className="mt-auto pt-4 text-xs text-muted-foreground">Delayed arrivals per destination airport, US DOT 2015</p>
        </Panel>

        {/* Real: the dataset in four numbers, and delay hours by cause */}
        <Panel title="US DOT 2015 delayed arrivals" source="real" className="lg:col-span-8">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <div className="space-y-2">
              <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  { label: "Delayed arrivals", value: stats.eligible, suffix: "" },
                  { label: "Average arrival delay", value: stats.avgEligibleArrivalDelay, suffix: " min" },
                  { label: "Late aircraft over 20 min", value: pct(stats.eligibleLateAircraft), suffix: "%" },
                  { label: "Weather over 15 min", value: pct(stats.eligibleWeather), suffix: "%" },
                ].map((t) => (
                  <motion.div
                    key={t.label}
                    whileHover={{ y: -2 }}
                    className="flex flex-col justify-between rounded-xl border border-border bg-background/40 p-3 transition-colors hover:border-primary/40"
                  >
                    <dt className="text-xs text-muted-foreground">{t.label}</dt>
                    <dd className="mt-6 font-display text-2xl font-semibold tabular-nums">
                      <CountUp value={t.value} />
                      {t.suffix}
                    </dd>
                  </motion.div>
                ))}
              </dl>
              <p className="text-xs text-muted-foreground">
                The two shares are of these arrivals. A flight can be in both, so they add up to more than 100%.
              </p>
            </div>
            <ul className="space-y-3">
              {CAUSES.slice(0, 3).map((c) => (
                <li key={c.key}>
                  <Bar
                    label={`${c.label} delay`}
                    value={Math.round(stats.causeMinutes[c.key] / 60)}
                    max={Math.round(causeMax / 60)}
                    suffix="h"
                    tone="bg-primary/70"
                  />
                </li>
              ))}
              <li className="text-xs text-muted-foreground">Hours of delay by cause, added up over these arrivals</li>
            </ul>
          </div>
        </Panel>

        <p className="text-xs text-muted-foreground lg:col-span-12">
          Source: US DOT on-time records, 2015, the organiser file flights.csv. {fmt.format(stats.eligible)} flown
          arrivals with weather delay over 15 min or late-aircraft delay over 20 min, October left out. Counted from the
          file, not estimated. Demo flights: the sample list shown on the Flights page, not a count from this file.
        </p>
      </motion.main>
    </div>
  );
}
