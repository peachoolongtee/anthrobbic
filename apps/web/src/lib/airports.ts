import { AIRLINE_NAMES } from "@/lib/airlines-data";
import { AIRPORT_PLACES, AIRPORT_POSITIONS } from "@/lib/airports-data";

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

/** The city an airport serves, such as "Las Vegas" for LAS, or null for an unknown code. */
export function airportCity(code: string): string | null {
  return AIRPORT_PLACES[code]?.[1] ?? null;
}

/** The full airport name, such as "McCarran International Airport" for LAS. */
export function airportName(code: string): string | null {
  return AIRPORT_PLACES[code]?.[0] ?? null;
}

/** The airline flying a flight such as "NK 612", from its two-letter code, or null if unknown. */
export function airlineName(flightId: string): string | null {
  return AIRLINE_NAMES[flightId.trim().slice(0, 2).toUpperCase()] ?? null;
}
