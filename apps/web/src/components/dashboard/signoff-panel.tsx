"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, CircleCheck, CircleX, Hash, Send, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { Card as PlanCardData, PackageTerm, Run } from "@/lib/api-types";
import type { DecisionState, SignoffState } from "@/hooks/use-dashboard";
import { DECIDED_BY } from "@/hooks/use-dashboard";
import { FINAL_DECISION_LABEL, TERM_LABEL, changedFieldLabel, isApproved, refusalBanner, signoffStatusLabel } from "@/lib/labels";
import { FallbackNotice } from "@/components/dashboard/fallback-notice";
import { ProvenanceBadge } from "@/components/dashboard/provenance-badge";
import { RuleList } from "@/components/dashboard/rule-line";

export function SignoffPanel({
  run,
  signoff,
  decision,
  onApprove,
  onReject,
  onTakeOver,
  onNewPlan,
}: {
  run: Run | null;
  signoff: SignoffState;
  decision: DecisionState;
  onApprove: (decisions: boolean, requests: boolean) => void;
  onReject: (reason: string) => void;
  onTakeOver: (note: string) => void;
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
        ) : run.decision.kind === "NO_GO" || !run.card ? (
          <div className="space-y-3">
            <p className="text-sm">
              <strong>Nothing to approve.</strong> No recovery plan passed the rules, so there is nothing to sign.
              The case is yours to handle.
            </p>
            <FallbackNotice run={run} onlyFaults />
            <TakeOverForm key={run.run_id} decision={decision} onTakeOver={onTakeOver} />
          </div>
        ) : (
          // Keyed so the choices reset whenever a new plan is made.
          <SignoffForm
            key={run.run_id}
            run={run}
            card={run.card}
            signoff={signoff}
            decision={decision}
            onApprove={onApprove}
            onReject={onReject}
            onNewPlan={onNewPlan}
          />
        )}
      </CardContent>
    </Card>
  );
}

/** Logged, no approval and no request. The note is stored as unverified. */
function TakeOverForm({
  decision,
  onTakeOver,
}: {
  decision: DecisionState;
  onTakeOver: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  if (decision.status === "done") {
    return (
      <DecisionOutcome>
        <p className="font-semibold">
          {decision.result.status === "TAKEN_OVER"
            ? "Logged: this case is with the duty manager. Nothing was approved or requested."
            : signoffStatusLabel(decision.result.status).title}
        </p>
        <LogHead head={decision.result.log_head} />
      </DecisionOutcome>
    );
  }
  const loading = decision.status === "loading";
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        onTakeOver(note);
      }}
    >
      {decision.status === "error" && <DecisionError message={decision.message} />}
      <FreeText id="take-over-note" label="Note (optional, recorded as unverified)" value={note} onChange={setNote} disabled={loading} />
      <Button type="submit" variant="secondary" disabled={loading} className="w-full">
        {loading ? "Logging..." : "I've taken this case"}
      </Button>
    </form>
  );
}

function FreeText({
  id,
  label,
  value,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </label>
      <Input
        id={id}
        value={value}
        maxLength={2000}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        // Enter must never approve or reject by accident.
        onKeyDown={(e) => {
          if (e.key === "Enter") e.preventDefault();
        }}
      />
    </div>
  );
}

function LogHead({ head }: { head: string }) {
  return (
    <p className="flex items-start gap-1 font-mono text-xs break-all">
      <Hash aria-hidden className="mt-0.5 size-3 shrink-0" />
      Log head {head}
    </p>
  );
}

function DecisionError({ message }: { message: string }) {
  const ref = useFocusOnShow<HTMLParagraphElement>();
  return (
    <p ref={ref} tabIndex={-1} role="alert" className="rounded-lg border border-destructive/40 bg-destructive-soft p-2 text-sm outline-none">
      <strong>That was not recorded.</strong> {message} Nothing was issued.
    </p>
  );
}

/** The panel scrolls, so an outcome must bring itself into view when it appears. */
function useFocusOnShow<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => ref.current?.focus(), []);
  return ref;
}

function DecisionOutcome({ children }: { children: React.ReactNode }) {
  const ref = useFocusOnShow<HTMLDivElement>();
  return (
    <div ref={ref} tabIndex={-1} role="status" className="space-y-2 rounded-lg border bg-muted/50 p-3 text-sm outline-none">
      {children}
    </div>
  );
}

/** The panel scrolls, so a step that just opened brings itself fully into view. */
function showWhenOpened(el: HTMLElement | null) {
  el?.scrollIntoView({ block: "end" });
}

function SignoffForm({
  run,
  card,
  signoff,
  decision,
  onApprove,
  onReject,
  onNewPlan,
}: {
  run: Run;
  card: PlanCardData;
  signoff: SignoffState;
  decision: DecisionState;
  onApprove: (decisions: boolean, requests: boolean) => void;
  onReject: (reason: string) => void;
  onNewPlan: () => void;
}) {
  // Nothing is ticked for you. Approving is a deliberate act.
  const [decide, setDecide] = useState(false);
  const [request, setRequest] = useState(false);
  const [reason, setReason] = useState("");
  // Rejecting takes two steps, and the reason is on screen at the second.
  const [confirmingReject, setConfirmingReject] = useState(false);
  const decided = decision.status === "done";
  const rejecting = decision.status === "loading";
  const locked =
    signoff.status === "loading" || (signoff.status === "done" && isApproved(signoff.result.status)) || decided || rejecting;
  const none = !decide && !request;
  const approved = signoff.status === "done" && isApproved(signoff.result.status);
  // After any refusal the plan on screen is out of date until a new one is made.
  const refused = signoff.status === "done" && !approved;
  const stale = refused && refusalBanner(signoff.result.status).outOfDate;
  const alreadyDecided = refused && signoff.result.status === "REFUSED_ALREADY_DECIDED";
  const loading = signoff.status === "loading";

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onApprove(decide, request);
      }}
    >
      <SignoffResultView signoff={signoff} onNewPlan={onNewPlan} />
      {decision.status === "error" && <DecisionError message={decision.message} />}
      {decision.status === "done" && (
        <DecisionOutcome>
          <p className="font-semibold">
            {decision.result.status === "REJECTED"
              ? "Plan rejected. Nothing was issued."
              : signoffStatusLabel(decision.result.status).title}
          </p>
          <LogHead head={decision.result.log_head} />
          <Button type="button" variant="outline" size="sm" onClick={onNewPlan}>
            Make a new recovery plan
          </Button>
        </DecisionOutcome>
      )}
      <FallbackNotice run={run} />

      <fieldset className="space-y-1.5" disabled={locked}>
        <legend className="flex items-center gap-1.5 text-sm font-semibold" title="The airline's own calls">
          <UserCheck aria-hidden className="size-4 text-muted-foreground" />
          You decide
        </legend>
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
        <legend
          className="flex items-center gap-1.5 text-sm font-semibold"
          title="Others decide these. The pilot in command keeps fuel and safety authority."
        >
          <Send aria-hidden className="size-4 text-muted-foreground" />
          You request
        </legend>
        <ul className="space-y-0.5 text-sm">
          {card.requests.map((r) => (
            <li key={r.key}>
              <span className="text-muted-foreground">{r.label}: </span>
              <span className="font-medium">{r.value}</span> <ProvenanceBadge provenance={r.provenance} className="align-middle" />{" "}
              <span title={`To ${r.to}`} className="inline-flex align-middle text-muted-foreground">
                <ArrowUpRight aria-hidden className="size-3.5" />
                <span className="sr-only">to {r.to}</span>
              </span>
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

      {/* Stays on screen while the rest of the panel scrolls. */}
      <div className="sticky -bottom-4 z-10 space-y-1 bg-card pt-2 pb-3">
        {confirmingReject && !decided ? (
          <div ref={showWhenOpened} className="space-y-2 rounded-lg border border-destructive/40 bg-destructive-soft p-2">
            <p className="text-sm font-semibold">Reject this plan? Nothing is issued, and this run cannot then be approved.</p>
            <FreeText id="reject-reason" label="Reason (optional, recorded as unverified)" value={reason} onChange={setReason} disabled={rejecting} />
            <div className="flex gap-2">
              <Button type="button" variant="destructive" disabled={rejecting} onClick={() => onReject(reason)} className="flex-1">
                {rejecting ? "Logging..." : "Confirm rejection"}
              </Button>
              <Button type="button" variant="outline" disabled={rejecting} onClick={() => setConfirmingReject(false)}>
                Keep plan
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button type="submit" disabled={none || refused || loading || approved || decided || rejecting} className="flex-1">
              {loading ? "Checking the rules again..." : approved ? "Approved" : "Approve"}
            </Button>
            <Button type="button" variant="secondary" disabled={loading || approved || decided || rejecting || alreadyDecided} onClick={() => setConfirmingReject(true)}>
              Reject plan
            </Button>
          </div>
        )}
        {!approved && !decided && !confirmingReject && (
          <p className="text-xs text-muted-foreground">
            {stale
              ? "This plan is out of date. Make a new recovery plan to approve again."
              : refused
                ? "This plan cannot be approved here."
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
            {signoff.result.requests.length > 0 ? "Requests issued, nothing executed" : "No requests issued, nothing executed"}
          </p>
          <p className="text-xs">
            Approved by {DECIDED_BY}.{" "}
            {signoff.result.requests.length > 0
              ? "Requests were issued, not granted. Nothing has been executed. ATC and the pilot still have to act on the requests."
              : "You chose not to send any requests, so ATC and the pilot have not been asked. Nothing has been executed."}
          </p>
          <TermList title="Airline decisions approved" items={signoff.result.airline_decisions} />
          <TermList title="Requests issued" items={signoff.result.requests} />
          <LogHead head={signoff.result.log_head} />
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
      <p className="text-xs">
        {result.final_decision ? `${FINAL_DECISION_LABEL[result.final_decision]} ` : ""}
        {label.detail}
      </p>
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
      {refusalBanner(result.status).outOfDate && (
        <Button type="button" variant="outline" size="sm" onClick={onNewPlan}>
          Make a new recovery plan
        </Button>
      )}
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
