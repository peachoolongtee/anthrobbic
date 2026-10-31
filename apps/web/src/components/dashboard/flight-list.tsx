"use client";

import { CloudLightning, Layers, PlaneLanding, Search } from "lucide-react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Cause, ScenarioSummary } from "@/lib/api-types";
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
}: {
  scenarios: ScenarioLoad;
  cause: Cause | "all";
  onCauseChange: (c: Cause | "all") => void;
  query: string;
  onQueryChange: (q: string) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRetry: () => void;
}) {
  const q = query.trim().toLowerCase();
  const rows =
    scenarios.status === "ready"
      ? scenarios.data.filter(
          (s) => !q || `${s.flight_id} ${s.route} ${s.next_leg?.flight_id ?? ""}`.toLowerCase().includes(q),
        )
      : [];

  return (
    <section aria-label="Delayed flights" className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-center gap-1.5">
        <label className="flex h-8 min-w-0 flex-1 items-center gap-1.5 rounded-lg border border-input bg-input/30 px-2 focus-within:ring-2 focus-within:ring-ring/50">
          <Search aria-hidden className="size-4 shrink-0 text-muted-foreground" />
          <span className="sr-only">Search flights</span>
          <input
            type="search"
            placeholder="Search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </label>
        <ToggleGroup
          aria-label="Filter by cause of delay"
          variant="outline"
          size="sm"
          spacing={0}
          value={[cause]}
          onValueChange={(v) => {
            const next = v[0] as Cause | "all" | undefined;
            if (next && next !== cause) onCauseChange(next);
          }}
        >
          <ToggleGroupItem value="all" aria-label="All causes" title="All">
            <Layers aria-hidden />
          </ToggleGroupItem>
          <ToggleGroupItem value="weather" aria-label="Weather" title="Weather">
            <CloudLightning aria-hidden />
          </ToggleGroupItem>
          <ToggleGroupItem value="late_aircraft" aria-label="Late aircraft" title="Late aircraft">
            <PlaneLanding aria-hidden />
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 pb-1">
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
            {rows.map((s) => {
              const selected = s.scenario_id === selectedId;
              const Icon = CAUSE_ICON[s.cause];
              return (
                <li key={s.scenario_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(s.scenario_id)}
                    aria-pressed={selected}
                    aria-label={`${s.flight_id}, ${s.route}, due ${s.scheduled_arrival}, ${s.delay_minutes} minutes late, ${CAUSE_LABEL[s.cause]}`}
                    className={cn(
                      "w-full rounded-xl border bg-card/70 px-3 py-2.5 text-left outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
                      selected ? "border-beacon ring-1 ring-beacon" : "border-border",
                    )}
                  >
                    <div className="flex items-center gap-2 text-sm">
                      <Icon aria-hidden className="size-3.5 text-muted-foreground" />
                      <span className="font-medium">{s.flight_id}</span>
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
                        <span title={`Same aircraft flies ${s.next_leg.flight_id} at ${s.next_leg.scheduled_departure}; ${s.next_leg.delay_minutes} min of delay reaches it`}>
                          Next {s.next_leg.flight_id}{" "}
                          <span className="text-warning">+{s.next_leg.delay_minutes}</span>
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
