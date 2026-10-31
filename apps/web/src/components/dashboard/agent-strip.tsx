"use client";

import { useEffect, useState } from "react";
import { CircleAlert, CircleCheck, CircleDashed, Loader2 } from "lucide-react";
import type { Domain, Run, RunMode } from "@/lib/api-types";
import { DOMAIN_LABEL, DOMAIN_ROLE, FAULT_LABEL, MODE_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

const DOMAINS: Domain[] = ["atc", "pilot", "ground"];

const STRIP = "flex items-center divide-x divide-border rounded-xl border border-border bg-card/85 shadow-lg shadow-black/30 backdrop-blur";

/** A live run takes many seconds. Says so, and counts them, so nobody takes the wait for a hang. */
export function LiveWorking() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div role="status" className={STRIP}>
      <span className="flex items-center gap-2 px-3 py-1.5">
        <Loader2 aria-hidden className="size-4 shrink-0 text-beacon motion-safe:animate-spin" />
        <span className="font-display text-sm font-semibold">Agents working, live</span>
        <span className="text-sm text-muted-foreground tabular-nums">{seconds} s</span>
      </span>
    </div>
  );
}

/** A live run that failed or was refused. The reason is on the panel. */
export function LiveFailed() {
  return (
    <div role="status" className={STRIP}>
      <span className="flex items-center gap-2 px-3 py-1.5">
        <CircleAlert aria-hidden className="size-4 shrink-0 text-destructive" />
        <span className="font-display text-sm font-semibold">The live run did not finish</span>
      </span>
    </div>
  );
}

/**
 * The three agents at a glance, read only from the run: how many plans each
 * accepted per turn, and whether the run agreed, fell back or faulted. A run
 * with no turns shows that the agents did not run, with the reason; it never
 * shows an exchange that did not happen. `mode` is optional: without it the
 * model_off fault tells the same story.
 */
export function AgentStrip({ run, mode }: { run: Run | null; mode?: RunMode }) {
  if (run && run.turns.length === 0) {
    const off = mode === "off" || run.faults.some((f) => f.kind === "model_off");
    const fault = run.faults.find((f) => f.kind !== "model_off");
    const reason = off ? MODE_LABEL.off.name : fault ? FAULT_LABEL[fault.kind] : null;
    return (
      <div role="status" className={STRIP}>
        <span className="flex items-center gap-2 px-3 py-1.5">
          <CircleDashed aria-hidden className="size-4 shrink-0 text-muted-foreground" />
          <span className="font-display text-sm font-semibold">The agents did not run</span>
          {reason && <span className="text-sm text-muted-foreground">{reason}</span>}
        </span>
      </div>
    );
  }
  return (
    <ul
      aria-label="Agents"
      className={STRIP}
    >
      {DOMAINS.map((domain) => {
        const counts = run?.turns.map((t) => t.responses.find((r) => r.domain === domain)?.acceptable_count) ?? [];
        const fault = run?.faults.find((f) => f.domain === domain);
        const tone = !run ? "idle" : fault ? "bad" : run.path === "consensus" ? "ok" : "warn";
        const Icon = tone === "ok" ? CircleCheck : tone === "idle" ? CircleDashed : CircleAlert;
        const summary =
          counts.length > 0
            ? `accepted ${counts.map((c, i) => `${c ?? "no answer"} in turn ${i + 1}`).join(", ")}`
            : "has no run to show yet";
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
