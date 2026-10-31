"use client";

import { useEffect, useState } from "react";
import { Loader2, Plane, Radar, Truck, type LucideIcon } from "lucide-react";
import type { Domain } from "@/lib/api-types";
import { DOMAIN_LABEL, DOMAIN_ROLE } from "@/lib/labels";
import { cn } from "@/lib/utils";

const AGENTS: { domain: Domain; Icon: LucideIcon }[] = [
  { domain: "atc", Icon: Radar },
  { domain: "pilot", Icon: Plane },
  { domain: "ground", Icon: Truck },
];

/** Past this many seconds the wait is called out as longer than usual. */
const SLOW_AFTER_S = 30;

/**
 * Shown while a recovery plan is being made. The API sends nothing until the
 * run finishes, so this claims no per-agent progress: it shows the three
 * agents at work together, the seconds elapsed, and the usual wait.
 */
export function AgentsWorking({ live }: { live: boolean }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, []);
  const slow = live && seconds >= SLOW_AFTER_S;

  return (
    <section role="status" aria-live="polite" aria-label="Making a recovery plan" className="space-y-3">
      <div className="flex items-center gap-2">
        <Loader2 aria-hidden className="size-4 shrink-0 text-primary motion-safe:animate-spin" />
        <p className="text-sm font-semibold">{live ? "The agents are negotiating" : "Loading the recorded run"}</p>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums" aria-label={`${seconds} seconds so far`}>
          {seconds} s
        </span>
      </div>

      <ul className="space-y-1.5">
        {AGENTS.map(({ domain, Icon }, i) => (
          <li key={domain} className="flex items-center gap-3 rounded-lg border border-border bg-background/40 px-3 py-2">
            <span className="grid size-7 shrink-0 place-items-center rounded-md bg-primary/12 text-primary">
              <Icon aria-hidden className="size-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">{DOMAIN_LABEL[domain]}</span>
              <span className="block truncate text-xs text-muted-foreground">{DOMAIN_ROLE[domain]}</span>
            </span>
            {/* Three dots that rise in turn: working, with no claim of how far along. */}
            <span aria-hidden className="flex items-end gap-0.5">
              {[0, 1, 2].map((d) => (
                <span
                  key={d}
                  className="size-1.5 rounded-full bg-primary motion-safe:animate-bounce"
                  style={{ animationDelay: `${i * 120 + d * 160}ms` }}
                />
              ))}
            </span>
          </li>
        ))}
      </ul>

      {/* Indeterminate: a band sweeping the track, not a percentage. */}
      <div aria-hidden className="relative h-1 overflow-hidden rounded-full bg-muted">
        <span className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-primary motion-safe:animate-[sweep_1.6s_ease-in-out_infinite] motion-reduce:w-full motion-reduce:opacity-40" />
      </div>

      <p className={cn("text-xs", slow ? "text-foreground" : "text-muted-foreground")}>
        {live
          ? slow
            ? "Taking longer than usual. The model may be busy; the rule-based fallback steps in if it fails."
            : "Usually 15 to 20 seconds. Code checks every rule before you see a plan."
          : "Replaying saved model answers."}
      </p>
    </section>
  );
}
