"use client";

import { FlaskConical, Plane } from "lucide-react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { IS_MOCK } from "@/lib/api";
import type { RunMode } from "@/lib/api-types";
import { MODE_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

const MODES: RunMode[] = ["off", "recorded", "live"];

/** Always on screen. Says which mode produced what is shown below it. */
export function ModeBanner({
  mode,
  onModeChange,
  disabled,
}: {
  mode: RunMode;
  onModeChange: (m: RunMode) => void;
  disabled: boolean;
}) {
  const meta = MODE_LABEL[mode];
  return (
    <header
      className={cn(
        "sticky top-0 z-20 flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-2",
        IS_MOCK ? "bg-warning-soft" : "bg-info-soft",
      )}
    >
      <div className="flex items-center gap-2 font-semibold">
        <Plane aria-hidden className="size-4" />
        Arrival recovery
      </div>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1 text-sm" role="status">
        {IS_MOCK && (
          <span className="inline-flex items-center gap-1 rounded-md bg-warning px-2 py-0.5 text-xs font-bold tracking-wide text-background uppercase">
            <FlaskConical aria-hidden className="size-3.5" />
            Mock
          </span>
        )}
        <span>
          <span className="sr-only">Current mode: </span>
          <strong>{IS_MOCK ? "Mock sample data." : `${meta.name}.`}</strong>{" "}
          {IS_MOCK
            ? "No backend and no model. Every figure is invented."
            : meta.detail}
        </span>
        {IS_MOCK && (
          <span className="text-muted-foreground">
            Run mode: <strong className="text-foreground">{meta.name}</strong>
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span id="run-mode-label" className="text-xs font-medium text-muted-foreground">
          Run mode
        </span>
        <ToggleGroup
          aria-labelledby="run-mode-label"
          variant="outline"
          size="sm"
          spacing={0}
          value={[mode]}
          disabled={disabled}
          onValueChange={(v) => {
            const next = v[0] as RunMode | undefined;
            if (next && next !== mode) onModeChange(next);
          }}
        >
          {MODES.map((m) => (
            <ToggleGroupItem key={m} value={m} aria-label={`${MODE_LABEL[m].name}. ${MODE_LABEL[m].detail}`}>
              {MODE_LABEL[m].name}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
    </header>
  );
}
