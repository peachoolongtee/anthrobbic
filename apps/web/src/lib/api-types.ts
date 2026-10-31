/**
 * Wire shapes for the negotiation API. They mirror
 * apps/api/app/negotiation/contracts.py. Fields marked "(addition)" are not in
 * the agreed route list and need the backend to supply them.
 */

export type Provenance = "real" | "derived" | "synthetic";
export type Domain = "atc" | "pilot" | "ground";
export type RunMode = "off" | "recorded" | "live";
export type RunPath = "consensus" | "fallback" | "no_deal";
export type Cause = "weather" | "late_aircraft";
export type RuleStatus = "confirmed" | "policy" | "assumption";
export type NoDealReason = "NOTHING_LEGAL" | "SYSTEM_FAULT";

export interface NextLeg {
  flight_id: string;
  route: string;
  /** 24-hour local time, already formatted by the API. */
  scheduled_departure: string;
  /** Minutes of delay that reach this flight if nothing is done. */
  delay_minutes: number;
}

export interface ScenarioSummary {
  scenario_id: string;
  flight_id: string;
  route: string;
  /** 24-hour local time, already formatted by the API. */
  scheduled_arrival: string;
  cause: Cause;
  delay_minutes: number;
  /** (addition) The same aircraft's next flight, derived from the same file. */
  next_leg?: NextLeg | null;
}

export interface RunOverrides {
  closed_runways?: string[];
  closed_gates?: string[];
  inject_unsafe?: string;
}

/** A plan reference. `label` is written by the API, e.g. "Runway 27L, 14:35, gate B12, hold". */
export interface PackageRef {
  package_id: string;
  label: string;
}

export interface TurnResponse {
  domain: Domain;
  acceptable_count: number;
  ranking_summary: string;
  /** Plain-language reasons for this agent's answer. */
  reason_codes: string[];
  /** What other agents are told. No private values. */
  public_reason_classes: string[];
}

export interface Turn {
  turn: number;
  responses: TurnResponse[];
}

export interface RuleResult {
  rule_id: string;
  domain: Domain;
  /** Plain-language rule name. */
  label: string;
  message: string;
  source: string;
  observed: number | null;
  limit: number | null;
  unit: string;
  /** (addition) Whether the observed value must be at least or at most the limit. */
  direction?: "at_least" | "at_most";
  status: RuleStatus;
  /** "constraint" for a real limit, "missing_data" when an input was unknown. */
  cause?: "constraint" | "missing_data";
}

export interface RemovedPackage extends PackageRef {
  /** Turn after which the plan was removed. */
  removed_in_turn: number;
  violations: RuleResult[];
  /** (addition) True when the plan came from "inject an unsafe proposal". */
  injected?: boolean;
}

export interface Deal {
  kind: "DEAL";
  /** (addition) Hash of the plan terms, sent back at sign-off. */
  terms_hash: string;
  package: PackageRef & { runway_id: string; gate_id: string };
  packages_considered: number;
  packages_legal: number;
}

export interface NoDeal {
  kind: "NO_DEAL";
  reason_type: NoDealReason;
  /** Rules that blocked every plan, with observed value and limit. */
  binding_rules: RuleResult[];
  packages_considered: number;
  nearest_package: PackageRef | null;
  nearest_violations: RuleResult[];
  /** What would have to change for the nearest plan to pass. */
  what_would_change: string[];
  reason: string;
}

export type Decision = Deal | NoDeal;

export interface Fact {
  key: string;
  label: string;
  value: string;
  provenance: Provenance;
}

export interface Request extends Fact {
  /** Who the request goes to, e.g. "Air traffic control". */
  to: string;
}

export interface Risk {
  text: string;
  /** The rule row this risk points at, so numbers are shown once. */
  rule_id?: string;
}

export interface Card {
  /** Hash of the exact card shown. Sent back at sign-off as `card_hash_seen`. */
  card_hash: string;
  /** The action as one sentence, written from a template. */
  action: string;
  action_facts: Fact[];
  why: string[];
  risks: Risk[];
  airline_decisions: Fact[];
  requests: Request[];
  rules: RuleResult[];
}

export interface ModelNote {
  domain: Domain;
  text: string;
}

export type FaultKind =
  | "model_off"
  | "missing_key"
  | "timeout"
  | "malformed_output"
  | "api_error"
  | "refusal"
  | "turn_cap"
  | "missing_data";

export interface Fault {
  kind: FaultKind;
  domain?: Domain | null;
  turn?: number | null;
  message: string;
}

export interface AirportState {
  runways: { id: string; closed: boolean }[];
  gates: { id: string; closed: boolean }[];
}

export interface Run {
  run_id: string;
  scenario_id: string;
  state_version: number;
  path: RunPath;
  turns: Turn[];
  removed_packages: RemovedPackage[];
  decision: Decision;
  /** Null when there is no plan to show. */
  card: Card | null;
  model_notes: ModelNote[];
  faults: Fault[];
  log_head: string;
  /** (addition) Current airport state, so the break-it controls list real resources. */
  airport?: AirportState;
}

export interface SignoffRequest {
  terms_hash: string;
  state_version_seen: number;
  /** `card.card_hash` of the card on screen when the manager decided. */
  card_hash_seen: string;
  decided_by: string;
  airline_decisions_approved: string[];
  requests_to_send: string[];
}

/**
 * "APPROVED", or a status starting with "REFUSED", e.g. REFUSED_CARD_CHANGED
 * when the card on screen differs from the card now held by the server. The UI
 * treats any other value as a refusal it cannot name and shows it as received.
 */
export type SignoffStatus = string;

export interface SignoffResult {
  status: SignoffStatus;
  /** Human-readable names of what changed since the plan was shown. */
  changed_fields: string[];
  violations: RuleResult[];
  requests: Request[];
  airline_decisions: Fact[];
  log_head: string;
}

export interface LogEntry {
  seq: number;
  kind: string;
  summary: string;
  hash: string;
}

export interface VerifyResult {
  valid: boolean;
  first_bad_seq: number | null;
  reason: string | null;
}

export interface RunLog {
  entries: LogEntry[];
  verify: VerifyResult;
}

export type EvidenceClass =
  | "unseen"
  | "tuned"
  | "recorded"
  | "live"
  | "rules_only"
  | "test";

export interface EvaluationRow {
  /** (addition) "unguarded_model" marks the comparison row. Absent means the guarded system. */
  arm?: "guarded" | "unguarded_model";
  metric: string;
  value: number | string;
  interval: [number, number] | null;
  n: number;
  evidence_class: EvidenceClass;
  commit: string;
  mode: string;
  seed: number | string;
}

export interface Evaluation {
  rows: EvaluationRow[];
  limits: string[];
}

export interface StateChange {
  closed_runways?: string[];
  closed_gates?: string[];
}
