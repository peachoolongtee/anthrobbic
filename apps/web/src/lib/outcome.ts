import type { Run } from "@/lib/api-types";
import { PATH_LABEL } from "@/lib/labels";

/**
 * What became of a flight's recovery plan, in the system document's words.
 * A system fault is its own outcome, never folded into a no-go. `failed`
 * means the run itself could not be started, so there is no outcome to show.
 */
export type Outcome = "agreed" | "fallback" | "no_go" | "fault" | "failed";

export const OUTCOME: Record<Outcome, { label: string; dot: string; text: string; stroke: string }> = {
  agreed: { label: PATH_LABEL.consensus, dot: "bg-success", text: "text-success", stroke: "stroke-success" },
  fallback: { label: PATH_LABEL.fallback, dot: "bg-muted-foreground", text: "text-muted-foreground", stroke: "stroke-muted-foreground" },
  no_go: { label: PATH_LABEL.no_go, dot: "bg-destructive", text: "text-destructive", stroke: "stroke-destructive" },
  fault: { label: "System fault", dot: "bg-warning", text: "text-warning", stroke: "stroke-warning" },
  failed: { label: "Run did not start", dot: "bg-muted", text: "text-muted-foreground", stroke: "stroke-muted" },
};

/** The outcome of a finished run. */
export function outcomeOf(run: Run): Outcome {
  if (run.decision.kind === "NO_GO") return run.decision.reason_type === "SYSTEM_FAULT" ? "fault" : "no_go";
  return run.path === "consensus" ? "agreed" : "fallback";
}
