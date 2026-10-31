"use client";

import { useState } from "react";
import { CircleCheck, CircleX, Hash } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import type { Card as PlanCardData, Run } from "@/lib/api-types";
import type { SignoffState } from "@/hooks/use-dashboard";
import { DECIDED_BY } from "@/hooks/use-dashboard";
import { isApproved, signoffStatusLabel } from "@/lib/labels";
import { ProvenanceBadge } from "@/components/dashboard/provenance-badge";
import { RuleList } from "@/components/dashboard/rule-line";
import { LoadingBlock } from "@/components/dashboard/states";

export function SignoffPanel({
  run,
  signoff,
  onApprove,
  onNewPlan,
}: {
  run: Run | null;
  signoff: SignoffState;
  onApprove: (decisions: string[], requests: string[]) => void;
  onNewPlan: () => void;
}) {
  return (
    <Card size="sm" aria-labelledby="signoff-heading" role="region">
      <CardHeader>
        <CardTitle id="signoff-heading">Sign off</CardTitle>
        <CardDescription>You approve what the airline decides. You send the rest as requests.</CardDescription>
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
          // Keyed so choices reset whenever a new plan is made.
          <SignoffForm
            key={run.run_id}
            card={run.card}
            signoff={signoff}
            onApprove={onApprove}
            onNewPlan={onNewPlan}
          />
        )}
      </CardContent>
    </Card>
  );
}

function SignoffForm({
  card,
  signoff,
  onApprove,
  onNewPlan,
}: {
  card: PlanCardData;
  signoff: SignoffState;
  onApprove: (decisions: string[], requests: string[]) => void;
  onNewPlan: () => void;
}) {
  const [decisions, setDecisions] = useState<string[]>(() => card.airline_decisions.map((d) => d.key));
  const [requests, setRequests] = useState<string[]>(() => card.requests.map((r) => r.key));
  const locked = signoff.status === "loading" || (signoff.status === "done" && isApproved(signoff.result.status));
  const toggle = (list: string[], set: (v: string[]) => void, key: string, on: boolean) =>
    set(on ? [...list, key] : list.filter((k) => k !== key));
  const none = decisions.length === 0 && requests.length === 0;

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onApprove(decisions, requests);
      }}
    >
      <div role="status" aria-live="polite">
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
              {signoffStatusLabel(signoff.result.status)} by {DECIDED_BY}. The requests below are sent; ATC and the
              pilot still have to act on them.
            </p>
            <ResultList title="Airline decisions approved" items={signoff.result.airline_decisions} />
            <ResultList
              title="Requests issued"
              items={signoff.result.requests.map((r) => ({ ...r, value: `${r.value} (to ${r.to})` }))}
            />
            <p className="flex items-center gap-1 font-mono text-xs break-all">
              <Hash aria-hidden className="size-3 shrink-0" />
              Log head {signoff.result.log_head}
            </p>
          </div>
        )}
        {signoff.status === "done" && !isApproved(signoff.result.status) && (
          <div className="space-y-2 rounded-lg border border-destructive/40 bg-destructive-soft p-3 text-sm">
            <p className="flex items-center gap-1.5 font-semibold text-destructive">
              <CircleX aria-hidden className="size-4" />
              {signoffStatusLabel(signoff.result.status)}
            </p>
            <p className="text-xs">Nothing was issued.</p>
            {signoff.result.changed_fields.length > 0 && (
              <div>
                <p className="text-xs font-semibold">What changed since you looked</p>
                <ul className="list-disc pl-5">
                  {signoff.result.changed_fields.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
            {signoff.result.violations.length > 0 && (
              <div>
                <p className="text-xs font-semibold">Rules now broken</p>
                <RuleList rules={signoff.result.violations} result="broken" />
              </div>
            )}
            <Button type="button" variant="outline" size="sm" onClick={onNewPlan}>
              Make a new recovery plan
            </Button>
          </div>
        )}
      </div>
      <fieldset className="space-y-1.5" disabled={locked}>
        <legend className="text-sm font-semibold">You decide</legend>
        <p className="text-xs text-muted-foreground">The airline&rsquo;s own calls.</p>
        {card.airline_decisions.map((d) => {
          const id = `dec-${d.key}`;
          return (
            <div key={d.key} className="flex items-start gap-2 text-sm">
              <Checkbox
                id={id}
                checked={decisions.includes(d.key)}
                onCheckedChange={(v) => toggle(decisions, setDecisions, d.key, v)}
                className="mt-0.5"
              />
              <label htmlFor={id} className="flex-1">
                <span className="text-muted-foreground">{d.label}: </span>
                <span className="font-medium">{d.value}</span>{" "}
                <ProvenanceBadge provenance={d.provenance} className="align-middle" />
              </label>
            </div>
          );
        })}
      </fieldset>

      <fieldset className="space-y-1.5" disabled={locked}>
        <legend className="text-sm font-semibold">You request</legend>
        <p className="text-xs text-muted-foreground">
          Others decide these. The pilot in command keeps fuel and safety authority.
        </p>
        {card.requests.map((r) => {
          const id = `req-${r.key}`;
          return (
            <div key={r.key} className="flex items-start gap-2 text-sm">
              <Checkbox
                id={id}
                checked={requests.includes(r.key)}
                onCheckedChange={(v) => toggle(requests, setRequests, r.key, v)}
                className="mt-0.5"
              />
              <label htmlFor={id} className="flex-1">
                <span className="text-muted-foreground">{r.label}: </span>
                <span className="font-medium">{r.value}</span>{" "}
                <ProvenanceBadge provenance={r.provenance} className="align-middle" />
                <span className="block text-xs text-muted-foreground">Request to {r.to}</span>
              </label>
            </div>
          );
        })}
      </fieldset>

      {signoff.status === "idle" || signoff.status === "error" || signoff.status === "done" ? (
        !locked && (
          <Button type="submit" disabled={none} className="w-full">
            Approve and send requests
          </Button>
        )
      ) : (
        <LoadingBlock label="Checking the rules again against the current airport" lines={2} />
      )}
      {none && !locked && (
        <p className="text-xs text-muted-foreground">Tick at least one item to approve.</p>
      )}
      <p className="text-xs text-muted-foreground">
        Sign-off checks the plan, the airport and this card again before anything is issued.
      </p>

    </form>
  );
}

function ResultList({ title, items }: { title: string; items: { key: string; label: string; value: string }[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-semibold">{title}</p>
      <ul className="list-disc pl-5">
        {items.map((i) => (
          <li key={i.key}>
            {i.label}: {i.value}
          </li>
        ))}
      </ul>
    </div>
  );
}
