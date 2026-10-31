import { CircleAlert, CircleCheck, CircleMinus } from "lucide-react";
import type { ReactNode } from "react";
import type { Run } from "@/lib/api-types";
import { DOMAIN_LABEL, FAULT_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

function Chip({
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
    <div className="inline-flex min-w-0 items-center gap-1.5 rounded-md border bg-card px-2 py-1 text-sm">
      <Icon
        aria-hidden
        className={cn(
          "size-4 shrink-0",
          tone === "ok" ? "text-success" : tone === "no" ? "text-destructive" : "text-muted-foreground",
        )}
      />
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold">{children}</span>
    </div>
  );
}

/**
 * Three plain answers: did the agents agree, did every rule pass, and which of
 * the two did the work. Read straight from `path` and `decision`.
 */
export function OutcomeStrip({ run }: { run: Run }) {
  const agreed = run.path === "consensus";
  const notAsked = run.fallback_trigger === "llm_off";
  const passed = run.decision.kind === "DEAL";
  return (
    <section aria-label="How this recovery plan was reached" className="space-y-1.5">
      <div className="flex flex-wrap gap-1.5">
        <Chip label="Agents agreed?" tone={agreed ? "ok" : notAsked ? "neutral" : "no"}>
          {agreed ? "Yes" : notAsked ? "Not asked: model off" : "No"}
        </Chip>
        <Chip label="Rules passed?" tone={passed ? "ok" : "no"}>
          {passed ? "Yes" : "No plan passes"}
        </Chip>
        <Chip label="Chosen by" tone="neutral">
          {run.path === "consensus" && "agents, then rules"}
          {run.path === "fallback" && "rules only, not agents"}
          {run.path === "no_go" && "nobody: no-go, yours to decide"}
        </Chip>
      </div>
      {run.faults.length > 0 && (
        <ul className="space-y-1" aria-label="Faults">
          {run.faults.map((f, i) => (
            <li
              key={i}
              className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning-soft px-2 py-1 text-sm"
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
