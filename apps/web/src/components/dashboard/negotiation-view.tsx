import { Ban, ShieldX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Domain, Run, Turn } from "@/lib/api-types";
import { DOMAIN_LABEL, DOMAIN_ROLE, FAULT_LABEL } from "@/lib/labels";
import { EmptyPanel } from "@/components/dashboard/states";
import { RuleList } from "@/components/dashboard/rule-line";

const DOMAINS: Domain[] = ["atc", "pilot", "ground"];

const TURN_HINT: Record<number, string> = {
  1: "Each agent answers alone, seeing only its own data.",
  2: "Each agent now sees which plans were removed and a general reason, with no private values.",
};

function TurnColumns({ turn, run }: { turn: Turn; run: Run }) {
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
                  <p>
                    Would accept <strong>{r.acceptable_count}</strong> {r.acceptable_count === 1 ? "plan" : "plans"}
                  </p>
                  <p className="text-muted-foreground">{r.ranking_summary}</p>
                  {r.reason_codes.length > 0 && (
                    <div>
                      <p className="text-xs font-medium">Its reasons</p>
                      <ul className="list-disc pl-4 text-muted-foreground">
                        {r.reason_codes.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {r.public_reason_classes.length > 0 && (
                    <div>
                      <p className="text-xs font-medium">Shared with the others</p>
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {r.public_reason_classes.map((c, i) => (
                          <Badge key={i} variant="outline">
                            {c}
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
  return (
    <div className="space-y-5">
      <p className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/40 bg-warning-soft px-2.5 py-1.5 text-sm">
        <Badge variant="outline" className="border-warning/50 bg-background text-warning">
          Unverified
        </Badge>
        <span>
          Agent answers below are model output and are not verified. Only rule results are checked.
        </span>
      </p>
      <p className="text-sm text-muted-foreground">
        {run.path === "consensus"
          ? "The agents agreed and the rules passed it. Agreement alone proves nothing: the rules decide what is allowed."
          : run.path === "fallback"
            ? run.fallback_trigger === "llm_off"
              ? "The model is off, so the agents did not run and code chose the plan. A fallback is never shown as a clean result."
              : "The agents did not reach a plan, so code chose one. A fallback is never shown as a clean result."
            : "No plan passed the rules, so the system stopped instead of guessing."}
      </p>
      <RemovedPlans removed={run.removed_packages} total={run.removed_total} />
      {run.turns.length === 0 ? (
        <EmptyPanel title="The agents did not negotiate">
          {run.faults.length > 0 ? run.faults[0].message : "No turns were recorded for this run."}
        </EmptyPanel>
      ) : (
        run.turns.map((t) => <TurnColumns key={t.turn} turn={t} run={run} />)
      )}
    </div>
  );
}

function RemovedPlans({ removed, total }: { removed: Run["removed_packages"]; total?: number }) {
  return (
    <section aria-labelledby="removed-heading" className="rounded-lg border bg-muted/40 p-3">
      <h3 id="removed-heading" className="flex items-center gap-1.5 text-sm font-semibold">
        <ShieldX aria-hidden className="size-4" />
        Plans the rules removed
      </h3>
      <p className="text-xs text-muted-foreground">
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
                <span className="font-medium">{p.label}</span>
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
    </section>
  );
}
