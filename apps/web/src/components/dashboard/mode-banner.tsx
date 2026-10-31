"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { RunMode } from "@/lib/api-types";
import { MODE_LABEL } from "@/lib/labels";
import { AppNav } from "@/components/app-nav";

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
  return (
    <header className="relative z-20 flex h-12 shrink-0 items-center gap-3 border-b border-border bg-background/70 px-3 backdrop-blur">
      <AppNav />
      <span role="status" className="sr-only">
        Current mode: {MODE_LABEL[mode].name}. {MODE_LABEL[mode].detail}
      </span>
      <div className="flex-1" />

      <ToggleGroup
        aria-label="Run mode"
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
          <ToggleGroupItem key={m} value={m} title={MODE_LABEL[m].detail} aria-label={`${MODE_LABEL[m].name}. ${MODE_LABEL[m].detail}`}>
            {MODE_LABEL[m].name}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </header>
  );
}
