"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { LookupQuery, ScenarioSummary } from "@/lib/api-types";
import type { LookupState } from "@/hooks/use-dashboard";
import { useEligibleCount } from "@/hooks/use-eligible-count";

/** "1672" or "UA 1672". An airline code has a letter, so "123" stays a number. */
const FLIGHT = /^\s*((?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{2})?\s*(\d{1,4})\s*$/;
const AIRPORT = /^[A-Za-z]{3}$/;

function parse(date: string, flight: string, origin: string, destination: string): LookupQuery | string {
  if (!date) return "Enter the date of the flight.";
  const match = FLIGHT.exec(flight);
  if (!match || Number(match[2]) < 1) return "Enter a flight number, like 1672 or UA 1672.";
  for (const code of [origin, destination]) {
    if (code && !AIRPORT.test(code)) return "An airport is three letters, like ORD.";
  }
  return {
    date,
    flight_number: Number(match[2]),
    ...(match[1] ? { airline: match[1].toUpperCase() } : {}),
    ...(origin ? { origin: origin.toUpperCase() } : {}),
    ...(destination ? { destination: destination.toUpperCase() } : {}),
  };
}

/** Separate from the search box above, which only filters the flights in the list. */
export function FindFlight({
  lookup,
  onFind,
  onChoose,
}: {
  lookup: LookupState;
  onFind: (query: LookupQuery) => void;
  onChoose: (flight: ScenarioSummary) => void;
}) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState("");
  const [flight, setFlight] = useState("");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [invalid, setInvalid] = useState<string | null>(null);
  const total = useEligibleCount();
  const loading = lookup.status === "loading";

  return (
    <details
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
      className="min-h-0 overflow-y-auto rounded-xl border border-border bg-card/70 px-2.5 py-1.5 text-sm"
    >
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium">
        <Search aria-hidden className="size-3.5" />
        Find any flight
      </summary>
      <form
        className="mt-1.5 space-y-1.5"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          const parsed = parse(date, flight, origin.trim(), destination.trim());
          if (typeof parsed === "string") {
            setInvalid(parsed);
            return;
          }
          setInvalid(null);
          onFind(parsed);
        }}
      >
        <p className="text-xs text-muted-foreground">
          The list is a sample. This searches all{" "}
          {total !== null ? `${total.toLocaleString("en-US")} ` : ""}eligible flights.
        </p>
        <label htmlFor="find-date" className="sr-only">
          Flight date
        </label>
        <Input
          id="find-date"
          type="date"
          min="2015-01-01"
          max="2015-12-31"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <label htmlFor="find-number" className="sr-only">
          Flight number
        </label>
        <Input
          id="find-number"
          placeholder="Flight, like 1672 or UA 1672"
          value={flight}
          onChange={(e) => setFlight(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-1.5">
          <label htmlFor="find-origin" className="sr-only">
            From airport, optional
          </label>
          <Input
            id="find-origin"
            placeholder="From"
            maxLength={3}
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
            className="px-2 text-xs md:text-xs"
          />
          <label htmlFor="find-destination" className="sr-only">
            To airport, optional
          </label>
          <Input
            id="find-destination"
            placeholder="To"
            maxLength={3}
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            className="px-2 text-xs md:text-xs"
          />
        </div>
        <Button type="submit" size="sm" variant="secondary" disabled={loading} className="w-full">
          {loading ? "Searching..." : "Find flight"}
        </Button>

        <div role="status" aria-live="polite" className="text-xs">
          {invalid && <p className="text-destructive">{invalid}</p>}
          {!invalid && lookup.status === "none" && <p>{lookup.message}</p>}
          {!invalid && lookup.status === "error" && (
            <p className="text-destructive">Could not search. {lookup.message}</p>
          )}
          {!invalid && lookup.status === "found" && <p>Found {lookup.flightId}. It is at the top of the list.</p>}
          {!invalid && lookup.status === "several" && (
            <div className="space-y-1">
              <p>
                {lookup.total} flights match.
                {lookup.total > lookup.matches.length && ` The first ${lookup.matches.length} are shown. Add a route to narrow it.`}{" "}
                Pick one:
              </p>
              <ul className="space-y-1">
                {lookup.matches.map((m) => (
                  <li key={m.scenario_id}>
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      className="h-auto w-full justify-between gap-1 whitespace-normal py-1 text-left"
                      onClick={() => onChoose(m)}
                    >
                      <span className="font-semibold">{m.flight_id}</span>
                      <span>
                        {m.route}, due {m.scheduled_arrival}
                      </span>
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </form>
    </details>
  );
}
