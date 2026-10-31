import type { Evaluation, ScenarioSummary } from "@/lib/api-types";

export interface MockScenario {
  summary: ScenarioSummary;
  /** Fuel data missing: ends in a system fault, not a legal block. */
  systemFault?: boolean;
  /** A model call times out, so the rule-based fallback decides. */
  fallbackFault?: boolean;
}

/**
 * Sample flights for mock mode. Which flight, its route, its scheduled arrival
 * and the cause come from real rows of data/flights.csv (US DOT 2015): DL 986
 * 2015-02-22, AA 90 2015-01-02, AS 687 2015-01-03, WN 489 2015-01-06,
 * B6 518 2015-01-09, NK 612 2015-01-13. The next leg is the same aircraft's
 * next scheduled flight that day: flight, route and time are real. Every delay
 * figure is INVENTED, so the as-flown delays in flights.csv never serve as
 * inputs. Invented values are marked "synthetic", and so is the next leg
 * because its delay is shown with it. Mock mode says so on screen.
 */
export const MOCK_SCENARIOS: MockScenario[] = [
  {
    summary: {
      scenario_id: "mock-001",
      flight_id: "DL 986",
      route: "ATL to LGA",
      scheduled_arrival: "09:54",
      cause: "weather",
      delay_provenance: "synthetic",
      delay_minutes: 35,
      next_leg: { flight_id: "DL 2077", route: "LGA to MCO", scheduled_departure: "16:30", delay_minutes: 25, provenance: "synthetic" },
    },
  },
  {
    summary: {
      scenario_id: "mock-002",
      flight_id: "AA 90",
      route: "DFW to ORD",
      scheduled_arrival: "08:05",
      cause: "late_aircraft",
      delay_provenance: "synthetic",
      delay_minutes: 70,
      next_leg: { flight_id: "AA 1538", route: "ORD to TUS", scheduled_departure: "09:40", delay_minutes: 38, provenance: "synthetic" },
    },
  },
  {
    summary: {
      scenario_id: "mock-003",
      flight_id: "AS 687",
      route: "DEN to SEA",
      scheduled_arrival: "20:01",
      cause: "weather",
      delay_provenance: "synthetic",
      delay_minutes: 52,
      next_leg: { flight_id: "AS 534", route: "SEA to ONT", scheduled_departure: "20:55", delay_minutes: 44, provenance: "synthetic" },
    },
    fallbackFault: true,
  },
  {
    summary: {
      scenario_id: "mock-004",
      flight_id: "WN 489",
      route: "MDW to BNA",
      scheduled_arrival: "14:50",
      cause: "late_aircraft",
      delay_provenance: "synthetic",
      delay_minutes: 41,
      next_leg: { flight_id: "WN 2300", route: "BNA to MDW", scheduled_departure: "15:20", delay_minutes: 33, provenance: "synthetic" },
    },
  },
  {
    summary: {
      scenario_id: "mock-005",
      flight_id: "B6 518",
      route: "JFK to BOS",
      scheduled_arrival: "11:33",
      cause: "weather",
      delay_provenance: "synthetic",
      delay_minutes: 48,
      next_leg: { flight_id: "B6 117", route: "BOS to JFK", scheduled_departure: "12:10", delay_minutes: 40, provenance: "synthetic" },
    },
  },
  {
    summary: {
      scenario_id: "mock-006",
      flight_id: "NK 612",
      route: "LAS to MSP",
      scheduled_arrival: "05:26",
      cause: "late_aircraft",
      delay_provenance: "synthetic",
      delay_minutes: 65,
      next_leg: { flight_id: "NK 612", route: "MSP to ORD", scheduled_departure: "06:17", delay_minutes: 55, provenance: "synthetic" },
    },
    systemFault: true,
  },
];

export const MOCK_EVALUATION: Evaluation = {
  rows: [
    {
      arm: "guarded",
      metric: "Runs where the agents agreed and every rule passed",
      value: 0.62,
      interval: [0.47, 0.75],
      n: 30,
      evidence_class: "unseen",
      commit: "mock0000",
      mode: "mock",
      seed: 7,
    },
    {
      arm: "guarded",
      metric: "Runs that used the rule-based fallback",
      value: 0.27,
      interval: [0.15, 0.43],
      n: 30,
      evidence_class: "unseen",
      commit: "mock0000",
      mode: "mock",
      seed: 7,
    },
    {
      arm: "guarded",
      metric: "Runs with no agreement",
      value: 0.11,
      interval: [0.04, 0.26],
      n: 30,
      evidence_class: "unseen",
      commit: "mock0000",
      mode: "mock",
      seed: 7,
    },
    {
      arm: "guarded",
      metric: "Injected plans that break a rule, blocked",
      value: "4 of 4",
      interval: null,
      n: 4,
      evidence_class: "test",
      commit: "mock0000",
      mode: "mock",
      seed: 1,
    },
    {
      arm: "guarded",
      metric: "Simulated delay difference against first come, first served (minutes)",
      value: 6.4,
      interval: [2.1, 10.3],
      n: 200,
      evidence_class: "rules_only",
      commit: "mock0000",
      mode: "mock",
      seed: 11,
    },
    {
      arm: "unguarded_model",
      metric: "Model plans that break at least one rule",
      value: 0.18,
      interval: [0.08, 0.34],
      n: 30,
      evidence_class: "recorded",
      commit: "mock0000",
      mode: "mock",
      seed: 7,
    },
  ],
  limits: [
    "Sample data only. Every figure on this page is invented for the mock. None is a result.",
    "Results from the real system are simulated outcomes on 2015 US data with invented operational fields. They are not measured savings and say nothing about real operations.",
    "The rules are a small set. Their limits come from the challenge workbook or are our own policy. They are not regulations.",
    "Zero broken rules in 30 live runs still allows a true rate of about 10 percent at 95 percent confidence. The rule check blocks a plan that breaks a rule. The sample size does not show the model never breaks one.",
  ],
};
