import { CircleAlert, CircleCheck, CircleMinus } from "lucide-react";
import type { ReactNode } from "react";
import type { Run } from "@/lib/api-types";
import { DOMAIN_LABEL, FAULT_LABEL, PATH_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

function Cell({
  label,
  tone,
  children,
}: {
  label: string;
  tone: "ok" | "no" | "neutral";
  children: ReactNode;
}) {
  const Icon = tone === "ok" ? CircleCheck : tone === "no" ? CircleAlert : CircleMinus;
  return (
    <div className="min-w-0 rounded-lg border bg-card p-2.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 flex items-start gap-1.5 text-sm font-semibold">
        <Icon
          aria-hidden
          className={cn(
            "mt-0.5 size-4 shrink-0",
            tone === "ok" ? "text-success" : tone === "no" ? "text-destructive" : "text-muted-foreground",
          )}
        />
        <span>{children}</span>
      </div>
    </div>
  );
}

/**
 * Three plain answers: did the agents agree, did every rule pass, and which of
 * the two did the work. Read straight from `path` and `decision`.
 */
export function OutcomeStrip({ run }: { run: Run }) {
  const agreed = run.path === "consensus";
  const passed = run.decision.kind === "DEAL";
  return (
    <section aria-label="How this recovery plan was reached" className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-3">
        <Cell label="Did the agents agree?" tone={agreed ? "ok" : "no"}>
          {agreed ? "Yes, all three" : "No"}
        </Cell>
        <Cell label="Did every rule pass?" tone={passed ? "ok" : "no"}>
          {passed ? "Yes" : "No plan passes"}
        </Cell>
        <Cell label="Who chose the plan" tone="neutral">
          {run.path === "consensus" && "The agents proposed it, the rules approved it"}
          {run.path === "fallback" && "The rule-based fallback, not the agents"}
          {run.path === "no_deal" && "Nobody. It is yours to decide"}
        </Cell>
      </div>
      <p className="text-xs text-muted-foreground">
        {PATH_LABEL[run.path]}.{" "}
        {run.path === "consensus"
          ? "Agreement alone proves nothing. What is allowed is decided by the rules."
          : run.path === "fallback"
            ? "A fallback is never shown as a clean result. The reason is below."
            : "The system stopped instead of guessing."}
      </p>
      {run.faults.length > 0 && (
        <ul className="space-y-1" aria-label="Faults">
          {run.faults.map((f, i) => (
            <li
              key={i}
              className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning-soft px-2.5 py-1.5 text-sm"
            >
              <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
              <span>
                <strong>{FAULT_LABEL[f.kind]}</strong>
                {f.domain ? ` (${DOMAIN_LABEL[f.domain]}${f.turn ? `, turn ${f.turn}` : ""})` : ""}. {f.message}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
