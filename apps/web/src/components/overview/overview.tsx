"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, CloudLightning, PlaneLanding } from "lucide-react";
import { api } from "@/lib/api";
import type { ScenarioSummary } from "@/lib/api-types";
import { AIRPORTS, routeCodes } from "@/lib/airports";
import { CAUSE_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";
import stats from "@/lib/flight-stats.json";
import { AppNav } from "@/components/app-nav";
import { Skeleton } from "@/components/ui/skeleton";
import { OrbitingGlobe, type GlobeRoute } from "@/components/landing/orbiting-globe";

const CAUSE_ICON = { weather: CloudLightning, late_aircraft: PlaneLanding } as const;

const CAUSES: { key: keyof typeof stats.causeMinutes; label: string }[] = [
  { key: "late_aircraft", label: "Late aircraft" },
  { key: "weather", label: "Weather" },
  { key: "airline", label: "Airline" },
  { key: "air_system", label: "Air system" },
  { key: "security", label: "Security" },
];

const fmt = new Intl.NumberFormat("en-US");

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
  source?: "real" | "demo";
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
            title={source === "real" ? "Counted from the US DOT on-time records for 2015" : "From the demo flight list, not from the 2015 counts"}
            className={cn(
              "rounded px-1.5 py-0.5 text-[11px] font-medium",
              source === "real" ? "bg-success-soft text-success" : "bg-info-soft text-info",
            )}
          >
            {source === "real" ? "US DOT 2015" : "Demo flights"}
          </span>
        )}
        <div className="ml-auto">{action}</div>
      </header>
      {children}
    </section>
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
      {segments.map(({ label, n, len, start, stroke }) =>
        n === 0 ? null : (
          <circle
            key={label}
            cx="80"
            cy="80"
            r={r}
            fill="none"
            strokeWidth="16"
            strokeDasharray={`${Math.max(len - 3, 0)} ${c}`}
            strokeDashoffset={-start}
            transform="rotate(-90 80 80)"
            className={stroke}
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
  const [flights, setFlights] = useState<ScenarioSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const router = useRouter();
  const pressAt = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    let live = true;
    // The flight list only. The overview starts no runs, so it spends no model calls and writes no logs.
    api
      .listScenarios({ limit: 12 })
      .then((list) => live && setFlights(list))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);

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

  const byCause = useMemo(
    () => [
      { label: CAUSE_LABEL.weather, n: flights?.filter((f) => f.cause === "weather").length ?? 0, stroke: "stroke-info", dot: "bg-info" },
      { label: CAUSE_LABEL.late_aircraft, n: flights?.filter((f) => f.cause === "late_aircraft").length ?? 0, stroke: "stroke-primary", dot: "bg-primary" },
    ],
    [flights],
  );

  // Flights with saved model answers first, then by scheduled arrival.
  const sorted = flights
    ? [...flights].sort(
        (a, b) => Number(b.has_recording === true) - Number(a.has_recording === true) || a.scheduled_arrival.localeCompare(b.scheduled_arrival),
      )
    : null;
  const causeMax = Math.max(...CAUSES.map((c) => stats.causeMinutes[c.key]));
  const destMax = stats.topDestinations[0]?.count ?? 0;
  const routeMax = stats.topRoutes[0]?.count ?? 0;
  const pct = (n: number) => `${Math.round((n / stats.eligible) * 100)}%`;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/70 px-4 backdrop-blur sm:px-6">
        <AppNav />
      </header>

      <main className="mx-auto grid max-w-[100rem] gap-4 p-4 sm:p-6 lg:grid-cols-12">
        {/* Centre stage: the globe across the full width. Clicking it opens the flights page. */}
        <section aria-label="Demo flights on the globe" className="relative lg:col-span-12">
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
              wide
              framed
              className="h-[24rem] sm:h-[32rem] lg:h-[min(66vh,44rem)]"
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
        </section>

        {/* The demo flights, in order. Pointing at one lights it on the globe. */}
        <Panel title="Arrivals" source="demo" className="lg:col-span-12">
          {failed ? (
            <p className="text-sm text-muted-foreground">The planning service did not answer.</p>
          ) : sorted && sorted.length === 0 ? (
            <p className="text-sm text-muted-foreground">There are no demo flights.</p>
          ) : (
            <ol className="-mx-2 grid gap-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6" onMouseLeave={() => setActiveId(null)}>
              {!sorted && Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="mx-2 h-16" />)}
              {sorted?.map((flight) => {
                const Icon = CAUSE_ICON[flight.cause];
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
                      <span className="justify-self-end font-display font-semibold text-beacon tabular-nums">
                        +{flight.delay_minutes}
                        <span className="sr-only"> minutes of delay</span>
                      </span>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">{flight.flight_id}</span>
                      <span className="inline-flex items-center gap-1 justify-self-end text-xs text-muted-foreground whitespace-nowrap">
                        <Icon aria-hidden className="size-3.5" />
                        {CAUSE_LABEL[flight.cause]}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ol>
          )}
        </Panel>

        {/* The demo flights split by cause of delay */}
        <Panel title="Demo flights by cause" source="demo" className="lg:col-span-4">
          {failed ? (
            <p className="text-sm text-muted-foreground">The planning service did not answer.</p>
          ) : !flights ? (
            <Skeleton className="mx-auto size-44 rounded-full" />
          ) : flights.length === 0 ? (
            <p className="text-sm text-muted-foreground">There are no demo flights.</p>
          ) : (
            <div className="flex flex-1 flex-col items-center gap-4">
              <Donut parts={byCause} total={flights.length} />
              <ul className="grid w-full gap-1.5">
                {byCause.map((c) => (
                  <li key={c.label} className="flex items-center gap-2 rounded-xl border border-border bg-background/40 px-3 py-2 text-sm">
                    <span aria-hidden className={cn("size-2.5 rounded-full", c.dot)} />
                    <span className="truncate text-muted-foreground">{c.label}</span>
                    <span className="ml-auto font-display text-base font-semibold tabular-nums">{c.n}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
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
        <Panel title="US DOT 2015 delayed arrivals" source="real" className="lg:col-span-12">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <div className="space-y-2">
              <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  { label: "Delayed arrivals", value: fmt.format(stats.eligible) },
                  { label: "Average arrival delay", value: `${stats.avgEligibleArrivalDelay} min` },
                  { label: "Late aircraft over 20 min", value: pct(stats.eligibleLateAircraft) },
                  { label: "Weather over 15 min", value: pct(stats.eligibleWeather) },
                ].map((t) => (
                  <div key={t.label} className="flex flex-col justify-between rounded-xl border border-border bg-background/40 p-3">
                    <dt className="text-xs text-muted-foreground">{t.label}</dt>
                    <dd className="mt-6 font-display text-2xl font-semibold tabular-nums">{t.value}</dd>
                  </div>
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
      </main>
    </div>
  );
}
