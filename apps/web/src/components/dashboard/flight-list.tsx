"use client";

import { ArrowRight, CornerDownRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Cause, ScenarioSummary } from "@/lib/api-types";
import { CAUSE_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { EmptyPanel, ErrorPanel, LoadingBlock } from "@/components/dashboard/states";
import { ProvenanceBadge } from "@/components/dashboard/provenance-badge";

type ScenarioLoad =
  | { status: "loading" }
  | { status: "error"; message: string; unreachable: boolean }
  | { status: "ready"; data: ScenarioSummary[] };

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
    <section aria-labelledby="flights-heading" className="flex min-h-0 flex-col gap-3">
      <div>
        <h2 id="flights-heading" className="text-sm font-semibold">
          Delayed flights
        </h2>
        <p className="text-xs text-muted-foreground">Pick one to build its recovery plan.</p>
      </div>
      <div className="space-y-2">
        <label className="sr-only" htmlFor="flight-search">
          Search flights
        </label>
        <Input
          id="flight-search"
          type="search"
          placeholder="Search flight or route"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
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
          className="w-full"
        >
          <ToggleGroupItem value="all" className="flex-1">
            All
          </ToggleGroupItem>
          <ToggleGroupItem value="weather" className="flex-1">
            Weather
          </ToggleGroupItem>
          <ToggleGroupItem value="late_aircraft" className="flex-1" aria-label="Late aircraft">
            Late
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {scenarios.status === "loading" && <LoadingBlock label="Loading flights" lines={6} />}
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
            {cause === "all"
              ? "The API returned no flights to recover."
              : `No ${CAUSE_LABEL[cause].toLowerCase()} delays. Try All.`}
          </EmptyPanel>
        )}
        {scenarios.status === "ready" && scenarios.data.length > 0 && rows.length === 0 && (
          <EmptyPanel title="No match">Nothing matches &ldquo;{query}&rdquo;. Clear the search to see all flights.</EmptyPanel>
        )}
        {rows.length > 0 && (
          <ul className="space-y-1.5">
            {rows.map((s) => {
              const selected = s.scenario_id === selectedId;
              return (
                <li key={s.scenario_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(s.scenario_id)}
                    aria-pressed={selected}
                    className={cn(
                      "w-full rounded-lg border bg-card p-2.5 text-left text-sm outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                      selected && "border-foreground bg-muted",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{s.flight_id}</span>
                      <span className="flex flex-wrap justify-end gap-1">
                        {s.has_recording && <Badge variant="secondary">Recorded</Badge>}
                        <Badge variant="outline">{CAUSE_LABEL[s.cause]}</Badge>
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center justify-between gap-2 text-muted-foreground">
                      <span className="truncate">{s.route}</span>
                      <span>due {s.scheduled_arrival}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-1.5">
                      <span className="font-medium">{s.delay_minutes} min late</span>
                      {s.delay_provenance && <ProvenanceBadge provenance={s.delay_provenance} />}
                    </div>
                    {s.next_leg ? (
                      <div className="mt-1.5 flex items-start gap-1.5 border-t pt-1.5 text-xs text-muted-foreground">
                        <CornerDownRight aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                        <span>
                          Same aircraft next: <span className="font-medium text-foreground">{s.next_leg.flight_id}</span>{" "}
                          <ArrowRight aria-hidden className="inline size-3" /> departs {s.next_leg.scheduled_departure},{" "}
                          <span className="font-medium text-foreground">
                            {s.next_leg.delay_minutes === null ? "unknown" : `${s.next_leg.delay_minutes} min`}
                          </span>{" "}
                          of delay reaches it{" "}
                          {(s.next_leg.delay_provenance ?? s.next_leg.provenance) && (
                            <ProvenanceBadge
                              provenance={(s.next_leg.delay_provenance ?? s.next_leg.provenance)!}
                              className="ml-0.5 align-middle"
                            />
                          )}
                        </span>
                      </div>
                    ) : (
                      <div className="mt-1.5 border-t pt-1.5 text-xs text-muted-foreground">
                        No next flight for this aircraft that day.
                      </div>
                    )}
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
