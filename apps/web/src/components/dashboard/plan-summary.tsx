import {
  ArrowRight,
  CalendarClock,
  CircleAlert,
  CircleCheck,
  Clock,
  CloudLightning,
  DoorOpen,
  Hourglass,
  PlaneLanding,
  Repeat,
  RotateCw,
  ScrollText,
  ShieldCheck,
  ShieldX,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { Provenance, Run, ScenarioSummary } from "@/lib/api-types";
import { ACTION_LABEL, CAUSE_LABEL, DOMAIN_LABEL, FAULT_LABEL, PATH_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { RouteCodes } from "@/components/dashboard/flight-list";

const CAUSE_ICON = { weather: CloudLightning, late_aircraft: PlaneLanding } as const;
/** An icon for each fact key; unknown keys fall back to their label. */
const FACT_ICON: Record<string, LucideIcon> = { runway: PlaneLanding, gate: DoorOpen, handling: RotateCw };

/** A small label: an icon with its word beside it, so both read from a distance. */
function IconLabel({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Icon aria-hidden className="size-3.5" />
      {label}
    </span>
  );
}

/** Facts already shown in the header, so the grid skips them. */
const IN_HEADER = new Set(["arrival", "scheduled"]);

/**
 * When the plan lands: the mock's own "arrival" fact, or the clock the API gives
 * beside the arrival slot, such as "runway R1 at minute 1319 (21:59)".
 */
export function landingFact(card: Run["card"] | undefined): { clock: string; provenance: Provenance } | null {
  const arrival = card?.action_facts.find((f) => f.key === "arrival");
  if (arrival) return { clock: arrival.value, provenance: arrival.provenance };
  const slot = card?.action_facts.find((f) => f.key === "slot");
  const clock = slot && /\((\d\d:\d\d)\)/.exec(slot.value)?.[1];
  return slot && clock ? { clock, provenance: slot.provenance } : null;
}

/**
 * Minutes from one "HH:MM" clock to another, taking the shorter way round
 * midnight, so 23:55 to 00:20 is +25, not -1415. Null if either is unreadable.
 */
function minutesBetween(from: string, to: string): number | null {
  const at = (clock: string) => {
    const m = /^(\d{1,2}):(\d{2})$/.exec(clock.trim());
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  };
  const a = at(from);
  const b = at(to);
  if (a === null || b === null) return null;
  const d = (((b - a) % 1440) + 1440) % 1440;
  return d > 720 ? d - 1440 : d;
}

function Pill({ ok, icon: Icon, title, children }: { ok: boolean; icon: LucideIcon; title: string; children: React.ReactNode }) {
  const Mark = ok ? CircleCheck : CircleAlert;
  return (
    <span title={title} className="inline-flex items-center gap-1 rounded-full border border-border bg-background/40 px-2 py-0.5 text-xs">
      <Icon aria-hidden className="size-3.5 text-muted-foreground" />
      {children}
      <Mark aria-hidden className={cn("size-3.5", ok ? "text-success" : "text-destructive")} />
    </span>
  );
}

/**
 * The top of the right panel: which flight, when it lands now, and how the
 * plan was reached. Detail lives in the drawer.
 */
export function PlanSummary({
  flight,
  run,
  pending = false,
  onDetails,
}: {
  flight: ScenarioSummary | undefined;
  run: Run | null;
  /** A recovery plan is being made: read "planning", not "no plan". */
  pending?: boolean;
  onDetails: () => void;
}) {
  if (!flight) return null;
  const Icon = CAUSE_ICON[flight.cause];
  const card = run?.card ?? null;
  const arrival = landingFact(card);
  // The landing time is in the header, so the summary's slot needs only its runway.
  const facts =
    card?.action_facts
      .filter((f) => !IN_HEADER.has(f.key))
      .map((f) =>
        f.key === "slot" && run?.decision.kind === "DEAL"
          ? { ...f, label: "Runway", value: run.decision.package.runway_id }
          : f.key === "action"
            ? { ...f, label: "Approach", value: ACTION_LABEL[f.value] ?? f.value }
            : f,
      ) ?? [];
  const deal = run?.decision.kind === "DEAL" ? run.decision : null;
  const change = arrival ? minutesBetween(flight.scheduled_arrival, arrival.clock) : null;
  // A system fault judged no plan illegal, so it must not read as "no plan passes".
  const noGoLabel =
    run?.decision.kind === "NO_GO" && run.decision.reason_type === "SYSTEM_FAULT"
      ? "No plan: system fault"
      : "No plan passes the rules";

  return (
    <section aria-label="Recovery plan" className="space-y-3">
      {/* pr-8 keeps clear of the panel's hide button in the top-right corner. */}
      <div className="flex items-center gap-2 pr-8 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{flight.flight_id}</span>
        <Icon aria-hidden className="size-3.5" />
        <span>{CAUSE_LABEL[flight.cause]}</span>
        <span className="ml-auto inline-flex items-center gap-1 tabular-nums" title="How late the flight is running">
          <Hourglass aria-hidden className="size-3.5" />
          <span className="font-semibold text-beacon">+{flight.delay_minutes} min</span> late
        </span>
      </div>
      <RouteCodes route={flight.route} size="lg" />

      {/* Before and after: the time the flight was scheduled to land, and the
          time it lands with this recovery plan, joined by the change between them. */}
      <div role="group" aria-label="Due and landing time" className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 rounded-xl border border-border bg-background/40 p-3 tabular-nums">
        <div>
          <IconLabel icon={CalendarClock} label="Due" />
          <p className="font-display text-xl font-semibold text-muted-foreground">{flight.scheduled_arrival}</p>
        </div>

        <div aria-hidden className="flex flex-col items-center gap-0.5 px-1">
          <span className={cn("text-xs font-semibold whitespace-nowrap", change === null ? "text-muted-foreground" : "text-beacon")}>
            {change === null ? (pending ? "planning" : "no plan") : `${change >= 0 ? "+" : "−"}${Math.abs(change)} min`}
          </span>
          <span className="flex items-center text-muted-foreground">
            <span className="h-px w-8 bg-gradient-to-r from-muted-foreground/30 to-beacon/70" />
            <ArrowRight className="-ml-1 size-3.5 text-beacon" />
          </span>
        </div>

        <div className="text-right">
          <div className="flex justify-end">
            <IconLabel icon={Clock} label={arrival ? "Lands" : pending ? "Planning" : "No plan"} />
          </div>
          <p className="flex items-center justify-end gap-1 font-display text-2xl font-semibold">
            {arrival?.clock ?? "—"}
          </p>
        </div>
        {change !== null && (
          <span className="sr-only">
            Lands {Math.abs(change)} minutes {change >= 0 ? "later" : "earlier"} than scheduled.
          </span>
        )}
      </div>

      {run && (
        <div className="flex flex-wrap gap-1.5">
          <Pill ok={run.path === "consensus"} icon={Users} title={PATH_LABEL[run.path]}>
            {run.path === "consensus" && run.turns.length > 0
              ? `Agents agreed in ${run.turns.length} ${run.turns.length === 1 ? "turn" : "turns"}`
              : PATH_LABEL[run.path]}
          </Pill>
          <Pill
            ok={run.decision.kind === "DEAL"}
            icon={run.decision.kind === "DEAL" ? ShieldCheck : ShieldX}
            title={run.decision.kind === "DEAL" ? "Every safety rule passes" : noGoLabel}
          >
            {run.decision.kind === "DEAL" ? "Safety rules pass" : noGoLabel}
          </Pill>
          {run.path !== "consensus" && run.turns.length > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground tabular-nums">
              <Repeat aria-hidden className="size-3.5" />
              {run.turns.length} {run.turns.length === 1 ? "turn" : "turns"}
            </span>
          )}
        </div>
      )}

      {run && run.faults.length > 0 && (
        <ul className="space-y-1" aria-label="Faults">
          {run.faults.map((f, i) => (
            <li key={i} title={f.message} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CircleAlert aria-hidden className="size-3.5 shrink-0" />
              {FAULT_LABEL[f.kind]}
              {f.domain ? `: ${DOMAIN_LABEL[f.domain]}` : ""}
              <span className="sr-only">. {f.message}</span>
            </li>
          ))}
        </ul>
      )}

      {facts.length > 0 && (
        <dl className="grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-border bg-border">
          {facts.map((f) => (
            <div key={f.key} className="bg-card px-2.5 py-2">
              <dt className="text-xs text-muted-foreground">
                {FACT_ICON[f.key] ? <IconLabel icon={FACT_ICON[f.key]} label={f.label} /> : f.label}
              </dt>
              <dd className="mt-0.5 flex items-start gap-1 font-display text-base leading-tight font-semibold">
                <span className="min-w-0">{f.value}</span>
              </dd>
            </div>
          ))}
        </dl>
      )}

      {run && (
        <Button variant="ghost" size="sm" onClick={onDetails} className="-ml-2 text-muted-foreground">
          <ScrollText aria-hidden />
          {deal ? `Why this plan (${deal.packages_legal} of ${deal.packages_considered} passed)` : "Why no plan passed"}
        </Button>
      )}
    </section>
  );
}
