"use client";

import { useEffect, useRef, useState } from "react";
import { CircleCheck, CircleX, Hash, Info, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import type { Card as PlanCardData, PackageTerm, Run } from "@/lib/api-types";
import type { SignoffState } from "@/hooks/use-dashboard";
import { DECIDED_BY } from "@/hooks/use-dashboard";
import { TERM_LABEL, changedFieldLabel, isApproved, signoffStatusLabel } from "@/lib/labels";
import { ProvenanceBadge } from "@/components/dashboard/provenance-badge";
import { RuleList } from "@/components/dashboard/rule-line";

export function SignoffPanel({
  run,
  signoff,
  onApprove,
  onNewPlan,
}: {
  run: Run | null;
  signoff: SignoffState;
  onApprove: (decisions: boolean, requests: boolean) => void;
  onNewPlan: () => void;
}) {
  return (
    <Card size="sm" aria-labelledby="signoff-heading" role="region" className="overflow-visible">
      <CardHeader>
        <CardTitle id="signoff-heading">Sign off</CardTitle>
      </CardHeader>
      <CardContent>
        {run === null ? (
          <p className="text-sm text-muted-foreground">Pick a flight to see its recovery plan.</p>
        ) : run.decision.kind === "NO_DEAL" || !run.card ? (
          <p className="text-sm">
            <strong>Nothing to approve.</strong> No recovery plan passed the rules, so there is nothing to sign.
            The case is yours to handle.
          </p>
        ) : (
          // Keyed so the choices reset whenever a new plan is made.
          <SignoffForm key={run.run_id} run={run} card={run.card} signoff={signoff} onApprove={onApprove} onNewPlan={onNewPlan} />
        )}
      </CardContent>
    </Card>
  );
}

function SignoffForm({
  run,
  card,
  signoff,
  onApprove,
  onNewPlan,
}: {
  run: Run;
  card: PlanCardData;
  signoff: SignoffState;
  onApprove: (decisions: boolean, requests: boolean) => void;
  onNewPlan: () => void;
}) {
  // Nothing is ticked for you. Approving is a deliberate act.
  const [decide, setDecide] = useState(false);
  const [request, setRequest] = useState(false);
  const locked = signoff.status === "loading" || (signoff.status === "done" && isApproved(signoff.result.status));
  const none = !decide && !request;
  const approved = signoff.status === "done" && isApproved(signoff.result.status);
  // After any refusal the plan on screen is out of date until a new one is made.
  const stale = signoff.status === "done" && !approved;
  const loading = signoff.status === "loading";
  const modelOff = run.fallback_trigger === "llm_off" || run.faults.some((f) => f.kind === "model_off");

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onApprove(decide, request);
      }}
    >
      <SignoffResultView signoff={signoff} onNewPlan={onNewPlan} />

      <fieldset className="space-y-1.5" disabled={locked}>
        <legend className="text-sm font-semibold">You decide</legend>
        <p className="text-xs text-muted-foreground">The airline&rsquo;s own calls.</p>
        <ul className="space-y-0.5 text-sm">
          {card.airline_decisions.map((d) => (
            <li key={d.key}>
              <span className="text-muted-foreground">{d.label}: </span>
              <span className="font-medium">{d.value}</span> <ProvenanceBadge provenance={d.provenance} className="align-middle" />
            </li>
          ))}
        </ul>
        <div className="flex items-start gap-2 pt-1 text-sm">
          <Checkbox id="approve-decisions" checked={decide} onCheckedChange={(v) => setDecide(v)} className="mt-0.5" />
          <label htmlFor="approve-decisions" className="font-medium">
            I approve these decisions
          </label>
        </div>
      </fieldset>

      <fieldset className="space-y-1.5" disabled={locked}>
        <legend className="text-sm font-semibold">You request</legend>
        <p className="text-xs text-muted-foreground">
          Others decide these. The pilot in command keeps fuel and safety authority.
        </p>
        <ul className="space-y-0.5 text-sm">
          {card.requests.map((r) => (
            <li key={r.key}>
              <span className="text-muted-foreground">{r.label}: </span>
              <span className="font-medium">{r.value}</span> <ProvenanceBadge provenance={r.provenance} className="align-middle" />
              <span className="text-xs text-muted-foreground">to {r.to}</span>
            </li>
          ))}
        </ul>
        <div className="flex items-start gap-2 pt-1 text-sm">
          <Checkbox id="send-requests" checked={request} onCheckedChange={(v) => setRequest(v)} className="mt-0.5" />
          <label htmlFor="send-requests" className="font-medium">
            Send these requests
          </label>
        </div>
      </fieldset>

      {run.path === "fallback" && (
        <p className="flex items-start gap-1.5 rounded-lg border bg-muted/50 px-2 py-1.5 text-sm">
          {modelOff ? (
            <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          ) : (
            <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
          )}
          <span>
            Chosen by the rule-based fallback. {modelOff ? "The model is off, so the agents did not run." : "The agents did not agree."}
          </span>
        </p>
      )}
      {/* Stays on screen while the rest of the panel scrolls. */}
      <div className="sticky bottom-0 space-y-1 bg-card py-2">
        <Button type="submit" disabled={none || stale || loading || approved} className="w-full">
          {loading ? "Checking the rules again..." : approved ? "Approved" : "Approve"}
        </Button>
        {!approved && (
          <p className="text-xs text-muted-foreground">
            {stale
              ? "This plan is out of date. Make a new recovery plan to approve again."
              : none
                ? "Tick at least one box to approve."
                : "Sign-off checks the plan, the airport, the rules and this plan summary again before anything is issued."}
          </p>
        )}
      </div>
    </form>
  );
}

function SignoffResultView({ signoff, onNewPlan }: { signoff: SignoffState; onNewPlan: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  // Move focus to the outcome so a keyboard or screen reader user lands on it.
  useEffect(() => {
    if (signoff.status === "done" || signoff.status === "error") ref.current?.focus();
  }, [signoff]);
  return (
    <div ref={ref} tabIndex={-1} role="status" aria-live="polite" className="outline-none">
      {signoff.status === "error" && (
        <p className="rounded-lg border border-destructive/40 bg-destructive-soft p-2 text-sm">
          <strong>Sign-off failed.</strong> {signoff.message} Nothing was issued.
        </p>
      )}
      {signoff.status === "done" && isApproved(signoff.result.status) && (
        <div className="space-y-2 rounded-lg border border-success/40 bg-success-soft p-3 text-sm">
          <p className="flex items-center gap-1.5 font-semibold text-success">
            <CircleCheck aria-hidden className="size-4" />
            Requests issued, nothing executed
          </p>
          <p className="text-xs">
            Approved by {DECIDED_BY}. {signoffStatusLabel(signoff.result.status).detail} ATC and the pilot still
            have to act on the requests.
          </p>
          <TermList title="Airline decisions approved" items={signoff.result.airline_decisions} />
          <TermList title="Requests issued" items={signoff.result.requests} />
          <p className="flex items-start gap-1 font-mono text-xs break-all">
            <Hash aria-hidden className="mt-0.5 size-3 shrink-0" />
            Log head {signoff.result.log_head}
          </p>
        </div>
      )}
      {signoff.status === "done" && !isApproved(signoff.result.status) && <Refusal result={signoff.result} onNewPlan={onNewPlan} />}
    </div>
  );
}

function Refusal({
  result,
  onNewPlan,
}: {
  result: Extract<SignoffState, { status: "done" }>["result"];
  onNewPlan: () => void;
}) {
  const label = signoffStatusLabel(result.status);
  const state = result.changed_fields ?? [];
  const cardFields = result.changed_card_fields ?? [];
  return (
    <div className="space-y-2 rounded-lg border border-destructive/40 bg-destructive-soft p-3 text-sm">
      <p className="flex items-start gap-1.5 font-semibold text-destructive">
        <CircleX aria-hidden className="mt-0.5 size-4 shrink-0" />
        {label.title}
      </p>
      <p className="text-xs">Nothing was issued. {label.detail}</p>
      {state.length > 0 && (
        <div>
          <p className="text-xs font-semibold">Airport fields that changed</p>
          <ul className="list-disc pl-5">
            {state.map((c, i) => (
              <li key={i}>{changedFieldLabel(c, "state")}</li>
            ))}
          </ul>
        </div>
      )}
      {cardFields.length > 0 && (
        <div>
          <p className="text-xs font-semibold">Plan summary facts that changed</p>
          <ul className="list-disc pl-5">
            {cardFields.map((c, i) => (
              <li key={i}>{changedFieldLabel(c, "summary")}</li>
            ))}
          </ul>
        </div>
      )}
      {result.violations.length > 0 && (
        <div>
          <p className="text-xs font-semibold">Rules broken now</p>
          <RuleList rules={result.violations} result="broken" />
        </div>
      )}
      <Button type="button" variant="outline" size="sm" onClick={onNewPlan}>
        Make a new recovery plan
      </Button>
    </div>
  );
}

function TermList({ title, items }: { title: string; items: PackageTerm[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-semibold">{title}</p>
      <ul className="list-disc pl-5">
        {items.map((t) => (
          <li key={t.name}>
            {TERM_LABEL[t.name] ?? t.name}: {t.value}
          </li>
        ))}
      </ul>
    </div>
  );
}
