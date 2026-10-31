import {
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
import type { Run, ScenarioSummary } from "@/lib/api-types";
import { CAUSE_LABEL, DOMAIN_LABEL, FAULT_LABEL, PATH_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ProvenanceMark } from "@/components/dashboard/provenance-badge";
import { RouteCodes } from "@/components/dashboard/flight-list";

const CAUSE_ICON = { weather: CloudLightning, late_aircraft: PlaneLanding } as const;
/** An icon for each fact key; unknown keys fall back to their label. */
const FACT_ICON: Record<string, LucideIcon> = { runway: PlaneLanding, gate: DoorOpen, handling: RotateCw };

/** A small label shown as an icon, with the word on hover and for screen readers. */
function IconLabel({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <span title={label} className="inline-flex text-muted-foreground">
      <Icon aria-hidden className="size-4" />
      <span className="sr-only">{label}</span>
    </span>
  );
}

/** Facts already shown in the header, so the grid skips them. */
const IN_HEADER = new Set(["arrival", "scheduled"]);

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
  onDetails,
}: {
  flight: ScenarioSummary | undefined;
  run: Run | null;
  onDetails: () => void;
}) {
  if (!flight) return null;
  const Icon = CAUSE_ICON[flight.cause];
  const card = run?.card ?? null;
  const arrival = card?.action_facts.find((f) => f.key === "arrival");
  const facts = card?.action_facts.filter((f) => !IN_HEADER.has(f.key)) ?? [];
  const deal = run?.decision.kind === "DEAL" ? run.decision : null;

  return (
    <section aria-label="Recovery plan" className="space-y-3">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{flight.flight_id}</span>
        <Icon aria-hidden className="size-3.5" />
        <span>{CAUSE_LABEL[flight.cause]}</span>
      </div>
      <RouteCodes route={flight.route} size="lg" />

      <dl className="grid grid-cols-3 items-end gap-2 tabular-nums">
        <div>
          <dt><IconLabel icon={CalendarClock} label="Due" /></dt>
          <dd className="font-display text-lg font-semibold text-muted-foreground line-through decoration-1">
            {flight.scheduled_arrival}
          </dd>
        </div>
        <div>
          <dt><IconLabel icon={Clock} label="Lands" /></dt>
          <dd className="flex items-center gap-1 font-display text-2xl font-semibold">
            {arrival?.value ?? "—"}
            {arrival && <ProvenanceMark provenance={arrival.provenance} />}
          </dd>
        </div>
        <div className="text-right">
          <dt><IconLabel icon={Hourglass} label="Minutes late" /></dt>
          <dd className="font-display text-lg font-semibold text-beacon">+{flight.delay_minutes}</dd>
        </div>
      </dl>

      {run && (
        <div className="flex flex-wrap gap-1.5">
          <Pill ok={run.path === "consensus"} icon={Users} title={PATH_LABEL[run.path]}>
            {run.path === "consensus" ? "Agreed" : run.path === "fallback" ? "Fallback" : "No deal"}
          </Pill>
          <Pill
            ok={run.decision.kind === "DEAL"}
            icon={run.decision.kind === "DEAL" ? ShieldCheck : ShieldX}
            title={run.decision.kind === "DEAL" ? "Every rule passes" : "No recovery plan passes the rules"}
          >
            Rules
          </Pill>
          {run.turns.length > 0 && (
            <span
              title={`${run.turns.length} of 2 negotiation turns used`}
              className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground tabular-nums"
            >
              <Repeat aria-hidden className="size-3.5" />
              {run.turns.length}/2
              <span className="sr-only">turns</span>
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
                <ProvenanceMark provenance={f.provenance} className="shrink-0" />
              </dd>
            </div>
          ))}
        </dl>
      )}

      {run && (
        <Button variant="ghost" size="sm" onClick={onDetails} className="-ml-2 text-muted-foreground">
          <ScrollText aria-hidden />
          {deal ? (
            <span title={`${deal.packages_legal} legal recovery plans of ${deal.packages_considered} considered`}>
              Why <span className="tabular-nums">{deal.packages_legal}/{deal.packages_considered}</span>
            </span>
          ) : (
            "Why no deal"
          )}
        </Button>
      )}
    </section>
  );
}
