import type {
  Cause,
  Domain,
  EvidenceClass,
  FaultKind,
  Provenance,
  RuleStatus,
  RunMode,
  RunPath,
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
  policy: { name: "Policy, not regulation", detail: "Our own limit, shaped on a regulation. It is not the regulation." },
  assumption: { name: "Assumption", detail: "A demo default that is not from a regulation" },
};

export const PATH_LABEL: Record<RunPath, string> = {
  consensus: "Agents agreed",
  fallback: "Rule-based fallback",
  no_deal: "No agreement",
};

export const FAULT_LABEL: Record<FaultKind, string> = {
  model_off: "Model off",
  missing_key: "No model key",
  timeout: "Timed out",
  malformed_output: "Unreadable answer",
  api_error: "Model error",
  refusal: "Agent refused",
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
  { value: "PLT-FUEL-POLICY", label: "Landing with too little fuel" },
  { value: "ATC-RWY-CLOSED", label: "Using a closed runway" },
  { value: "ATC-WAKE-SEP", label: "Landing too close behind a heavy aircraft" },
  { value: "GND-GATE-OVERLAP", label: "Parking at an occupied gate" },
];

/** Refusal statuses are shown as received, with plain names for the known ones. */
export function signoffStatusLabel(status: string): string {
  switch (status) {
    case "APPROVED":
      return "Approved";
    case "REFUSED_STATE_CHANGED":
      return "Refused: the airport changed";
    case "REFUSED_CARD_CHANGED":
      return "Refused: the card changed";
    case "REFUSED_TERMS_CHANGED":
      return "Refused: the plan changed";
    case "REFUSED_RULES":
      return "Refused: a rule now fails";
    default:
      return status.startsWith("REFUSED") ? `Refused (${status})` : status;
  }
}

export const isApproved = (status: string) => status.toUpperCase() === "APPROVED";
