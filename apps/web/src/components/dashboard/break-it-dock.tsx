"use client";

import { useState } from "react";
import { CircleAlert, CircleCheck, FileWarning, Info, Loader2, RotateCcw, ShieldAlert, TimerReset } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Run, RunOverrides } from "@/lib/api-types";
import type { BreakKind, BreakOutcome } from "@/hooks/use-dashboard";
import { UNSAFE_OPTIONS } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface Props {
  run: Run | null;
  overrides: RunOverrides;
  busy: BreakKind | null;
  disabled: boolean;
  outcome: BreakOutcome | null;
  onUnsafe: (ruleId: string) => void;
  onStale: () => void;
  onTamper: () => void;
  onReset: () => void;
}

const TONE = {
  ok: { icon: CircleCheck, cls: "border-success/40", iconCls: "text-success" },
  bad: { icon: CircleAlert, cls: "border-destructive/50", iconCls: "text-destructive" },
  info: { icon: Info, cls: "border-info/40", iconCls: "text-info" },
} as const;

/**
 * The try-to-break-it controls that are not on the map: inject an unsafe
 * plan, change the airport behind the screen, tamper with the log, reset.
 * Runways and gates are closed by selecting them on the map.
 */
export function BreakItDock(p: Props) {
  const [unsafe, setUnsafe] = useState<string>(UNSAFE_OPTIONS[0].value);
  const off = p.disabled || p.busy !== null || p.run === null;
  const hasOverrides =
    (p.overrides.closed_runways?.length ?? 0) > 0 ||
    (p.overrides.closed_gates?.length ?? 0) > 0 ||
    !!p.overrides.inject_unsafe;
  const tone = p.outcome ? TONE[p.outcome.tone] : null;
  const Icon = tone?.icon;

  return (
    <section aria-label="Try to break it" className="flex flex-col items-center gap-2">
      <div role="status" aria-live="polite" className="min-h-0">
        {p.busy !== null && (
          <p className="flex items-center gap-2 rounded-full border border-border bg-card/90 px-3 py-1 text-sm backdrop-blur">
            <Loader2 aria-hidden className="size-4 animate-spin" />
            Re-running
          </p>
        )}
        {p.busy === null && p.outcome && tone && Icon && (
          <p
            className={cn(
              "flex max-w-xl items-start gap-2 rounded-xl border bg-card/90 px-3 py-1.5 text-sm backdrop-blur",
              tone.cls,
            )}
          >
            <Icon aria-hidden className={cn("mt-0.5 size-4 shrink-0", tone.iconCls)} />
            <span>
              <strong className="font-semibold">{p.outcome.title}.</strong>{" "}
              <span className="text-muted-foreground">{p.outcome.detail}</span>
            </span>
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-center gap-1 rounded-xl border border-border bg-card/85 p-1 shadow-lg shadow-black/30 backdrop-blur">
        <Select items={UNSAFE_OPTIONS} value={unsafe} onValueChange={(v) => v && setUnsafe(v)} disabled={off}>
          <SelectTrigger size="sm" aria-label="Unsafe recovery plan to inject" className="w-34 border-transparent bg-transparent">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {UNSAFE_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" variant="secondary" disabled={off} onClick={() => p.onUnsafe(unsafe)} title="Slip this unsafe recovery plan into the negotiation">
          <ShieldAlert aria-hidden />
          Inject
        </Button>
        <span aria-hidden className="mx-1 h-5 w-px bg-border" />
        <Button
          size="sm"
          variant="ghost"
          disabled={off}
          onClick={p.onStale}
          title="Block the recovery plan's gate on the server while this screen keeps the old recovery plan. Then try to approve."
        >
          <TimerReset aria-hidden />
          Change behind
        </Button>
        <Button size="sm" variant="ghost" disabled={off} onClick={p.onTamper} title="Edit the decision log and check it">
          <FileWarning aria-hidden />
          Tamper log
        </Button>
        <Button size="icon-sm" variant="ghost" disabled={off || !hasOverrides} onClick={p.onReset} aria-label="Reset" title="Reset">
          <RotateCcw aria-hidden />
        </Button>
      </div>
    </section>
  );
}
