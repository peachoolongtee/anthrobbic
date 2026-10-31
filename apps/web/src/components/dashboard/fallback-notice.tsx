import { Info, TriangleAlert } from "lucide-react";
import type { Domain, FaultKind, Run } from "@/lib/api-types";
import { DOMAIN_LABEL, FAULT_LABEL } from "@/lib/labels";

/** Each fault kind once, with the agents it hit, so a fallback's cause stays readable. */
function faultLines(run: Run): string[] {
  const byKind = new Map<FaultKind, Domain[]>();
  for (const f of run.faults) {
    if (f.kind === "model_off") continue;
    const domains = byKind.get(f.kind) ?? [];
    if (f.domain && !domains.includes(f.domain)) domains.push(f.domain);
    byKind.set(f.kind, domains);
  }
  return [...byKind].map(([kind, domains]) => {
    const who = domains.map((d) => DOMAIN_LABEL[d]).join(", ");
    return who ? `${FAULT_LABEL[kind]}: ${who}` : FAULT_LABEL[kind];
  });
}

/**
 * Says how a plan was reached when the agents did not reach it. A fault is always
 * named, so a fallback caused by a failure never looks like a clean result.
 */
export function FallbackNotice({ run, onlyFaults = false }: { run: Run; onlyFaults?: boolean }) {
  const faults = faultLines(run);
  if (faults.length === 0 && (onlyFaults || run.path !== "fallback")) return null;
  const modelOff = run.fallback_trigger === "llm_off" || run.faults.some((f) => f.kind === "model_off");
  return (
    <div className="flex items-start gap-1.5 rounded-lg border bg-muted/50 px-2 py-1.5 text-sm">
      {faults.length === 0 && modelOff ? (
        <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      ) : (
        <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
      )}
      <div>
        {run.path === "fallback" ? (
          <p>
            Chosen by the rule-based fallback.{" "}
            {faults.length > 0
              ? "A fault stopped the agents, so they did not agree on this plan."
              : modelOff
                ? "The model is off, so the agents did not run."
                : "The agents did not agree."}
          </p>
        ) : (
          <p>A fault occurred during this run.</p>
        )}
        {faults.length > 0 && (
          <ul className="mt-0.5 list-disc pl-4 font-medium">
            {faults.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
