import { ServerCrash, ShieldAlert } from "lucide-react";
import type { NoGo } from "@/lib/api-types";
import { cn } from "@/lib/utils";
import { RuleList } from "@/components/dashboard/rule-line";

const COPY = {
  NOTHING_LEGAL: {
    icon: ShieldAlert,
    tone: "border-destructive/40 bg-destructive-soft",
    iconTone: "text-destructive",
    title: "No legal recovery plan",
    kind: "No-go: nothing is legal",
    lead: "Every possible plan breaks at least one rule. This is a real constraint, not a fault. No recovery plan passes the rules checked, so none is offered.",
    next: "Decide with air traffic control, the crew and the ramp. The closest plan below shows what would have to change.",
  },
  SYSTEM_FAULT: {
    icon: ServerCrash,
    tone: "border-warning/50 bg-warning-soft",
    iconTone: "text-warning",
    title: "The system could not decide",
    kind: "No-go: system fault",
    lead: "Data was missing or a part failed, so the plans could not be checked. No plan was judged illegal. Do not read this as an unrecoverable flight.",
    next: "Fix the data or the failing part, then run it again. If you cannot, decide by hand.",
  },
} as const;

export function NoGoView({ decision }: { decision: NoGo }) {
  const c = COPY[decision.reason_type];
  const Icon = c.icon;
  return (
    <div className="space-y-3">
      <section className={cn("rounded-lg border p-3", c.tone)} aria-labelledby="nogo-heading">
        <div className="flex items-start gap-3">
          <Icon aria-hidden className={cn("mt-0.5 size-6 shrink-0", c.iconTone)} />
          <div className="space-y-1">
            <p className="text-xs font-semibold tracking-wide uppercase">{c.kind}</p>
            <h2 id="nogo-heading" className="text-base font-semibold">
              {c.title}
            </h2>
            <p className="text-sm">{c.lead}</p>
            <p className="text-sm font-medium">{c.next}</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="binding-heading" className="rounded-lg border bg-card p-4">
        <h3 id="binding-heading" className="text-sm font-semibold">
          {decision.reason_type === "NOTHING_LEGAL" ? "Rules that block every plan" : "What could not be checked"}
        </h3>
        <p className="text-xs text-muted-foreground">
          {decision.reason} {decision.packages_considered} plans were considered.
        </p>
        <RuleList rules={decision.binding_rules} result="broken" />
      </section>

      <section aria-labelledby="nearest-heading" className="rounded-lg border bg-card p-4">
        <h3 id="nearest-heading" className="text-sm font-semibold">
          Closest plan
        </h3>
        {decision.nearest_package ? (
          <>
            <p className="mt-1 text-sm font-medium">{decision.nearest_package.label}</p>
            <p className="text-xs text-muted-foreground">Fails the fewest rules. Not a recommendation.</p>
            {decision.nearest_violations.length > 0 && (
              <RuleList rules={decision.nearest_violations} result="broken" />
            )}
          </>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            No closest plan can be shown, because the plans could not be checked.
          </p>
        )}
      </section>

      <section aria-labelledby="change-heading" className="rounded-lg border bg-card p-4">
        <h3 id="change-heading" className="text-sm font-semibold">
          What would have to change
        </h3>
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
          {decision.what_would_change.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
