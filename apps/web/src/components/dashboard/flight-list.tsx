"use client";

import type { ReactNode } from "react";
import { CloudLightning, CornerDownRight, Layers, PlaneLanding, Search } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { Cause, ScenarioSummary } from "@/lib/api-types";
import { useEligibleCount } from "@/hooks/use-eligible-count";
import { CAUSE_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { EmptyPanel, ErrorPanel, LoadingBlock } from "@/components/dashboard/states";
import { ProvenanceMark } from "@/components/dashboard/provenance-badge";
import { Airliner } from "@/components/landing/airliner";

type ScenarioLoad =
  | { status: "loading" }
  | { status: "error"; message: string; unreachable: boolean }
  | { status: "ready"; data: ScenarioSummary[] };

const CAUSE_ICON = { weather: CloudLightning, late_aircraft: PlaneLanding } as const;

const CAUSE_FILTERS: { value: Cause | "all"; label: string; Icon: typeof Layers }[] = [
  { value: "all", label: "All", Icon: Layers },
  { value: "weather", label: CAUSE_LABEL.weather, Icon: CAUSE_ICON.weather },
  { value: "late_aircraft", label: CAUSE_LABEL.late_aircraft, Icon: CAUSE_ICON.late_aircraft },
];

function codes(route: string): [string, string] {
  const [a, b] = route.split(" to ");
  return [a ?? route, b ?? ""];
}

/** A route drawn as two airport codes joined by a flight line. */
export function RouteCodes({ route, size = "md" }: { route: string; size?: "md" | "lg" }) {
  const [from, to] = codes(route);
  return (
    <div className="flex items-center gap-2" aria-label={route}>
      <span className={cn("font-display font-semibold tracking-tight", size === "lg" ? "text-3xl" : "text-xl")}>
        {from}
      </span>
      <span aria-hidden className="relative flex flex-1 items-center">
        <span className="h-px w-full bg-gradient-to-r from-muted-foreground/30 via-muted-foreground/60 to-muted-foreground/30" />
        <Airliner className="absolute left-1/2 size-4 -translate-x-1/2 text-muted-foreground" />
      </span>
      <span className={cn("font-display font-semibold tracking-tight", size === "lg" ? "text-3xl" : "text-xl")}>
        {to}
      </span>
    </div>
  );
}

export function FlightList({
  scenarios,
  cause,
  onCauseChange,
  query,
  onQueryChange,
  selectedId,
  onSelect,
  onRetry,
  found,
  finder,
  hideRecordedTag,
}: {
  scenarios: ScenarioLoad;
  cause: Cause | "all";
  onCauseChange: (c: Cause | "all") => void;
  query: string;
  onQueryChange: (q: string) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRetry: () => void;
  /** Flights the lookup found. They stay at the top, whatever the filters say. */
  found: ScenarioSummary[];
  finder: ReactNode;
  /** In Live nothing is replayed, so the tag would read as if this run were. */
  hideRecordedTag: boolean;
}) {
  const eligible = useEligibleCount();
  const q = query.trim().toLowerCase();
  const foundIds = new Set(found.map((s) => s.scenario_id));
  const rows =
    scenarios.status === "ready"
      ? [
          ...found,
          ...scenarios.data.filter(
            (s) =>
              !foundIds.has(s.scenario_id) &&
              (!q || `${s.flight_id} ${s.route} ${s.next_leg?.flight_id ?? ""}`.toLowerCase().includes(q)),
          ),
        ]
      : [];

  return (
    <section aria-label="Delayed flights" className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-center gap-1.5">
        <label className="flex h-8 min-w-0 flex-1 items-center gap-1.5 rounded-lg border border-input bg-input/30 px-2 focus-within:ring-2 focus-within:ring-ring/50">
          <Search aria-hidden className="size-4 shrink-0 text-muted-foreground" />
          <span className="sr-only">Filter the flights in this list</span>
          <input
            type="search"
            placeholder="Filter this list"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </label>
      </div>

      {/* Cause of delay, named in words. One pill slides to the chosen cause. */}
      <div
        role="radiogroup"
        aria-label="Filter by cause of delay"
        className="grid grid-cols-[auto_1fr_1fr] gap-0.5 rounded-lg border border-border bg-card/60 p-0.5"
      >
        {CAUSE_FILTERS.map(({ value, label, Icon }) => {
          const on = cause === value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => on || onCauseChange(value)}
              className={cn(
                "relative flex h-7 items-center justify-center gap-1.5 rounded-md px-2.5 text-xs font-medium whitespace-nowrap outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                on ? "text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {on && (
                <motion.span
                  layoutId="cause-filter"
                  aria-hidden
                  className="absolute inset-0 rounded-md border border-primary/50 bg-primary/15"
                />
              )}
              <Icon aria-hidden className={cn("relative size-3.5", on && "text-primary")} />
              <span className="relative">{label}</span>
            </button>
          );
        })}
      </div>

      {scenarios.status === "ready" && (
        <p className="text-xs text-muted-foreground tabular-nums">
          Showing {scenarios.data.length.toLocaleString("en-US")}
          {eligible !== null ? ` of ${eligible.toLocaleString("en-US")}` : ""} flights
        </p>
      )}

      {finder}

      <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 pb-1 max-lg:max-h-64">
        {scenarios.status === "loading" && <LoadingBlock label="Loading flights" lines={5} />}
        {scenarios.status === "error" && (
          <ErrorPanel
            title="Could not load flights"
            message={scenarios.message}
            unreachable={scenarios.unreachable}
            compact
            onRetry={onRetry}
          />
        )}
        {scenarios.status === "ready" && scenarios.data.length === 0 && (
          <EmptyPanel title="No delayed flights">
            {cause === "all" ? "None to recover." : `No ${CAUSE_LABEL[cause].toLowerCase()} delays.`}
          </EmptyPanel>
        )}
        {scenarios.status === "ready" && scenarios.data.length > 0 && rows.length === 0 && (
          <EmptyPanel title="No match">Nothing matches &ldquo;{query}&rdquo;.</EmptyPanel>
        )}
        {rows.length > 0 && (
          <ul className="space-y-1.5">
            {/* Cards a filter removes fade out while the rest glide together. */}
            <AnimatePresence initial={false} mode="popLayout">
            {rows.map((s) => {
              const selected = s.scenario_id === selectedId;
              const Icon = CAUSE_ICON[s.cause];
              return (
                <motion.li
                  key={s.scenario_id}
                  layout="position"
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.97 }}
                >
                  <motion.button
                    type="button"
                    onClick={() => onSelect(s.scenario_id)}
                    whileTap={{ scale: 0.985 }}
                    aria-pressed={selected}
                    aria-label={`${s.flight_id}, ${s.route}, due ${s.scheduled_arrival}, ${s.delay_minutes} minutes late, ${CAUSE_LABEL[s.cause]}`}
                    className="relative w-full rounded-xl border border-border bg-card/70 px-3 py-2.5 text-left outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {/* One ring, shared by every card, so it slides to the flight you pick. */}
                    {selected && (
                      <motion.span
                        layoutId="flight-selected"
                        aria-hidden
                        className="pointer-events-none absolute -inset-px rounded-xl border border-beacon ring-1 ring-beacon"
                      />
                    )}
                    <div className="flex items-center gap-2 text-sm">
                      <Icon aria-hidden className="size-3.5 text-muted-foreground" />
                      <span className="font-medium">{s.flight_id}</span>
                      {foundIds.has(s.scenario_id) && (
                        <span className="rounded bg-secondary px-1 text-[10px] font-medium text-secondary-foreground">Looked up</span>
                      )}
                      {s.has_recording && !hideRecordedTag && (
                        <span title="Saved model answers exist for this flight" className="rounded bg-info-soft px-1 text-[10px] font-medium text-info">
                          Recorded
                        </span>
                      )}
                      <span className="ml-auto flex items-center gap-1 font-display font-semibold text-beacon tabular-nums">
                        +{s.delay_minutes}
                        {s.delay_provenance && <ProvenanceMark provenance={s.delay_provenance} />}
                      </span>
                    </div>
                    <div className="mt-1">
                      <RouteCodes route={s.route} />
                    </div>
                    <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground tabular-nums">
                      <span>{s.scheduled_arrival}</span>
                      {s.next_leg && (
                        <span title={`Same aircraft flies ${s.next_leg.flight_id} at ${s.next_leg.scheduled_departure}; ${s.next_leg.delay_minutes ?? "unknown"} min of delay reaches it`}>
                          <CornerDownRight aria-hidden className="mr-0.5 inline size-3.5 align-[-2px]" />
                          <span className="sr-only">Next flight </span>
                          {s.next_leg.flight_id}{" "}
                          <span className="text-beacon">{s.next_leg.delay_minutes === null ? "unknown" : `+${s.next_leg.delay_minutes}`}</span>
                        </span>
                      )}
                    </div>
                  </motion.button>
                </motion.li>
              );
            })}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </section>
  );
}
