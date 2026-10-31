// Boils data/flights.csv (the organisers' file: 2015 US DOT on-time records
// already cut to the challenge's disruption rule, git-ignored) down to the
// figures the overview page shows, written to src/lib/flight-stats.json. Run
// from apps/web:
//   node scripts/summarise-flights.mjs [path/to/flights.csv]
// Every figure is a count or sum over the file; nothing is estimated.
// A row counts only if it was flown, is not in October, and has WEATHER_DELAY
// over 15 or LATE_AIRCRAFT_DELAY over 20. The organiser file holds only such
// rows (358,774), so the rule drops none of them. Run on the full 5,819,079-row
// data/flight-delays/flights.csv, the same rule and month cut give the same
// figures; both were checked against each other.
import { createReadStream, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";

const SOURCE = process.argv[2] ?? new URL("../../../data/flights.csv", import.meta.url);
const TARGET = new URL("../src/lib/flight-stats.json", import.meta.url);

const lines = createInterface({ input: createReadStream(SOURCE), crlfDelay: Infinity });

let header = null;
let rows = 0;
let skipped = 0;
let eligible = 0;
let eligibleWeather = 0;
let eligibleLate = 0;
let eligibleArrivalDelay = 0;
const causeMinutes = { late_aircraft: 0, airline: 0, air_system: 0, weather: 0, security: 0 };
const byDest = new Map();
const byRoute = new Map();
const byHour = Array(24).fill(0);
const months = new Set();

const num = (v) => (v === "" || v === undefined ? 0 : Number(v));

for await (const line of lines) {
  const f = line.split(",");
  if (!header) {
    header = Object.fromEntries(f.map((name, i) => [name, i]));
    continue;
  }
  const get = (name) => f[header[name]];
  rows++;
  if (get("CANCELLED") === "1" || get("MONTH") === "10") {
    skipped++;
    continue;
  }

  const weather = num(get("WEATHER_DELAY"));
  const late = num(get("LATE_AIRCRAFT_DELAY"));

  // The challenge's rule for a usable disruption row.
  if (!(weather > 15 || late > 20)) {
    skipped++;
    continue;
  }
  months.add(get("MONTH"));
  eligible++;
  causeMinutes.late_aircraft += late;
  causeMinutes.airline += num(get("AIRLINE_DELAY"));
  causeMinutes.air_system += num(get("AIR_SYSTEM_DELAY"));
  causeMinutes.weather += weather;
  causeMinutes.security += num(get("SECURITY_DELAY"));

  if (weather > 15) eligibleWeather++;
  if (late > 20) eligibleLate++;
  eligibleArrivalDelay += num(get("ARRIVAL_DELAY"));
  const dest = get("DESTINATION_AIRPORT");
  byDest.set(dest, (byDest.get(dest) ?? 0) + 1);
  const route = `${get("ORIGIN_AIRPORT")}-${dest}`;
  byRoute.set(route, (byRoute.get(route) ?? 0) + 1);
  const hour = Math.floor(Number(get("SCHEDULED_ARRIVAL")) / 100) % 24;
  if (Number.isFinite(hour)) byHour[hour]++;
}

const top = (map, n) =>
  [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([key, count]) => ({ key, count }));

const stats = {
  source: "US DOT on-time records, 2015, organiser file data/flights.csv",
  year: 2015,
  rule: "WEATHER_DELAY over 15 min or LATE_AIRCRAFT_DELAY over 20 min, flown, October left out",
  months: [...months].map(Number).sort((a, b) => a - b),
  rows,
  skipped,
  eligible,
  eligibleWeather,
  eligibleLateAircraft: eligibleLate,
  avgEligibleArrivalDelay: Math.round(eligibleArrivalDelay / Math.max(eligible, 1)),
  causeMinutes,
  topDestinations: top(byDest, 6),
  topRoutes: top(byRoute, 6),
  eligibleByArrivalHour: byHour,
};

writeFileSync(TARGET, JSON.stringify(stats, null, 2) + "\n");
console.log(JSON.stringify({ rows, skipped, eligible, top: stats.topDestinations.slice(0, 3) }));
