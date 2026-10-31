/**
 * How a plan absorbs the delay. Mirrors FlightPlanAction in the API
 * (apps/api/app/negotiation/contracts.py): the values are the enum's.
 */
export type FlightPlanAction = "direct" | "hold" | "vector" | "ground_delay";

const ACTIONS: readonly FlightPlanAction[] = ["direct", "hold", "vector", "ground_delay"];

/**
 * The action named at the end of a plan label such as
 * "Runway 27L, 14:35, gate B12, hold". The API's TypeScript types carry only
 * the label, so this reads its last part. Returns undefined when the label
 * names none, so a caller never draws a hold it cannot vouch for.
 */
export function planActionFromLabel(label: string | null | undefined): FlightPlanAction | undefined {
  if (!label) return undefined;
  const last = label.split(",").pop()?.trim().toLowerCase().replace(/[\s-]+/g, "_");
  return ACTIONS.find((a) => a === last);
}
