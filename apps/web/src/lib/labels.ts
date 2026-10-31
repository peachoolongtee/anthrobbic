import type {
  Cause,
  Domain,
  EvidenceClass,
  FaultKind,
  Provenance,
  RuleStatus,
  RunMode,
  RunPath,
  SignoffStatus,
} from "@/lib/api-types";

/** Words only. No figures are computed here. */

export const DOMAIN_LABEL: Record<Domain, string> = {
  atc: "ATC",
  pilot: "Pilot",
  ground: "Ground",
};

export const DOMAIN_ROLE: Record<Domain, string> = {
  atc: "Air traffic control",
  pilot: "Pilot in command",
  ground: "Ground operations",
};

export const CAUSE_LABEL: Record<Cause, string> = {
  weather: "Weather",
  late_aircraft: "Late aircraft",
};

export const MODE_LABEL: Record<RunMode, { name: string; detail: string }> = {
  off: { name: "Model off", detail: "Rules only. The agents do not negotiate." },
  recorded: { name: "Recorded", detail: "Replays saved model answers. Works offline." },
  live: { name: "Live", detail: "Calls the model now." },
};

export const PROVENANCE_LABEL: Record<Provenance, { name: string; detail: string }> = {
  real: { name: "Real", detail: "Taken from the US DOT flight record" },
  derived: { name: "Derived", detail: "Worked out from real records, such as the same aircraft's next flight" },
  synthetic: { name: "Synthetic", detail: "Invented for this demo, seeded per flight" },
};

export const RULE_STATUS_LABEL: Record<RuleStatus, { name: string; detail: string }> = {
  confirmed: { name: "Regulation", detail: "Confirmed against the published rule" },
  secondary: { name: "Published study", detail: "From a published study, not a rule" },
  unverified: { name: "Unverified", detail: "Not yet verified against its source" },
  policy: { name: "Policy, not regulation", detail: "Our own limit, shaped on a regulation. It is not the regulation." },
  assumption: { name: "Assumption", detail: "A demo default that is not from a regulation" },
  scenario_defined: { name: "Set by the scenario", detail: "The limit comes from the scenario data, not a regulation" },
  unknown: { name: "Basis unknown", detail: "The basis of this limit is not known" },
};

export const PATH_LABEL: Record<RunPath, string> = {
  consensus: "Agents agreed",
  fallback: "Rule-based fallback",
  no_deal: "No agreement",
};

export const FAULT_LABEL: Record<FaultKind, string> = {
  model_off: "Model off",
  missing_key: "No model key",
  auth_failure: "Model key refused",
  rate_limit: "Rate limited",
  timeout: "Timed out",
  wall_clock_cap: "Time limit reached",
  connection_error: "Could not reach the model",
  malformed_output: "Unreadable answer",
  max_tokens: "Answer cut off",
  hallucinated_package: "Named a plan not offered",
  api_error: "Model error",
  refusal: "Agent refused",
  recording_miss: "No recording",
  consensus_recheck_failed: "Agreed plan failed the re-check",
  package_bound: "Too many candidate plans",
  scenario_data: "Scenario data problem",
  sink_failure: "Log write failed",
  internal_error: "Internal error",
  turn_cap: "Turn limit reached",
  missing_data: "Missing data",
};

export const EVIDENCE_LABEL: Record<EvidenceClass, { name: string; detail: string }> = {
  unseen: { name: "Unseen", detail: "Held-out cases scored once before any tuning" },
  tuned: { name: "Tuned", detail: "Cases the prompts were tuned on. Never compare with unseen." },
  recorded: { name: "Recorded", detail: "Replayed from saved model answers" },
  live: { name: "Live", detail: "Run against the live model" },
  rules_only: { name: "Rules only", detail: "Model off. Code and rules alone" },
  test: { name: "Test", detail: "An automated test, not a sample" },
};

export const UNSAFE_OPTIONS: { value: string; label: string }[] = [
  { value: "PLT-FUEL-POLICY", label: "Too little fuel" },
  { value: "ATC-RWY-CLOSED", label: "Closed runway" },
  { value: "ATC-WAKE-SEP", label: "Too close behind" },
  { value: "GND-GATE-OVERLAP", label: "Occupied gate" },
];

export const SIGNOFF_STATUS: Record<SignoffStatus, { title: string; detail: string }> = {
  APPROVED: {
    title: "Approved",
    detail: "Requests were issued, not granted. Nothing has been executed.",
  },
  REFUSED_STATE_CHANGED: {
    title: "Refused: the airport changed after you looked",
    detail: "The plan you saw was made for an earlier state. Make a new recovery plan.",
  },
  REFUSED_PACKAGE_CHANGED: {
    title: "Refused: this is not the recovery plan you were shown",
    detail: "The plan being signed differs from the one on screen.",
  },
  REFUSED_CARD_CHANGED: {
    title: "Refused: the plan summary is not the one you saw",
    detail: "What the plan summary says now differs from what was on screen when you decided.",
  },
  REFUSED_RULES_FAILED: {
    title: "Refused: a rule fails now",
    detail: "The plan broke a hard rule when checked again against the current state.",
  },
  REFUSED_ALREADY_USED: {
    title: "Refused: this approval was already used",
    detail: "Each approval can be used once. Make a new recovery plan to approve again.",
  },
  REFUSED_NOT_ELIGIBLE: {
    title: "Refused: this plan was not offered for sign-off",
    detail: "Only a plan the system itself offered for this flight can be approved.",
  },
  REFUSED_ALREADY_DECIDED: {
    title: "Refused: this run was already decided",
    detail: "A run has one final decision, and this one is recorded. Make a new recovery plan to decide again.",
  },
};

/** Why a log failed its check, in plain words. Unknown reasons are shown as received. */
const VERIFY_REASON_LABEL: Record<string, string> = {
  malformed_entry: "A log line cannot be read.",
  seq_mismatch: "An entry was deleted, moved or inserted.",
  prev_hash_mismatch: "An entry no longer links to the one before it.",
  entry_hash_mismatch: "An entry's content was edited.",
  anchor_not_found: "The log was rewritten or cut short: its recorded head is missing.",
  non_canonical_line: "A log line was rewritten: it is not in the exact form it was written in.",
  file_diverged: "The log file no longer matches what this service wrote.",
  log_failed: "A log write failed and could not be undone, so this log is closed.",
};

export function verifyReasonLabel(reason: string | null): string {
  if (reason === null) return "";
  return VERIFY_REASON_LABEL[reason] ?? reason;
}

/** Log entry kinds with a plain name. Others are shown as logged. */
const LOG_KIND_LABEL: Record<string, string> = {
  plan_rejected: "Plan rejected by the duty manager",
  case_taken_over: "Case taken over by the duty manager",
  decision_refused: "Decision refused: this run was already decided",
  signoff: "Sign-off",
  state_change: "Airport state changed",
};

export function logKindLabel(kind: string): string {
  return LOG_KIND_LABEL[kind] ?? kind;
}

export function signoffStatusLabel(status: string): { title: string; detail: string } {
  return (
    (SIGNOFF_STATUS as Record<string, { title: string; detail: string }>)[status] ?? {
      title: status.startsWith("REFUSED") ? `Refused (${status})` : status,
      detail: "",
    }
  );
}

export const isApproved = (status: string) => status === "APPROVED";

export const UNATTRIBUTED = "unattributed";

/** Scenario fields, in plain words. Unknown names are shown as received. */
const STATE_FIELD_LABEL: Record<string, string> = {
  runways: "Runways",
  taxiways: "Taxiways",
  gates: "Gates",
  gate_occupancies: "Gate occupancy",
  other_arrivals: "Other arrivals",
  destination_forecast: "Destination weather forecast",
  fuel_on_board_kg: "Fuel on board",
  trip_fuel_kg: "Trip fuel",
  planned_gate: "Planned gate",
  next_departure_min: "Next flight departure",
  ground_shift_end_min: "Ground shift end",
  connections: "Passenger connections",
  earliest_arrival_min: "Earliest arrival",
  latest_arrival_min: "Latest arrival",
};

/** Card facts, in plain words. */
const CARD_FIELD_LABEL: Record<string, string> = {
  kind: "Summary type",
  package_name: "Plan name",
  terms_hash: "Plan terms",
  headline: "Headline",
  authority: "Who decides what",
  what_to_do: "What to do",
  why: "Why",
  what_could_go_wrong: "What could go wrong",
  rules: "Rule results",
  costs: "Costs",
  provenance: "Where values came from",
  all_rules_passed: "Whether every rule passed",
};

export function changedFieldLabel(name: string, kind: "state" | "summary"): string {
  if (name === UNATTRIBUTED) return "The system cannot say which field changed";
  const map = kind === "state" ? STATE_FIELD_LABEL : CARD_FIELD_LABEL;
  return map[name] ?? name;
}

export const TERM_LABEL: Record<string, string> = {
  gate_id: "Gate",
  slot: "Arrival slot",
  action: "Delay handling",
};
