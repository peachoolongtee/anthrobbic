"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronUp, PlaneTakeoff } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { Cause, ScenarioSummary } from "@/lib/api-types";
import { airlineName, airportCity, airportName, routeCodes } from "@/lib/airports";
import { CAUSE_LABEL } from "@/lib/labels";
import { OUTCOME, type Outcome } from "@/lib/outcome";
import { cn } from "@/lib/utils";
import { ProvenanceMark } from "@/components/dashboard/provenance-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const PAGE_SIZE = 10;

const MotionRow = motion.create(TableRow);

const CAUSE_DOT: Record<Cause, string> = { weather: "bg-info", late_aircraft: "bg-primary" };

// Best outcome first when sorting by outcome; a flight still running sorts last.
const OUTCOME_ORDER: Outcome[] = ["agreed", "fallback", "no_go", "fault", "failed"];

type SortKey = "flight" | "route" | "arrival" | "delay" | "cause" | "outcome";

const COLUMNS: { key: SortKey | "next"; label: string; width: string }[] = [
  { key: "flight", label: "Flight", width: "w-[17%]" },
  { key: "route", label: "Route", width: "w-[20%]" },
  { key: "arrival", label: "Arrival", width: "w-[10%]" },
  { key: "delay", label: "Delay", width: "w-[9%]" },
  { key: "cause", label: "Cause", width: "w-[13%]" },
  { key: "outcome", label: "Outcome", width: "w-[16%]" },
  { key: "next", label: "Next leg", width: "w-[15%]" },
];

function flightHref(id: string) {
  return `/dashboard/flights?flight=${encodeURIComponent(id)}`;
}

/** A small ring joined to a dashed rule, as in a departure board. `flip` puts the ring at the far end. */
function Connector({ flip = false }: { flip?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex items-center gap-0.5 opacity-50 before:size-1.5 before:rounded-full before:border before:border-muted-foreground after:h-px after:w-3 after:border-t after:border-dashed after:border-muted-foreground",
        flip && "before:order-1",
      )}
    />
  );
}

/** The outcome badge. It morphs from a pulsing placeholder into the result when the run finishes. */
function OutcomeCell({ outcome }: { outcome: Outcome | undefined }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      {outcome ? (
        <motion.span key={outcome} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
          <Badge variant="outline" className={cn("gap-1.5 font-normal", OUTCOME[outcome].text)}>
            <span aria-hidden className={cn("size-1.5 rounded-full", OUTCOME[outcome].dot)} />
            {OUTCOME[outcome].label}
          </Badge>
        </motion.span>
      ) : (
        <motion.span
          key="running"
          aria-label="Running"
          className="block h-5 w-24 rounded-full bg-muted"
          animate={{ opacity: [0.4, 0.9, 0.4] }}
          transition={{ duration: 1.4, repeat: Infinity }}
        />
      )}
    </AnimatePresence>
  );
}

/**
 * The flights in a sortable table. Pointing at a row lights its route on the
 * globe through `onActive`; selecting it opens the flight. Airline and city
 * names come from the organiser's airlines.csv and airports.csv. `outcomes`
 * holds each flight's recorded run; a flight missing from it is still running.
 */
export function ArrivalsTable({
  flights,
  outcomes,
  activeId,
  onActive,
}: {
  flights: ScenarioSummary[];
  outcomes: Record<string, Outcome>;
  activeId: string | null;
  onActive: (id: string | null) => void;
}) {
  const router = useRouter();
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "arrival", desc: false });
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    const value: Record<SortKey, (f: ScenarioSummary) => string | number> = {
      flight: (f) => f.flight_id,
      route: (f) => f.route,
      arrival: (f) => f.scheduled_arrival,
      delay: (f) => f.delay_minutes,
      cause: (f) => CAUSE_LABEL[f.cause],
      outcome: (f) => (outcomes[f.scenario_id] ? OUTCOME_ORDER.indexOf(outcomes[f.scenario_id]) : OUTCOME_ORDER.length),
    };
    const pick = value[sort.key];
    const dir = sort.desc ? -1 : 1;
    return [...flights].sort((a, b) => {
      const x = pick(a);
      const y = pick(b);
      return dir * (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y)));
    });
  }, [flights, outcomes, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const shown = sorted.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);
  const first = sorted.length ? current * PAGE_SIZE + 1 : 0;
  const last = current * PAGE_SIZE + shown.length;

  function toggle(key: SortKey) {
    setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key === "delay" }));
    setPage(0);
  }

  return (
    <div className="-mx-2 overflow-hidden rounded-xl border border-border bg-background/40">
      <Table className="min-w-[46rem] table-fixed">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {COLUMNS.map((col) => {
              const sortable = col.key !== "next";
              const active = sort.key === col.key;
              return (
                <TableHead
                  key={col.key}
                  className={cn("h-10 px-3 text-xs", col.width)}
                  aria-sort={active ? (sort.desc ? "descending" : "ascending") : sortable ? "none" : undefined}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggle(col.key as SortKey)}
                      className="-mx-1 flex h-full w-full items-center justify-between gap-2 rounded px-1 outline-none select-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {col.label}
                      {/* One chevron that turns over when the order flips. */}
                      <AnimatePresence initial={false}>
                        {active && (
                          <motion.span
                            key="chevron"
                            initial={{ opacity: 0, scale: 0.6 }}
                            animate={{ opacity: 0.8, scale: 1, rotate: sort.desc ? 180 : 0 }}
                            exit={{ opacity: 0, scale: 0.6 }}
                            className="shrink-0"
                          >
                            <ChevronUp aria-hidden className="size-4" />
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </button>
                  ) : (
                    col.label
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody onMouseLeave={() => onActive(null)}>
          {/* Rows glide to their new places when the order changes; a new page fades in. */}
          <AnimatePresence initial={false} mode="popLayout">
          {shown.map((flight) => {
            const codes = routeCodes(flight.route);
            const airline = airlineName(flight.flight_id);
            return (
              <MotionRow
                key={flight.scenario_id}
                layout="position"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                onMouseEnter={() => onActive(flight.scenario_id)}
                onClick={() => router.push(flightHref(flight.scenario_id))}
                className={cn("cursor-pointer", activeId === flight.scenario_id && "bg-muted/50")}
              >
                <TableCell className="px-3 py-2.5">
                  <Link
                    href={flightHref(flight.scenario_id)}
                    onFocus={() => onActive(flight.scenario_id)}
                    onBlur={() => onActive(null)}
                    className="rounded font-mono font-medium text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {flight.flight_id}
                  </Link>
                  <span className="block truncate text-xs text-muted-foreground/80">{airline ?? "Airline not in airlines.csv"}</span>
                </TableCell>
                <TableCell className="px-3 py-2.5">
                  <span className="font-display font-medium whitespace-nowrap">{flight.route.replace(" to ", " → ")}</span>
                  {codes && (
                    <span
                      className="block truncate text-xs text-muted-foreground/80"
                      title={codes.map((c) => airportName(c) ?? c).join(" to ")}
                    >
                      {codes.map((c) => airportCity(c) ?? c).join(" → ")}
                    </span>
                  )}
                </TableCell>
                <TableCell className="px-3 py-2.5">
                  <span className="flex items-center gap-1.5 tabular-nums">
                    {flight.scheduled_arrival}
                    <ProvenanceMark provenance="real" />
                    <span className="sr-only">scheduled</span>
                  </span>
                </TableCell>
                <TableCell className="px-3 py-2.5">
                  <span className="flex items-center gap-1.5">
                    <Connector flip />
                    <span className="font-display font-semibold text-beacon tabular-nums">+{flight.delay_minutes}</span>
                    <span className="sr-only"> minutes of delay</span>
                    {flight.delay_provenance && <ProvenanceMark provenance={flight.delay_provenance} />}
                  </span>
                </TableCell>
                <TableCell className="px-3 py-2.5">
                  <Badge variant="outline" className="gap-1.5 font-normal">
                    <span aria-hidden className={cn("size-1.5 rounded-full", CAUSE_DOT[flight.cause])} />
                    {CAUSE_LABEL[flight.cause]}
                  </Badge>
                </TableCell>
                <TableCell className="px-3 py-2.5">
                  <OutcomeCell outcome={outcomes[flight.scenario_id]} />
                </TableCell>
                <TableCell className="px-3 py-2.5">
                  {flight.next_leg ? (
                    <span className="flex items-center gap-1">
                      <Badge
                        variant="outline"
                        className="gap-1 font-normal tabular-nums"
                        title={`Same aircraft flies ${flight.next_leg.flight_id} (${flight.next_leg.route}) at ${flight.next_leg.scheduled_departure}`}
                      >
                        <PlaneTakeoff aria-hidden />
                        {flight.next_leg.flight_id}
                        <span className="text-beacon">
                          {flight.next_leg.delay_minutes === null ? "unknown" : `+${flight.next_leg.delay_minutes}`}
                        </span>
                      </Badge>
                      {flight.next_leg.provenance && <ProvenanceMark provenance={flight.next_leg.provenance} />}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">None that day</span>
                  )}
                </TableCell>
              </MotionRow>
            );
          })}
          </AnimatePresence>
        </TableBody>
      </Table>
      <footer className="flex items-center justify-between gap-2 border-t border-border px-3 py-2 text-sm">
        <p className="text-muted-foreground tabular-nums">
          Viewing {first}–{last} of <strong className="font-medium text-foreground">{sorted.length}</strong> flights
        </p>
        {pages > 1 && (
          <nav aria-label="Pages" className="flex gap-1">
            <Button size="sm" variant="outline" disabled={current === 0} onClick={() => setPage(current - 1)}>
              Previous
            </Button>
            <Button size="sm" variant="outline" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
              Next
            </Button>
          </nav>
        )}
      </footer>
    </div>
  );
}
