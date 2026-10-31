"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { STARTS_LIVE } from "@/lib/api";
import type { RunMode } from "@/lib/api-types";
import { MODE_LABEL } from "@/lib/labels";
import { APP_HEADER, AppNav } from "@/components/app-nav";

// A build that starts in Live offers Recorded only as the offline backup, so
// Model off is left out. Every other build keeps all three.
const MODES: RunMode[] = STARTS_LIVE ? ["live", "recorded"] : ["off", "recorded", "live"];

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
    <header className={`relative ${APP_HEADER}`}>
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
