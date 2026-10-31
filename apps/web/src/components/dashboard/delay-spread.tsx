"use client";

import { useEffect, useState } from "react";
import { api, describeError } from "@/lib/api";
import type { DelaySpread } from "@/lib/api-types";
import { ProvenanceBadge } from "@/components/dashboard/provenance-badge";
import { LoadingBlock } from "@/components/dashboard/states";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; spread: DelaySpread };

/**
 * The same aircraft's later flights that day, from the schedule, with the knock-on
 * this plan's arrival would cause. A projection from scheduled data, and it says so.
 * Mount with a `key` of the run.
 */
export function DelaySpreadView({ runId }: { runId: string }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let live = true;
    api
      .getSpread(runId)
      .then((spread) => live && setState({ status: "ready", spread }))
      .catch((err) => live && setState({ status: "error", message: describeError(err) }));
    return () => {
      live = false;
    };
  }, [runId]);

  if (state.status === "loading") return <LoadingBlock label="Loading the delay spread" lines={2} />;

  return (
    <section aria-labelledby="spread-heading" className="rounded-xl border border-border bg-card p-3 text-sm">
      <h3 id="spread-heading" className="font-display font-semibold">
        Delay spread: this aircraft&rsquo;s later flights that day
      </h3>
      {state.status === "error" ? (
        <p className="mt-1 text-muted-foreground">Could not load it. {state.message}</p>
      ) : (
        <>
          <p className="mt-0.5 text-xs text-muted-foreground">{state.spread.note}</p>
          {state.spread.plan_arrival && (
            <p className="mt-1.5 flex flex-wrap items-center gap-1.5">
              At the gate under this plan: <strong className="tabular-nums">{state.spread.plan_arrival}</strong>
              {state.spread.plan_arrival_provenance && <ProvenanceBadge provenance={state.spread.plan_arrival_provenance} />}
            </p>
          )}
          {state.spread.legs.length === 0 ? (
            <p className="mt-1.5 text-muted-foreground">No later flight for this aircraft that day.</p>
          ) : (
            <ul className="mt-1.5 divide-y divide-border">
              {state.spread.legs.map((leg) => (
                <li key={`${leg.flight_id}-${leg.scheduled_departure}`} className="py-1.5">
                  <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-medium">{leg.flight_id}</span>
                    <span>{leg.route}</span>
                    <span className="tabular-nums text-muted-foreground">departs {leg.scheduled_departure}</span>
                    <ProvenanceBadge provenance={leg.provenance} />
                  </p>
                  {leg.projection ? (
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span>
                        Scheduled knock-on <strong className="tabular-nums">{leg.projection.knock_on_min} min</strong>, earliest
                        departure <span className="tabular-nums">{leg.projection.earliest_departure}</span>
                      </span>
                      <ProvenanceBadge provenance={leg.projection.provenance} />
                      <span className="text-xs text-muted-foreground">
                        with a {leg.projection.turnaround_min} min minimum turnaround
                      </span>
                      <ProvenanceBadge provenance={leg.projection.turnaround_provenance} />
                    </p>
                  ) : (
                    <p className="mt-0.5 text-muted-foreground">{leg.unprojected_reason}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
