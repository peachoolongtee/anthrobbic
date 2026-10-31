import { CircleAlert, CircleCheck, CircleDashed } from "lucide-react";
import type { Domain, Run } from "@/lib/api-types";
import { DOMAIN_LABEL, DOMAIN_ROLE } from "@/lib/labels";
import { cn } from "@/lib/utils";

const DOMAINS: Domain[] = ["atc", "pilot", "ground"];

/**
 * The three agents at a glance: how many plans each accepted per turn, and
 * whether it agreed, fell back or faulted.
 */
export function AgentStrip({ run }: { run: Run | null }) {
  return (
    <ul
      aria-label="Agents"
      className="flex items-center divide-x divide-border rounded-xl border border-border bg-card/85 shadow-lg shadow-black/30 backdrop-blur"
    >
      {DOMAINS.map((domain) => {
        const counts = run?.turns.map((t) => t.responses.find((r) => r.domain === domain)?.acceptable_count) ?? [];
        const fault = run?.faults.find((f) => f.domain === domain);
        const tone = !run || run.turns.length === 0 ? "idle" : fault ? "bad" : run.path === "consensus" ? "ok" : "warn";
        const Icon = tone === "ok" ? CircleCheck : tone === "idle" ? CircleDashed : CircleAlert;
        const summary =
          counts.length > 0
            ? `accepted ${counts.map((c, i) => `${c ?? "no answer"} in turn ${i + 1}`).join(", ")}`
            : "did not negotiate";
        return (
          <li key={domain} title={`${DOMAIN_ROLE[domain]} agent ${summary}`} className="flex items-center gap-2 px-3 py-1.5">
            <Icon
              aria-hidden
              className={cn(
                "size-4 shrink-0",
                tone === "ok" && "text-success",
                tone === "warn" && "text-warning",
                tone === "bad" && "text-destructive",
                tone === "idle" && "text-muted-foreground",
              )}
            />
            <span className="font-display text-sm font-semibold">{DOMAIN_LABEL[domain]}</span>
            <span aria-hidden className="flex items-center gap-1 font-display text-sm tabular-nums text-muted-foreground">
              {counts.length === 0
                ? "—"
                : counts.map((c, i) => (
                    <span key={i} className={i === counts.length - 1 ? "text-foreground" : undefined}>
                      {i > 0 && <span className="mr-1 opacity-50">›</span>}
                      {c ?? "×"}
                    </span>
                  ))}
            </span>
            <span className="sr-only">{summary}</span>
          </li>
        );
      })}
    </ul>
  );
}
