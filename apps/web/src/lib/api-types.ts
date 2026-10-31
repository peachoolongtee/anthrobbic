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
/** The basis of a rule's limit, from rule_values.py and card.py. */
export type RuleStatus =
  | "confirmed"
  | "secondary"
  | "unverified"
  | "policy"
  | "assumption"
  | "scenario_defined"
  | "unknown";
export type NoDealReason = "NOTHING_LEGAL" | "SYSTEM_FAULT";

export interface NextLeg {
  flight_id: string;
  route: string;
  /** 24-hour local time, already formatted by the API. */
  scheduled_departure: string;
  /** Minutes of delay that reach this flight if nothing is done. Null when an input is unknown. */
  delay_minutes: number | null;
  /** (addition) Provenance of the next leg itself. */
  provenance?: Provenance;
  /** (addition) Provenance of `delay_minutes`, which rests on synthetic aircraft size. */
  delay_provenance?: Provenance;
}

export interface ScenarioSummary {
  scenario_id: string;
  flight_id: string;
  route: string;
  /** 24-hour local time, already formatted by the API. */
  scheduled_arrival: string;
  cause: Cause;
  delay_minutes: number;
  /** (addition) Provenance of `delay_minutes`. The badge is shown only when this is given. */
  delay_provenance?: Provenance;
  /** (addition) The same aircraft's next flight, derived from the same file. */
  next_leg?: NextLeg | null;
  /** (addition) True when saved model answers exist for this row. Listed first. */
  has_recording?: boolean;
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
  /** The agent's own reason codes. Unverified. */
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
  /** The requirement, shown when the rule held. */
  label?: string;
  /** What the plan does wrong, shown when it failed. Null when the rule held. */
  message: string | null;
  source: string;
  /** Null when the rule held: the rules report values only when they fail. */
  observed: number | null;
  limit: number | null;
  unit: string;
  /** (addition) Whether the observed value must be at least or at most the limit. */
  direction?: "at_least" | "at_most" | null;
  /** The basis of the limit. */
  status?: RuleStatus;
  /** (addition) card.py's sentence for that basis. */
  status_label?: string;
  /** (addition) Whether the rule held at this state. */
  result?: "pass" | "fail" | "missing_data";
  /** "constraint" for a real limit, "missing_data" when an input was unknown. */
  cause?: "constraint" | "missing_data" | null;
}

export interface RemovedPackage extends PackageRef {
  /** Turn after which the plan was removed. Null when no agent turn ran. */
  removed_in_turn: number | null;
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
  /** (addition) Hash per hashed card fact, sent back as `card_field_hashes_seen`. */
  field_hashes?: Record<string, string>;
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
  | "auth_failure"
  | "rate_limit"
  | "timeout"
  | "wall_clock_cap"
  | "connection_error"
  | "malformed_output"
  | "max_tokens"
  | "hallucinated_package"
  | "api_error"
  | "refusal"
  | "recording_miss"
  | "consensus_recheck_failed"
  | "package_bound"
  | "scenario_data"
  | "sink_failure"
  | "internal_error"
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
  /** Hash string. Sent back as `state_version_seen`. */
  state_version: string;
  /** (addition) Hash per scenario field, so a refusal can name what changed. */
  field_versions?: Record<string, string>;
  path: RunPath;
  /** (addition) Why the fallback ran, e.g. "llm_off". Null when it did not. */
  fallback_trigger?: string | null;
  turns: Turn[];
  removed_packages: RemovedPackage[];
  /** (addition) Illegal plans in all. `removed_packages` shows one per distinct failure. */
  removed_total?: number;
  decision: Decision;
  /** Null when there is no plan to show. */
  card: Card | null;
  model_notes: ModelNote[];
  faults: Fault[];
  log_head: string;
  /** (addition) Current airport state, so the break-it controls list real resources. */
  airport?: AirportState;
}

/** Mirrors SignOffRequest in apps/api/app/negotiation/signoff.py. */
export interface SignoffRequest {
  terms_hash: string;
  state_version_seen: string;
  card_hash_seen: string;
  decided_by: string;
  /** True when the manager approved the "you decide" section. */
  airline_decisions_approved: boolean;
  /** True when the manager chose to send the "you request" section. */
  requests_to_send: boolean;
  field_versions_seen?: Record<string, string>;
  card_field_hashes_seen?: Record<string, string>;
}

export type SignoffStatus =
  | "APPROVED"
  | "REFUSED_STATE_CHANGED"
  | "REFUSED_PACKAGE_CHANGED"
  | "REFUSED_CARD_CHANGED"
  | "REFUSED_RULES_FAILED"
  | "REFUSED_ALREADY_USED";

/** A term of the plan as sign-off returns it, e.g. {name: "gate_id", value: "gate B12"}. */
export interface PackageTerm {
  name: string;
  value: string;
}

/** Mirrors SignOffOutcome. A changed field may be "unattributed". */
export interface SignoffResult {
  status: SignoffStatus;
  package_name?: string;
  violations: RuleResult[];
  changed_fields: string[];
  changed_card_fields: string[];
  airline_decisions: PackageTerm[];
  requests: PackageTerm[];
  card_hash?: string;
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
  /** (addition) The head now, which moves on at state changes and sign-off. */
  head?: string;
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
  n: number | null;
  evidence_class: EvidenceClass;
  commit: string;
  mode: string;
  seed: number | string;
}

export interface Evaluation {
  /** (addition) "not_yet_run" means no evaluation output exists. */
  status?: "ok" | "not_yet_run" | "unreadable";
  rows: EvaluationRow[];
  limits: string[];
}

export interface StateChange {
  closed_runways?: string[];
  closed_gates?: string[];
}
