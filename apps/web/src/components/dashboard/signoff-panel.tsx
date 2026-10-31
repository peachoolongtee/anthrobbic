"use client";

import { useEffect, useRef, useState } from "react";
import { Check, CircleCheck, CircleX, Copy, Hash, Send, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { Card as PlanCardData, PackageTerm, Run } from "@/lib/api-types";
import type { DecisionState, SignoffState } from "@/hooks/use-dashboard";
import { DECIDED_BY } from "@/hooks/use-dashboard";
import {
  FINAL_DECISION_LABEL,
  TERM_LABEL,
  changedFieldLabel,
  isApproved,
  plainTerm,
  refusalBanner,
  shortRecipient,
  signoffStatusLabel,
} from "@/lib/labels";
import { FallbackNotice } from "@/components/dashboard/fallback-notice";
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
              <strong>Nothing to approve.</strong>{" "}
              {run.decision.kind === "NO_GO" && run.decision.reason_type === "SYSTEM_FAULT"
                ? "The plans could not be checked, so there is nothing to sign."
                : "No recovery plan passed the rules, so there is nothing to sign."}{" "}
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

/** The log's fingerprint after this decision: short, with the full value on hover and copy. */
function LogHead({ head }: { head: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground" title={`Log fingerprint ${head}`}>
      <Hash aria-hidden className="size-3 shrink-0" />
      <span className="font-mono">{head.slice(0, 8)}</span>
      <span className="sr-only">Log fingerprint {head}</span>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard?.writeText(head).then(() => setCopied(true));
        }}
        aria-label="Copy the log fingerprint"
        className="rounded p-0.5 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        {copied ? <Check aria-hidden className="size-3" /> : <Copy aria-hidden className="size-3" />}
      </button>
    </span>
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
  // Approved or decided earlier: nothing more can happen to this plan.
  const finished =
    signoff.status === "done" &&
    (signoff.result.status === "REFUSED_ALREADY_USED" || signoff.result.status === "REFUSED_ALREADY_DECIDED");
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

      {!(approved || decided || finished) && (
        <>
      <fieldset className="space-y-1.5" disabled={locked}>
        <legend className="flex items-center gap-1.5 text-sm font-semibold" title="The airline's own calls">
          <UserCheck aria-hidden className="size-4 text-muted-foreground" />
          You decide
        </legend>
        <ul className="space-y-0.5 text-sm">
          {card.airline_decisions.map((d) => {
            const t = plainTerm(d.key, d.label, d.value);
            return (
              <li key={d.key} className="flex items-center gap-1.5">
                <span className="text-muted-foreground">{t.label}</span>
                <span className="font-medium">{t.value}</span>
              </li>
            );
          })}
        </ul>
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
          {card.requests.map((r) => {
            const t = plainTerm(r.key, r.label, r.value);
            return (
              <li key={r.key} className="flex flex-wrap items-center gap-x-1.5">
                <span className="text-muted-foreground">{t.label}</span>
                <span className="font-medium">{t.value}</span>
                <span className="text-xs text-muted-foreground" title={`To ${r.to}`}>
                  to {shortRecipient(r.to)}
                </span>
              </li>
            );
          })}
        </ul>
      </fieldset>

      {/* Stops following the scroll once decided, so it cannot cover the outcome above it. */}
      <div className={cn("space-y-1.5 bg-card pt-2 pb-3", !approved && !decided && "sticky -bottom-4 z-10")}>
        {!confirmingReject && !locked && !refused && (
          <div className="space-y-1 text-sm">
            <div className="flex items-start gap-2">
              <Checkbox id="approve-decisions" checked={decide} disabled={locked} onCheckedChange={(v) => setDecide(v)} className="mt-0.5" />
              <label htmlFor="approve-decisions" className="font-medium">
                Approve my decisions
              </label>
            </div>
            <div className="flex items-start gap-2">
              <Checkbox id="send-requests" checked={request} disabled={locked} onCheckedChange={(v) => setRequest(v)} className="mt-0.5" />
              <label htmlFor="send-requests" className="font-medium">
                Send the requests
              </label>
            </div>
          </div>
        )}
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
                  ? "Tick a box to approve."
                  : "The rules are checked again before anything is sent."}
          </p>
        )}
      </div>
        </>
      )}
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
        <div className="space-y-2.5 rounded-lg border border-success/40 bg-success-soft p-3 text-sm">
          <p className="flex items-center gap-1.5 font-semibold text-success">
            <CircleCheck aria-hidden className="size-4" />
            Approved
          </p>
          <p className="text-xs text-muted-foreground">
            {signoff.result.requests.length > 0
              ? "Requests sent. ATC and the pilot still decide."
              : "No requests sent."}
          </p>
          <DoneList icon={UserCheck} label="Decided" items={signoff.result.airline_decisions} />
          <DoneList icon={Send} label="Requested" items={signoff.result.requests} />
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span title={DECIDED_BY}>By duty manager (demo)</span>
            <LogHead head={signoff.result.log_head} />
          </div>
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
  if (result.status === "REFUSED_ALREADY_USED") {
    return (
      <div className="space-y-1 rounded-lg border border-border bg-muted/50 p-3 text-sm">
        <p className="flex items-center gap-1.5 font-semibold">
          <CircleCheck aria-hidden className="size-4 text-success" />
          {label.title}
        </p>
        <p className="text-xs text-muted-foreground">{label.detail}</p>
      </div>
    );
  }
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

function DoneList({ icon: Icon, label, items }: { icon: typeof Send; label: string; items: PackageTerm[] }) {
  if (items.length === 0) return null;
  return (
    <ul aria-label={label} className="space-y-1">
      {items.map((t) => {
        const p = plainTerm(t.name, TERM_LABEL[t.name] ?? t.name, t.value);
        return (
          <li key={t.name} className="flex items-center gap-2">
            <Icon aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="text-muted-foreground">{p.label}</span>
            <span className="font-medium">{p.value}</span>
          </li>
        );
      })}
    </ul>
  );
}
