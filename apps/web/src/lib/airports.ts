import { AIRPORT_POSITIONS } from "@/lib/airports-data";

/**
 * Airport positions for the map and the globe, as [latitude, longitude].
 * Generated from data/airports.csv; see scripts/gen-airports.mjs.
 */
export const AIRPORTS: Record<string, [number, number]> = AIRPORT_POSITIONS;

/** Splits a route such as "ATL to LGA" into airport codes. */
export function routeCodes(route: string): [string, string] | null {
  const parts = route.split(" to ");
  return parts.length === 2 ? [parts[0].trim(), parts[1].trim()] : null;
}
