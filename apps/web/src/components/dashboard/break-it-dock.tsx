"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  CircleAlert,
  CircleCheck,
  ChevronDown,
  FileWarning,
  Info,
  Loader2,
  MousePointerClick,
  RotateCcw,
  ShieldAlert,
  TimerReset,
  Wrench,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Run, RunOverrides } from "@/lib/api-types";
import type { BreakKind, BreakOutcome } from "@/hooks/use-dashboard";
import { DISRUPTION_LABELS, planDisruptions, type DisruptionId } from "@/lib/disruptions";
import { UNSAFE_OPTIONS } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface Props {
  run: Run | null;
  overrides: RunOverrides;
  busy: BreakKind | null;
  disabled: boolean;
  /** Closed by default, so the card does not cover the route on the map. */
  open: boolean;
  onToggle: () => void;
  onDisrupt: (kind: "runway" | "gate", overrides: RunOverrides, title: string) => void;
  /** Where runways and gates are closed: the diagram, or a hint for the 3D view. */
  children?: ReactNode;
  className?: string;
  onUnsafe: (ruleId: string) => void;
  onStale: () => void;
  onTamper: () => void;
  onReset: () => void;
}

/**
 * Every try-to-break-it control in one card: close runways and gates on the
 * diagram, inject an unsafe recovery plan, change the airport behind the
 * screen, tamper with the log, or reset. Results show in BreakNotice.
 */
export function BreakItDock(p: Props) {
  const [unsafe, setUnsafe] = useState<string>(UNSAFE_OPTIONS[0].value);
  const off = p.disabled || p.busy !== null || p.run === null;
  const hasOverrides =
    (p.overrides.closed_runways?.length ?? 0) > 0 ||
    (p.overrides.closed_gates?.length ?? 0) > 0 ||
    !!p.overrides.inject_unsafe;
  const presets = planDisruptions(p.run, p.overrides, p.run?.airport?.runways ?? []);
  const presetIds = Object.keys(presets) as DisruptionId[];
  const unavailable = presetIds.flatMap((id) => {
    const d = presets[id];
    return d.ok ? [] : [d.reason];
  });

  return (
    <section aria-labelledby="break-heading" className={cn("space-y-2", p.className)}>
      <header className="flex items-center gap-2">
        <h2 id="break-heading" className="text-sm font-semibold">
          <button
            type="button"
            aria-expanded={p.open}
            aria-controls="break-controls"
            onClick={p.onToggle}
            className="flex items-center gap-2 rounded-md outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Wrench aria-hidden className="size-4 text-muted-foreground" />
            Try to break it
            <ChevronDown aria-hidden className={cn("size-4 text-muted-foreground transition-transform motion-reduce:transition-none", !p.open && "rotate-180")} />
          </button>
        </h2>
        {p.busy !== null && <Loader2 aria-label="Re-running" className="size-4 animate-spin text-muted-foreground" />}
        <Button
          size="icon-sm"
          variant="ghost"
          disabled={off || !hasOverrides}
          onClick={p.onReset}
          aria-label="Reset every change"
          title="Reset every change"
          className="ml-auto"
        >
          <RotateCcw aria-hidden />
        </Button>
      </header>

      <div id="break-controls" hidden={!p.open} className="space-y-2">
        <div role="group" aria-label="Disruption presets" className="flex flex-wrap items-center gap-1">
          {presetIds.map((id) => {
            const d = presets[id];
            return (
              <Button
                key={id}
                size="sm"
                variant="secondary"
                disabled={off || !d.ok}
                title={d.ok ? `${d.modelled}. The page says so when it runs.` : d.reason}
                aria-describedby={!d.ok ? "preset-why" : undefined}
                onClick={() => d.ok && p.onDisrupt(id === "equipment" ? "gate" : "runway", d.overrides, d.modelled)}
              >
                {DISRUPTION_LABELS[id]}
              </Button>
            );
          })}
        </div>
        {!off && unavailable.length > 0 && (
          <p id="preset-why" className="sr-only">
            {unavailable.join(" ")}
          </p>
        )}

        {p.children}

        <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-2">
          <Select items={UNSAFE_OPTIONS} value={unsafe} onValueChange={(v) => v && setUnsafe(v)} disabled={off}>
            <SelectTrigger size="sm" aria-label="Unsafe recovery plan to inject" className="min-w-0 flex-1">
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
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <Button
            size="sm"
            variant="outline"
            disabled={off}
            onClick={p.onStale}
            title="Block this recovery plan's gate on the server while the screen keeps the old plan. Then try to approve."
          >
            <TimerReset aria-hidden />
            Late change
          </Button>
          <Button size="sm" variant="outline" disabled={off} onClick={p.onTamper} title="Edit the decision log, then check it">
            <FileWarning aria-hidden />
            Tamper log
          </Button>
        </div>
      </div>
    </section>
  );
}

/** The hint shown in place of the diagram when runways and gates are clicked in 3D. */
export function SceneHint() {
  return (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <MousePointerClick aria-hidden className="size-4" />
      Click a runway or gate in the scene to close it.
    </p>
  );
}

const TONE = {
  ok: { icon: CircleCheck, cls: "border-success/40", iconCls: "text-success" },
  bad: { icon: CircleAlert, cls: "border-destructive/50", iconCls: "text-destructive" },
  info: { icon: Info, cls: "border-border", iconCls: "text-muted-foreground" },
} as const;

const SHOW_MS = 9000;

/**
 * The result of the last try-to-break-it action, shown once near the top of
 * the stage. It closes itself after a few seconds, or on X.
 */
export function BreakNotice({ outcome, className }: { outcome: BreakOutcome | null; className?: string }) {
  const [closed, setClosed] = useState<BreakOutcome | null>(null);

  useEffect(() => {
    if (!outcome) return;
    const t = window.setTimeout(() => setClosed(outcome), SHOW_MS);
    return () => window.clearTimeout(t);
  }, [outcome]);

  const visible = outcome && closed !== outcome ? outcome : null;
  const tone = visible ? TONE[visible.tone] : null;

  return (
    <div role="status" aria-live="polite" className={className}>
      {visible && tone && (
        <p
          className={cn(
            "flex max-w-md items-start gap-2 rounded-xl border bg-card/95 py-2 pr-1.5 pl-3 text-sm shadow-lg shadow-black/40 backdrop-blur-xl animate-in fade-in slide-in-from-top-2",
            tone.cls,
          )}
        >
          <tone.icon aria-hidden className={cn("mt-0.5 size-4 shrink-0", tone.iconCls)} />
          <span className="flex-1">
            <strong className="font-semibold">{visible.title}.</strong>{" "}
            <span className="text-muted-foreground">{visible.detail}</span>
          </span>
          <button
            type="button"
            onClick={() => setClosed(visible)}
            aria-label="Dismiss"
            className="rounded-md p-0.5 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X aria-hidden className="size-4" />
          </button>
        </p>
      )}
    </div>
  );
}
