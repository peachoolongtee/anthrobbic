import type { Evaluation, ScenarioSummary } from "@/lib/api-types";

export interface MockScenario {
  summary: ScenarioSummary;
  /** Fuel data missing: ends in a system fault, not a legal block. */
  systemFault?: boolean;
  /** A model call times out, so the rule-based fallback decides. */
  fallbackFault?: boolean;
}

export const MOCK_SCENARIOS: MockScenario[] = [
  {
    summary: {
      scenario_id: "mock-001",
      flight_id: "DL 2217",
      route: "ATL to LGA",
      scheduled_arrival: "14:35",
      cause: "weather",
      delay_minutes: 62,
      next_leg: { flight_id: "DL 2218", route: "LGA to ATL", scheduled_departure: "16:10", delay_minutes: 41 },
    },
  },
  {
    summary: {
      scenario_id: "mock-002",
      flight_id: "AA 903",
      route: "DFW to ORD",
      scheduled_arrival: "13:10",
      cause: "late_aircraft",
      delay_minutes: 38,
      next_leg: { flight_id: "AA 904", route: "ORD to DFW", scheduled_departure: "14:30", delay_minutes: 21 },
    },
  },
  {
    summary: {
      scenario_id: "mock-003",
      flight_id: "UA 512",
      route: "DEN to SEA",
      scheduled_arrival: "17:45",
      cause: "weather",
      delay_minutes: 47,
      next_leg: { flight_id: "UA 513", route: "SEA to DEN", scheduled_departure: "19:05", delay_minutes: 30 },
    },
    fallbackFault: true,
  },
  {
    summary: {
      scenario_id: "mock-004",
      flight_id: "WN 3340",
      route: "MDW to BNA",
      scheduled_arrival: "11:20",
      cause: "late_aircraft",
      delay_minutes: 26,
      next_leg: null,
    },
  },
  {
    summary: {
      scenario_id: "mock-005",
      flight_id: "B6 615",
      route: "JFK to BOS",
      scheduled_arrival: "09:55",
      cause: "weather",
      delay_minutes: 74,
      next_leg: { flight_id: "B6 616", route: "BOS to JFK", scheduled_departure: "10:50", delay_minutes: 58 },
    },
  },
  {
    summary: {
      scenario_id: "mock-006",
      flight_id: "NK 221",
      route: "LAS to MSP",
      scheduled_arrival: "20:15",
      cause: "late_aircraft",
      delay_minutes: 33,
      next_leg: { flight_id: "NK 222", route: "MSP to LAS", scheduled_departure: "21:30", delay_minutes: 19 },
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
      metric: "Unsafe injected plans caught",
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
      metric: "Delay avoided against first come, first served",
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
    "Sample data only. Every figure on this page is invented for the mock.",
    "Results from the real system are simulated outcomes on 2015 US data with invented operational fields. They are not measured savings.",
    "The rules are a subset of real air traffic procedure.",
    "Zero broken rules in 30 live runs still allows a true rate of about 10 percent at 95 percent confidence. Safety rests on the rule check, not on the sample.",
  ],
};
