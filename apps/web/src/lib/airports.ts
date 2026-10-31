/** Airport positions for the home page globe, as [latitude, longitude]. */
export const AIRPORTS: Record<string, [number, number]> = {
  ATL: [33.6407, -84.4277],
  BNA: [36.1263, -86.6774],
  BOS: [42.3656, -71.0096],
  DEN: [39.8561, -104.6737],
  DFW: [32.8998, -97.0403],
  JFK: [40.6413, -73.7781],
  LAS: [36.084, -115.1537],
  LGA: [40.7769, -73.874],
  MDW: [41.7868, -87.7522],
  MSP: [44.8848, -93.2223],
  ORD: [41.9742, -87.9073],
  SEA: [47.4502, -122.3088],
};

/** Splits a route such as "ATL to LGA" into airport codes. */
export function routeCodes(route: string): [string, string] | null {
  const parts = route.split(" to ");
  return parts.length === 2 ? [parts[0].trim(), parts[1].trim()] : null;
}
