import { Ban, CircleCheck, ShieldX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Domain, Run, Turn, TurnResponse } from "@/lib/api-types";
import { DOMAIN_LABEL, DOMAIN_ROLE, FAULT_LABEL, agentReasonLabel, planLabel, publicReasonLabel } from "@/lib/labels";
import { EmptyPanel } from "@/components/dashboard/states";
import { OutcomeStrip } from "@/components/dashboard/outcome-strip";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RuleList } from "@/components/dashboard/rule-line";

const DOMAINS: Domain[] = ["atc", "pilot", "ground"];

/** A summary that is only plan IDs says nothing to a reader; the list stays on hover and in the log. */
const ONLY_PLAN_IDS = /^PKG-\w+(, PKG-\w+)*$/;

const TURN_HINT: Record<number, string> = {
  1: "Each agent answers alone, seeing only its own data.",
  2: "Each agent now sees which plans were removed and a general reason, with no private values.",
};

/** What an agent gave up between turns: plans it had declined and now accepts. */
function withdrawn(previous: TurnResponse | undefined, now: TurnResponse) {
  if (!previous || !now.accepted) return [];
  const accepted = new Set(now.accepted);
  return (previous.declined ?? []).filter((d) => accepted.has(d.package));
}

function byReason(items: { package: string; reason: string }[]) {
  const groups = new Map<string, string[]>();
  for (const item of items) groups.set(item.reason, [...(groups.get(item.reason) ?? []), item.package]);
  return groups;
}

/** The opposite move: plans it accepted before and no longer does. */
function dropped(previous: TurnResponse | undefined, now: TurnResponse) {
  if (!previous?.accepted || !now.accepted) return [];
  const accepted = new Set(now.accepted);
  return previous.accepted.filter((p) => !accepted.has(p));
}

function TurnColumns({ turn, run, previous }: { turn: Turn; run: Run; previous?: Turn }) {
  return (
    <section aria-labelledby={`turn-${turn.turn}`} className="space-y-2">
      <div>
        <h3 id={`turn-${turn.turn}`} className="text-sm font-semibold">
          Turn {turn.turn}
        </h3>
        <p className="text-xs text-muted-foreground">{TURN_HINT[turn.turn] ?? ""}</p>
      </div>
      <div className="grid gap-2 md:grid-cols-3">
        {DOMAINS.map((d) => {
          const r = turn.responses.find((x) => x.domain === d);
          const fault = run.faults.find((f) => f.domain === d && f.turn === turn.turn);
          return (
            <div key={d} className="rounded-lg border bg-card p-3 text-sm">
              <div className="flex items-baseline justify-between gap-2">
                <h4 className="font-semibold">{DOMAIN_LABEL[d]}</h4>
                <span className="text-xs text-muted-foreground">{DOMAIN_ROLE[d]}</span>
              </div>
              {r ? (
                <div className="mt-1.5 space-y-1.5">
                  <p title={ONLY_PLAN_IDS.test(r.ranking_summary) ? `Ranked first: ${r.ranking_summary}` : undefined}>
                    Would accept <strong>{r.acceptable_count}</strong> {r.acceptable_count === 1 ? "plan" : "plans"}
                  </p>
                  {!ONLY_PLAN_IDS.test(r.ranking_summary) && <p className="text-muted-foreground">{r.ranking_summary}</p>}
                  {r.reason_codes.length > 0 && (
                    <div>
                      <p className="text-xs font-medium">Its reasons</p>
                      <ul className="list-disc pl-4 text-muted-foreground">
                        {r.reason_codes.map((c, i) => (
                          <li key={i}>{agentReasonLabel(c)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {withdrawn(previous?.responses.find((x) => x.domain === d), r).length > 0 && (
                    <div>
                      <p className="text-xs font-medium">Withdrew its objection to</p>
                      <ul className="list-disc pl-4 text-muted-foreground">
                        {[...byReason(withdrawn(previous?.responses.find((x) => x.domain === d), r))].map(([reason, plans]) => (
                          <li key={reason} title={plans.join(", ")}>
                            {plans.length} {plans.length === 1 ? "plan" : "plans"} (was: {publicReasonLabel(reason)})
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {dropped(previous?.responses.find((x) => x.domain === d), r).length > 0 && (
                    <div>
                      <p className="text-xs font-medium">No longer accepts</p>
                      <p className="font-mono text-xs break-words text-muted-foreground">
                        {dropped(previous?.responses.find((x) => x.domain === d), r).join(", ")}
                      </p>
                    </div>
                  )}
                  {run.model_notes
                    .filter((n) => n.domain === d && n.turn === turn.turn)
                    .map((n, i) => (
                      <div key={i} className="rounded-md border border-dashed border-warning/50 p-2">
                        <Badge variant="outline" className="border-warning/50 text-warning">
                          Unverified
                        </Badge>
                        <p className="mt-1 text-xs font-medium">The model&rsquo;s own note</p>
                        <p className="text-muted-foreground">{n.text}</p>
                      </div>
                    ))}
                  {r.public_reason_classes.length > 0 && (
                    <div>
                      <p className="text-xs font-medium">Shared with the others</p>
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {r.public_reason_classes.map((c, i) => (
                          <Badge key={i} variant="outline" className="h-auto whitespace-normal">
                            {publicReasonLabel(c)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="mt-1.5 flex items-start gap-1.5 text-destructive">
                  <Ban aria-hidden className="mt-0.5 size-4 shrink-0" />
                  <span>
                    No answer.{" "}
                    {fault ? `${FAULT_LABEL[fault.kind]}: ${fault.message}` : "This agent did not respond."}
                  </span>
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function NegotiationView({ run }: { run: Run }) {
  // A plan the user slipped in is the point of that click, so its catch comes first and open.
  const injected = run.removed_packages.some((p) => p.injected);
  const removed = <RemovedPlans key={run.run_id} removed={run.removed_packages} total={run.removed_total} open={injected} />;
  return (
    <div className="space-y-5">
      <OutcomeStrip run={run} />
      {run.turns.some((t) => t.responses.length > 0) ? (
        <p className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/40 bg-warning-soft px-2.5 py-1.5 text-sm">
          <Badge variant="outline" className="border-warning/50 bg-background text-warning">
            Unverified
          </Badge>
          <span>
            Agent answers below are model output and are not verified. Only rule results are checked.
          </span>
        </p>
      ) : (
        <p className="rounded-lg border border-border px-2.5 py-1.5 text-sm">No agent answered in this run, so there is no model output here.</p>
      )}
      <p className="text-sm text-muted-foreground">
        {run.path === "consensus"
          ? "The agents agreed and the rules passed it. Agreement alone proves nothing: the rules decide what is allowed."
          : run.path === "fallback"
            ? run.fallback_trigger === "llm_off"
              ? "The model is off, so the agents did not run and code chose the plan. A fallback is never shown as a clean result."
              : "The agents did not reach a plan, so code chose one. A fallback is never shown as a clean result."
            : "No plan passed the rules, so the system stopped instead of guessing."}
      </p>
      {injected && removed}
      {run.turns.length === 0 ? (
        <EmptyPanel title="The agents did not run.">
          {run.faults.length > 0 ? run.faults[0].message : "No turns were recorded for this run."}
        </EmptyPanel>
      ) : (
        run.turns.map((t, i) => <TurnColumns key={t.turn} turn={t} run={run} previous={run.turns[i - 1]} />)
      )}
      <PlansConsidered run={run} />
      {!injected && removed}
    </div>
  );
}

/** What the flight was due to do, and, only if the agents answered, what they were offered. */
function PlansConsidered({ run }: { run: Run }) {
  const offered = run.offered_plans ?? [];
  const last = [...run.turns].reverse().find((t) => t.responses.length > 0);
  if (!run.original && offered.length === 0) return null;
  return (
    <section aria-label="Plans considered" className="space-y-2">
      {run.original && (
        <p className="flex flex-wrap items-center gap-1.5 text-sm">
          <span className="text-muted-foreground">Originally:</span> gate {run.original.gate_id}, due {run.original.due}
        </p>
      )}
      {offered.length > 0 && last && (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            <h3 className="text-sm font-semibold">Plans considered</h3>
            {run.packages_legal !== undefined && (
              <p className="text-xs text-muted-foreground tabular-nums">
                {offered.length} of {run.packages_legal} legal plans were offered to the agents
              </p>
            )}
          </div>
          <div className="overflow-x-auto rounded-lg border border-border">
            <Table className="text-xs">
              <TableHeader>
                <TableRow>
                  {["Gate", "Runway", "Lands", "Action"].map((h) => (
                    <TableHead key={h} className="h-8 px-2.5">
                      {h}
                    </TableHead>
                  ))}
                  {DOMAINS.map((d) => (
                    <TableHead key={d} className="h-8 px-2.5 text-center">
                      {DOMAIN_LABEL[d]}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {offered.map((plan) => (
                  <TableRow key={plan.package} aria-current={plan.chosen || undefined} className={plan.chosen ? "bg-primary/15 font-medium hover:bg-primary/20" : undefined}>
                    <TableCell className="px-2.5 py-1">{plan.gate_id}</TableCell>
                    <TableCell className="px-2.5 py-1">{plan.runway_id}</TableCell>
                    <TableCell className="px-2.5 py-1 tabular-nums">{plan.lands}</TableCell>
                    <TableCell className="px-2.5 py-1">
                      {plan.action.replaceAll("_", " ")}
                      {plan.chosen && (
                        <Badge variant="outline" className="ml-1.5">
                          Chosen
                        </Badge>
                      )}
                    </TableCell>
                    {DOMAINS.map((d) => {
                      const accepted = last.responses.find((r) => r.domain === d)?.accepted?.includes(plan.package);
                      return (
                        <TableCell key={d} className="px-2.5 py-1 text-center">
                          {accepted ? <CircleCheck aria-hidden className="mx-auto size-3.5 text-success" /> : <span aria-hidden className="text-muted-foreground">–</span>}
                          <span className="sr-only">{accepted ? "accepted" : "did not accept"}</span>
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <p className="text-xs text-muted-foreground">Ticks show who accepted each plan on turn {last.turn}, the last turn played.</p>
        </>
      )}
    </section>
  );
}

function RemovedPlans({ removed, total, open }: { removed: Run["removed_packages"]; total?: number; open: boolean }) {
  return (
    <details open={open} className="rounded-lg border bg-muted/40 p-3">
      <summary className="cursor-pointer">
        <h3 id="removed-heading" className="inline-flex items-center gap-1.5 text-sm font-semibold">
          <ShieldX aria-hidden className="size-4" />
          Plans the rules removed
        </h3>
      </summary>
      <p className="mt-1 text-xs text-muted-foreground">
        Code removes any plan that breaks a rule, then the agents choose from what is left. They cannot put one back.
        {total !== undefined && ` ${total} plans were illegal. One example of each kind of failure is shown.`}
      </p>
      {removed.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">No plan was removed.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {removed.map((p) => (
            <li key={p.package_id} className="rounded-md border bg-card p-2.5">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium" title={p.label}>
                  {planLabel(p.label)}
                </span>
                {p.injected && (
                  <Badge variant="outline" className="border-transparent bg-warning-soft text-warning">
                    Injected by you
                  </Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  {p.removed_in_turn === null ? "removed before any agent ran" : `removed in turn ${p.removed_in_turn}`}
                </span>
              </div>
              <RuleList rules={p.violations} result="broken" />
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
