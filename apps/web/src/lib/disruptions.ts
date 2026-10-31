import type { Run, RunOverrides } from "@/lib/api-types";

export type DisruptionId = "runway" | "equipment" | "weather";

/** A preset either applies, as new overrides plus the sentence saying how it is modelled, or it cannot, and says why. */
export type Disruption =
  | { id: DisruptionId; ok: true; overrides: RunOverrides; modelled: string }
  | { id: DisruptionId; ok: false; reason: string };

export const DISRUPTION_LABELS: Record<DisruptionId, string> = {
  runway: "Runway closes",
  equipment: "Ground equipment fails",
  weather: "Weather worsens",
};

const list = (ids: string[]) => (ids.length > 1 ? `${ids.slice(0, -1).join(", ")} and ${ids[ids.length - 1]}` : ids[0]);

/**
 * Work out each preset from what is on screen. Presets only use the existing
 * overrides (closed_runways, closed_gates), so the API sees nothing new.
 * `runways` is the same list the detailed controls show.
 */
export function planDisruptions(
  run: Run | null,
  overrides: RunOverrides,
  runways: { id: string; closed: boolean }[],
): Record<DisruptionId, Disruption> {
  const deal = run?.decision.kind === "DEAL" ? run.decision.package : null;
  const closedRunways = overrides.closed_runways ?? [];
  const closedGates = overrides.closed_gates ?? [];
  const open = runways.filter((r) => !r.closed && !closedRunways.includes(r.id)).map((r) => r.id);

  // Runway closes: the plan's runway if it is open, else the first open one.
  const target = deal && open.includes(deal.runway_id) ? deal.runway_id : open[0];
  const runway: Disruption = target
    ? {
        id: "runway",
        ok: true,
        overrides: { ...overrides, closed_runways: [...closedRunways, target] },
        modelled: `Runway closure, modelled as closing runway ${target}`,
      }
    : { id: "runway", ok: false, reason: "Runway closes needs an open runway, and none is open." };

  // Ground equipment fails: the plan's gate.
  let equipment: Disruption;
  if (!deal) {
    equipment = { id: "equipment", ok: false, reason: "Ground equipment fails needs a plan gate, and this run has no plan." };
  } else if (closedGates.includes(deal.gate_id)) {
    equipment = { id: "equipment", ok: false, reason: `Gate ${deal.gate_id} is already blocked.` };
  } else {
    equipment = {
      id: "equipment",
      ok: true,
      overrides: { ...overrides, closed_gates: [...closedGates, deal.gate_id] },
      modelled: `Ground equipment failure, modelled as blocking gate ${deal.gate_id}`,
    };
  }

  // Weather worsens: keep one open runway, preferring one the plan does not use so the plan has to move.
  let weather: Disruption;
  if (open.length < 2) {
    weather = {
      id: "weather",
      ok: false,
      reason:
        open.length === 1
          ? `Weather worsens needs two or more open runways, and only ${open[0]} is open.`
          : "Weather worsens needs two or more open runways, and none is open.",
    };
  } else {
    const keep = open.find((id) => id !== deal?.runway_id) ?? open[0];
    const close = open.filter((id) => id !== keep);
    weather = {
      id: "weather",
      ok: true,
      overrides: { ...overrides, closed_runways: [...closedRunways, ...close] },
      modelled: `Weather worsening, modelled as closing runway${close.length > 1 ? "s" : ""} ${list(close)} and keeping ${keep} open`,
    };
  }

  return { runway, equipment, weather };
}
