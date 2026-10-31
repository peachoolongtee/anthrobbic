"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, CircleAlert, CircleCheck, CircleDashed, CloudLightning, PlaneLanding } from "lucide-react";
import { api } from "@/lib/api";
import type { Run, ScenarioSummary } from "@/lib/api-types";
import { AIRPORTS, routeCodes } from "@/lib/airports";
import { cn } from "@/lib/utils";
import stats from "@/lib/flight-stats.json";
import { AppNav } from "@/components/app-nav";
import { Skeleton } from "@/components/ui/skeleton";
import { OrbitingGlobe, type GlobeRoute } from "@/components/landing/orbiting-globe";

type Outcome = "agreed" | "fallback" | "none" | "error";

interface Row {
  flight: ScenarioSummary;
  run: Run | null;
  outcome: Outcome;
}

const OUTCOME: Record<Outcome, { label: string; dot: string; text: string; Icon: typeof CircleCheck }> = {
  agreed: { label: "Agents agreed", dot: "bg-success", text: "text-success", Icon: CircleCheck },
  fallback: { label: "Fallback", dot: "bg-warning", text: "text-warning", Icon: CircleAlert },
  none: { label: "No recovery plan", dot: "bg-destructive", text: "text-destructive", Icon: CircleAlert },
  error: { label: "Failed", dot: "bg-muted-foreground", text: "text-muted-foreground", Icon: CircleDashed },
};

const CAUSE_ICON = { weather: CloudLightning, late_aircraft: PlaneLanding } as const;

const CAUSES: { key: keyof typeof stats.causeMinutes; label: string }[] = [
  { key: "late_aircraft", label: "Late aircraft" },
  { key: "weather", label: "Weather" },
  { key: "airline", label: "Airline" },
  { key: "air_system", label: "Air system" },
  { key: "security", label: "Security" },
];

const fmt = new Intl.NumberFormat("en-US");

function outcomeOf(run: Run): Outcome {
  if (run.decision.kind === "NO_DEAL") return "none";
  return run.path === "consensus" ? "agreed" : "fallback";
}

function flightHref(id: string) {
  return `/dashboard/flights?flight=${encodeURIComponent(id)}`;
}

function Panel({
  title,
  action,
  source,
  className,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  source?: "real" | "runs";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className={cn("flex min-w-0 flex-col rounded-2xl border border-border bg-card/70 p-5 backdrop-blur", className)}
    >
      <header className="mb-4 flex items-center gap-2">
        <h2 className="font-display text-lg font-medium">{title}</h2>
        {source && (
          <span
            title={source === "real" ? "Counted from the 2015 US DOT records" : "From recorded runs of the demo flights"}
            className={cn(
              "rounded px-1.5 py-0.5 text-[11px] font-medium",
              source === "real" ? "bg-success-soft text-success" : "bg-info-soft text-info",
            )}
          >
            {source === "real" ? "2015 DOT" : "Runs"}
          </span>
        )}
        <div className="ml-auto">{action}</div>
      </header>
      {children}
    </section>
  );
}

/** A ring split by outcome, drawn with stroke dashes on one circle. */
function Donut({ counts, total }: { counts: [Outcome, number][]; total: number }) {
  const r = 64;
  const c = 2 * Math.PI * r;
  // Each segment starts where the ones before it end.
  const segments = counts.map(([o, n], i) => ({
    o,
    n,
    len: total ? (n / total) * c : 0,
    start: counts.slice(0, i).reduce((sum, [, m]) => sum + (total ? (m / total) * c : 0), 0),
  }));
  return (
    <svg viewBox="0 0 160 160" className="size-44" role="img" aria-label={counts.map(([o, n]) => `${OUTCOME[o].label} ${n}`).join(", ")}>
      <circle cx="80" cy="80" r={r} fill="none" strokeWidth="16" className="stroke-muted" />
      {segments.map(({ o, n, len, start }) =>
        n === 0 ? null : (
          <circle
            key={o}
            cx="80"
            cy="80"
            r={r}
            fill="none"
            strokeWidth="16"
            strokeDasharray={`${Math.max(len - 3, 0)} ${c}`}
            strokeDashoffset={-start}
            transform="rotate(-90 80 80)"
            className={cn(
              o === "agreed" && "stroke-success",
              o === "fallback" && "stroke-warning",
              o === "none" && "stroke-destructive",
              o === "error" && "stroke-muted-foreground",
            )}
          />
        ),
      )}
      <text x="80" y="78" textAnchor="middle" className="fill-foreground font-display text-[34px] font-semibold">
        {total}
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
          {fmt.format(value)}
          {suffix}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${max ? (value / max) * 100 : 0}%` }} />
      </div>
    </div>
  );
}

export function Overview() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const router = useRouter();
  const pressAt = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    let live = true;
    // Recorded mode only: the overview must never spend live model calls.
    api
      .listScenarios({ limit: 12 })
      .then((flights) =>
        Promise.all(
          flights.map((flight) =>
            api
              .createRun({ scenario_id: flight.scenario_id, mode: "recorded", overrides: {} })
              .then((run): Row => ({ flight, run, outcome: outcomeOf(run) }))
              .catch((): Row => ({ flight, run: null, outcome: "error" })),
          ),
        ),
      )
      .then((r) => live && setRows(r))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);

  const routes = useMemo<GlobeRoute[]>(
    () =>
      (rows ?? []).flatMap(({ flight }) => {
        const codes = routeCodes(flight.route);
        const from = codes && AIRPORTS[codes[0]];
        const to = codes && AIRPORTS[codes[1]];
        return from && to ? [{ id: flight.scenario_id, from, to }] : [];
      }),
    [rows],
  );

  const counts = useMemo(() => {
    const c: Record<Outcome, number> = { agreed: 0, fallback: 0, none: 0, error: 0 };
    rows?.forEach((r) => c[r.outcome]++);
    return (Object.entries(c) as [Outcome, number][]).filter(([o, n]) => o !== "error" || n > 0);
  }, [rows]);

  const removedByRule = useMemo(() => {
    const m = new Map<string, { label: string; count: number }>();
    rows?.forEach(({ run }) =>
      run?.removed_packages.forEach((p) =>
        p.violations.forEach((v) => {
          const cur = m.get(v.rule_id) ?? { label: v.label ?? v.rule_id, count: 0 };
          cur.count++;
          m.set(v.rule_id, cur);
        }),
      ),
    );
    return [...m.entries()].sort((a, b) => b[1].count - a[1].count).slice(0, 5);
  }, [rows]);

  const sorted = rows ? [...rows].sort((a, b) => a.flight.scheduled_arrival.localeCompare(b.flight.scheduled_arrival)) : null;
  const causeMax = Math.max(...CAUSES.map((c) => stats.causeMinutes[c.key]));
  const destMax = stats.topDestinations[0]?.count ?? 0;
  const pct = (n: number) => `${Math.round((n / stats.eligible) * 100)}%`;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/70 px-4 backdrop-blur sm:px-6">
        <AppNav />
      </header>

      <main className="mx-auto grid max-w-[100rem] gap-4 p-4 sm:p-6 lg:grid-cols-12">
        {/* Centre stage: the globe across the full width. Clicking it opens the flights page. */}
        <section aria-label="Delayed arrivals on the globe" className="relative lg:col-span-12">
          <div className="pointer-events-none absolute top-1 left-1 z-10">
            <h1 className="font-display text-2xl font-medium">Delayed arrivals</h1>
            <p className="text-sm text-muted-foreground tabular-nums">
              {rows ? `${rows.length} flights, ${rows.reduce((n, r) => n + r.flight.delay_minutes, 0)} min late in all` : "\u00a0"}
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
              wide
              framed
              className="h-[24rem] sm:h-[32rem] lg:h-[min(66vh,44rem)]"
            />
          </div>
          <div className="absolute inset-x-0 bottom-2 z-10 flex justify-center">
            <Link
              href="/dashboard/flights"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/80 px-4 py-2 text-sm backdrop-blur outline-none transition-colors hover:border-beacon hover:text-beacon focus-visible:ring-2 focus-visible:ring-ring"
            >
              Open flights
              <ArrowUpRight aria-hidden className="size-4" />
            </Link>
          </div>
        </section>

        {/* Every delayed arrival, in order. Pointing at one lights it on the globe. */}
        <Panel title="Arrivals" source="runs" className="lg:col-span-12">
          <ol className="-mx-2 grid gap-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6" onMouseLeave={() => setActiveId(null)}>
            {!sorted && Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="mx-2 h-16" />)}
            {sorted?.map(({ flight, outcome }) => {
              const Icon = CAUSE_ICON[flight.cause];
              const o = OUTCOME[outcome];
              return (
                <li key={flight.scenario_id}>
                  <Link
                    href={flightHref(flight.scenario_id)}
                    onMouseEnter={() => setActiveId(flight.scenario_id)}
                    onFocus={() => setActiveId(flight.scenario_id)}
                    onBlur={() => setActiveId(null)}
                    className={cn(
                      "grid grid-cols-[3rem_minmax(0,1fr)_auto] items-center gap-x-3 rounded-xl px-2 py-2 outline-none transition-colors hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring",
                      activeId === flight.scenario_id && "bg-accent/60",
                    )}
                  >
                    <span className="row-span-2 grid size-12 place-items-center rounded-full bg-secondary font-display text-xs font-semibold tabular-nums">
                      {flight.scheduled_arrival}
                    </span>
                    <span className="font-display text-base font-medium whitespace-nowrap">
                      {flight.route.replace(" to ", " → ")}
                    </span>
                    <span className="justify-self-end font-display font-semibold text-beacon tabular-nums">+{flight.delay_minutes}</span>
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap">
                      {flight.flight_id}
                      <Icon aria-hidden className="size-3.5" />
                    </span>
                    <span className={cn("inline-flex items-center gap-1 justify-self-end text-xs whitespace-nowrap", o.text)}>
                      <o.Icon aria-hidden className="size-3.5" />
                      {o.label}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ol>
        </Panel>

        {/* Outcome mix across the demo flights */}
        <Panel title="Outcomes" source="runs" className="lg:col-span-4">
          {failed ? (
            <p className="text-sm text-muted-foreground">The planning service did not answer.</p>
          ) : !rows ? (
            <Skeleton className="mx-auto size-44 rounded-full" />
          ) : (
            <div className="flex flex-1 flex-col items-center gap-4">
              <Donut counts={counts} total={rows.length} />
              <ul className="grid w-full gap-1.5">
                {counts.map(([o, n]) => (
                  <li key={o} className="flex items-center gap-2 rounded-xl border border-border bg-background/40 px-3 py-2 text-sm">
                    <span aria-hidden className={cn("size-2.5 rounded-full", OUTCOME[o].dot)} />
                    <span className="truncate text-muted-foreground">{OUTCOME[o].label}</span>
                    <span className="ml-auto font-display text-base font-semibold tabular-nums">{n}</span>
                  </li>
                ))}
                <li className="flex items-center gap-2 rounded-xl border border-border bg-background/40 px-3 py-2 text-sm">
                  <span aria-hidden className="size-2.5 rounded-full bg-primary" />
                  <span className="truncate text-muted-foreground">Turns, max</span>
                  <span className="ml-auto font-display text-base font-semibold tabular-nums">
                    {Math.max(0, ...rows.map((r) => r.run?.turns.length ?? 0))}
                  </span>
                </li>
              </ul>
            </div>
          )}
        </Panel>

        {/* Runs: what the safety rules removed */}
        <Panel title="Rules that removed recovery plans" source="runs" className="lg:col-span-4">
          {!rows ? (
            <Skeleton className="h-32 w-full" />
          ) : removedByRule.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recovery plan broke a rule.</p>
          ) : (
            <ul className="space-y-4">
              {removedByRule.map(([id, r]) => (
                <li key={id}>
                  <Bar label={r.label} value={r.count} max={removedByRule[0][1].count} tone="bg-destructive/80" />
                  <span className="mt-1 block font-mono text-[11px] text-muted-foreground">{id}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* Real: where delays land */}
        <Panel title="Busiest airports" source="real" className="lg:col-span-4">
          <ul className="space-y-4">
            {stats.topDestinations.map((d, i) => (
              <li key={d.key}>
                <Bar label={d.key} value={d.count} max={destMax} tone={i === 0 ? "bg-beacon" : "bg-primary/70"} />
              </li>
            ))}
          </ul>
          <p className="mt-auto pt-4 text-xs text-muted-foreground">Delayed arrivals per airport</p>
        </Panel>

        {/* Real: the dataset in four numbers, and delay hours by cause */}
        <Panel title="2015 records" source="real" className="lg:col-span-12">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { label: "Delayed arrivals", value: fmt.format(stats.eligible) },
                { label: "Avg arrival delay", value: `${stats.avgEligibleArrivalDelay}m` },
                { label: "Late aircraft 20m+", value: pct(stats.eligibleLateAircraft) },
                { label: "Weather 15m+", value: pct(stats.eligibleWeather) },
              ].map((t) => (
                <div key={t.label} className="flex flex-col justify-between rounded-xl border border-border bg-background/40 p-3">
                  <dt className="text-xs text-muted-foreground">{t.label}</dt>
                  <dd className="mt-6 font-display text-2xl font-semibold tabular-nums">{t.value}</dd>
                </div>
              ))}
            </dl>
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
            </ul>
          </div>
        </Panel>

        <p className="text-xs text-muted-foreground lg:col-span-12">
          2015 DOT: {fmt.format(stats.rows)} delayed arrivals that meet the challenge rule (weather over 15 min or late
          aircraft over 20 min). Runs: recorded runs of the demo flights.
        </p>
      </main>
    </div>
  );
}
