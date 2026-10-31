"use client";

import { useState } from "react";
import { Ban, CircleAlert, CircleCheck, Info, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
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
  onRunway: (id: string) => void;
  onGate: (id: string) => void;
  onUnsafe: (ruleId: string) => void;
  onStale: () => void;
  onTamper: () => void;
  onReset: () => void;
}

/** Resources to offer: the API's airport list, else what the plan and overrides name. */
function options(run: Run | null, kind: "runways" | "gates", closed: string[]): { id: string; closed: boolean }[] {
  if (run?.airport) return run.airport[kind];
  const ids = new Set<string>(closed);
  if (run?.decision.kind === "DEAL") ids.add(kind === "runways" ? run.decision.package.runway_id : run.decision.package.gate_id);
  return [...ids].map((id) => ({ id, closed: closed.includes(id) }));
}

/** A pressed toggle means the resource is closed: red, with an icon, never colour alone. */
const CLOSED_STYLE =
  "aria-pressed:border-destructive aria-pressed:bg-destructive aria-pressed:text-background aria-pressed:hover:bg-destructive/90";

const TONE = {
  ok: { icon: CircleCheck, cls: "border-success/40 bg-success-soft", iconCls: "text-success" },
  bad: { icon: CircleAlert, cls: "border-destructive/40 bg-destructive-soft", iconCls: "text-destructive" },
  info: { icon: Info, cls: "border-info/40 bg-info-soft", iconCls: "text-info" },
} as const;

export function BreakItDock(p: Props) {
  const [unsafe, setUnsafe] = useState<string>(UNSAFE_OPTIONS[0].value);
  const closedRunways = p.overrides.closed_runways ?? [];
  const closedGates = p.overrides.closed_gates ?? [];
  const runways = options(p.run, "runways", closedRunways);
  const gates = options(p.run, "gates", closedGates);
  // A runway the scenario itself closed shows as closed, and cannot be toggled open.
  const closedInScenario = runways.filter((r) => r.closed && !closedRunways.includes(r.id)).map((r) => r.id);
  const runwayValue = [...closedRunways, ...closedInScenario];
  const off = p.disabled || p.busy !== null || p.run === null;
  const hasOverrides = closedRunways.length > 0 || closedGates.length > 0 || !!p.overrides.inject_unsafe;
  const tone = p.outcome ? TONE[p.outcome.tone] : null;
  const Icon = tone?.icon;

  return (
    <section
      aria-labelledby="break-heading"
      className="shrink-0 border-t bg-card px-3 py-2 lg:sticky lg:bottom-0 lg:z-10"
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-2">
        <h2 id="break-heading" className="flex items-center gap-1.5 text-sm font-semibold">
          <Wrench aria-hidden className="size-4" />
          Try to break it
        </h2>

        <div className="flex items-center gap-1.5">
          <span id="rwy-label" className="text-xs text-muted-foreground">
            Close runway
          </span>
          <ToggleGroup
            aria-labelledby="rwy-label"
            multiple
            variant="outline"
            size="sm"
            spacing={0}
            value={runwayValue}
            disabled={off}
            onValueChange={(next) => {
              const changed = next.find((v) => !runwayValue.includes(v)) ?? runwayValue.find((v) => !next.includes(v));
              if (changed) p.onRunway(changed);
            }}
          >
            {runways.map((r) => (
              <ToggleGroupItem
                key={r.id}
                value={r.id}
                aria-label={`Runway ${r.id}, ${r.closed ? "closed" : "open"}`}
                title={closedInScenario.includes(r.id) ? "Closed in this scenario" : undefined}
                disabled={off || closedInScenario.includes(r.id)}
                className={CLOSED_STYLE}
              >
                {r.closed && <Ban aria-hidden className="size-3" />}
                {r.id}
                {r.closed && <span className="sr-only"> closed</span>}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        <div className="flex items-center gap-1.5">
          <span id="gate-label" className="text-xs text-muted-foreground">
            Block gate
          </span>
          <ToggleGroup
            aria-labelledby="gate-label"
            multiple
            variant="outline"
            size="sm"
            spacing={0}
            value={closedGates}
            disabled={off}
            onValueChange={(next) => {
              const changed = next.find((v) => !closedGates.includes(v)) ?? closedGates.find((v) => !next.includes(v));
              if (changed) p.onGate(changed);
            }}
          >
            {gates.map((g) => (
              <ToggleGroupItem
                key={g.id}
                value={g.id}
                aria-label={`Gate ${g.id}, ${g.closed ? "blocked" : "free"}`}
                className={CLOSED_STYLE}
              >
                {g.closed && <Ban aria-hidden className="size-3" />}
                {g.id}
                {g.closed && <span className="sr-only"> blocked</span>}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        <div className="flex items-center gap-1.5">
          <Select items={UNSAFE_OPTIONS} value={unsafe} onValueChange={(v) => v && setUnsafe(v)} disabled={off}>
            <SelectTrigger size="sm" aria-label="Unsafe plan to inject" className="w-34">
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
          <Button size="sm" variant="outline" disabled={off} onClick={() => p.onUnsafe(unsafe)}>
            Inject
          </Button>
        </div>

        <Button
          size="sm"
          variant="outline"
          disabled={off}
          onClick={p.onStale}
          title="Blocks the plan's gate on the server while this screen keeps showing the old plan. Then try to approve."
        >
          Change airport state
        </Button>
        <Button size="sm" variant="outline" disabled={off} onClick={p.onTamper}>
          Tamper with log
        </Button>
        <Button size="sm" variant="ghost" disabled={off || !hasOverrides} onClick={p.onReset}>
          Reset
        </Button>
      </div>

      <div role="status" aria-live="polite" className="mt-1.5 min-h-7">
        {p.busy !== null && <p className="text-sm text-muted-foreground">Running&hellip;</p>}
        {p.busy === null && p.outcome && tone && Icon && (
          <p className={cn("flex items-start gap-2 rounded-md border px-2.5 py-1 text-sm", tone.cls)}>
            <Icon aria-hidden className={cn("mt-0.5 size-4 shrink-0", tone.iconCls)} />
            <span>
              <strong>{p.outcome.title}.</strong> {p.outcome.detail}
            </span>
          </p>
        )}
        {p.busy === null && !p.outcome && (
          <p className="text-xs text-muted-foreground">
            Each control changes the situation and shows its result here.
          </p>
        )}
      </div>
    </section>
  );
}
