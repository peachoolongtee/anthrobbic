/**
 * In-browser stand-in for the API, used only when NEXT_PUBLIC_API_MODE=mock.
 * Every figure here is invented sample data. It exists so the dashboard can be
 * shown and tested with no backend, and it imitates the real API's behaviour
 * for the "try to break it" controls.
 */
import type {
  AirportState,
  Card,
  Cause,
  DecisionResult,
  DelaySpread,
  Domain,
  Evaluation,
  Fact,
  Headline,
  WorkbookLimits,
  Fault,
  FinalDecision,
  LogEntry,
  LookupQuery,
  LookupResult,
  NoGo,
  RemovedPackage,
  Run,
  RunLog,
  RunMode,
  RunOverrides,
  RuleResult,
  ScenarioSummary,
  SignoffRequest,
  SignoffResult,
  StateChange,
  Turn,
  VerifyResult,
} from "@/lib/api-types";
import {
  MOCK_BELOW_THRESHOLD_FLIGHT,
  MOCK_EVALUATION,
  MOCK_LOOKUP_ONLY,
  MOCK_SCENARIOS,
  type MockScenario,
} from "@/lib/mock/fixtures";

const RUNWAYS = ["27L", "27R"];
const GATES = ["B12", "B14", "C3"];
const DOMAINS: Domain[] = ["atc", "pilot", "ground"];

interface StoredRun {
  scenario: MockScenario;
  mode: RunMode;
  closedRunways: string[];
  closedGates: string[];
  run: Run;
  extraLog: LogEntry[];
  /** One final decision per run, like the real API. */
  final?: FinalDecision;
}

const store = new Map<string, StoredRun>();
/** Single-use approvals, like the real sign-off: terms, state and card as seen. */
const usedTokens = new Set<string>();

function fieldVersions(closedRunways: string[], closedGates: string[]): Record<string, string> {
  return {
    runways: hash(`runways:${[...closedRunways].sort().join()}`),
    gates: hash(`gates:${[...closedGates].sort().join()}`),
    planned_gate: hash("planned_gate"),
    fuel_on_board_kg: hash("fuel"),
  };
}

const versionRoot = (fv: Record<string, string>) => hash(JSON.stringify(fv));

function changedNames(seen: Record<string, string> | undefined, seenRoot: string, current: Record<string, string>): string[] {
  if (!seen || versionRoot(seen) !== seenRoot) return ["unattributed"];
  const names = [...Object.keys(current), ...Object.keys(seen)].filter((n) => seen[n] !== current[n]);
  return Array.from(new Set(names));
}

/** Sign-off violations carry no label or status, as in the real API. */
const bare = (r: RuleResult): RuleResult => ({ ...r, label: undefined, status: undefined });
let counter = 0;

const wait = (ms = 250) => new Promise((r) => setTimeout(r, ms));

function hash(input: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0") + (h ^ 0x9e3779b9).toString(16).padStart(8, "0").slice(-8);
}

function clock(totalMinutes: number): string {
  const m = ((totalMinutes % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

function minutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function rule(
  id: string,
  domain: Domain,
  label: string,
  status: RuleResult["status"],
  observed: number | null,
  limit: number | null,
  unit: string,
  direction: "at_least" | "at_most",
  source: string,
  message: string,
  cause: RuleResult["cause"] = "constraint",
): RuleResult {
  return { rule_id: id, domain, label, message, source, observed, limit, unit, direction, status, cause };
}

const SRC_WAKE = "Challenge workbook (synthetic), simplified from FAA JO 7110.65 para 5-5-4";
const SRC_FUEL = "Challenge workbook (synthetic): 30 minutes of holding fuel plus 5% of trip fuel";
const SRC_CAP = "Challenge workbook (synthetic): runway movements per hour for the airport";
const SRC_TURN = "Challenge workbook (synthetic): minimum turnaround for the airport";
const SRC_ASSUMED = "Assumption: demo default, not from a regulation";

function passingRules(offset: number): RuleResult[] {
  return [
    rule("ATC-WAKE-SEP", "atc", "Spacing behind the aircraft ahead", "organiser_workbook", 6, 5, "NM", "at_least", SRC_WAKE, "Lands too close behind the aircraft ahead"),
    rule("ATC-RWY-THROUGHPUT", "atc", "Arrivals per hour at the airport", "organiser_workbook", 26 + offset, 36, "arrivals/h", "at_most", SRC_CAP, "Puts too many arrivals into the airport in an hour"),
    rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "organiser_workbook", 57 - offset * 3, 30, "min", "at_least", SRC_FUEL, "Lands with less fuel than the workbook reserve allows"),
    rule("GND-GATE-OVERLAP", "ground", "Gap before the next aircraft at the gate", "assumption", 25, 15, "min", "at_least", SRC_ASSUMED, "Uses a gate that is occupied or blocked"),
    rule("GND-TURNAROUND", "ground", "Time to turn the aircraft round", "organiser_workbook", 48, 35, "min", "at_least", SRC_TURN, "Leaves too little time to turn the aircraft round"),
  ];
}

function airport(closedRunways: string[], closedGates: string[]): AirportState {
  return {
    runways: RUNWAYS.map((id) => ({ id, closed: closedRunways.includes(id) })),
    gates: GATES.map((id) => ({ id, closed: closedGates.includes(id) })),
  };
}

const UNSAFE: Record<string, { label: string; rule: RuleResult }> = {
  "PLT-FUEL-POLICY": {
    label: "Land at the earliest slot with no hold, 31 min of fuel left",
    rule: rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "organiser_workbook", 31, 30, "min", "at_least", SRC_FUEL, "Lands with less fuel than the workbook reserve allows"),
  },
  "ATC-RWY-CLOSED": {
    label: "Use a closed runway",
    rule: rule("ATC-RWY-CLOSED", "atc", "Runway is open", "assumption", 1, 0, "closed runways", "at_most", "Scenario state", "Uses a closed runway"),
  },
  "ATC-WAKE-SEP": {
    label: "Land 3 NM behind a heavy aircraft",
    rule: rule("ATC-WAKE-SEP", "atc", "Spacing behind the aircraft ahead", "organiser_workbook", 3, 5, "NM", "at_least", SRC_WAKE, "Lands too close behind the aircraft ahead"),
  },
  "GND-GATE-OVERLAP": {
    label: "Park at an occupied gate",
    rule: rule("GND-GATE-OVERLAP", "ground", "Gap before the next aircraft at the gate", "assumption", 0, 15, "min", "at_least", SRC_ASSUMED, "Uses a gate that is occupied or blocked"),
  },
};

function build(
  runId: string,
  sc: MockScenario,
  mode: RunMode,
  closedRunways: string[],
  closedGates: string[],
  inject: string | undefined,
): Run {
  const openRunways = RUNWAYS.filter((r) => !closedRunways.includes(r));
  const openGates = GATES.filter((g) => !closedGates.includes(g));
  const base = minutes(sc.summary.scheduled_arrival) + sc.summary.delay_minutes;
  const ap = airport(closedRunways, closedGates);

  const removed: RemovedPackage[] = [];
  const pid = (s: string) => hash(`${sc.summary.scenario_id}:${s}`);
  if (!sc.systemFault) {
    removed.push({
      package_id: pid("early"),
      label: `Runway 27L, ${clock(base - 12)}, gate B12, no hold`,
      removed_in_turn: 1,
      violations: [
        rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "organiser_workbook", 41, 30, "min", "at_least", SRC_FUEL, "Lands with less fuel than the workbook reserve allows"),
      ],
    });
    removed.push({
      package_id: pid("wake"),
      label: `Runway 27R, ${clock(base + 2)}, gate B14, vector`,
      removed_in_turn: 1,
      violations: [
        rule("ATC-WAKE-SEP", "atc", "Spacing behind the aircraft ahead", "organiser_workbook", 4, 5, "NM", "at_least", SRC_WAKE, "Lands too close behind the aircraft ahead"),
      ],
    });
  }
  for (const r of closedRunways) {
    removed.push({
      package_id: pid(`rwy${r}`),
      label: `Runway ${r}, ${clock(base)}, gate B12, hold`,
      removed_in_turn: 1,
      violations: [UNSAFE["ATC-RWY-CLOSED"].rule],
    });
  }
  for (const g of closedGates) {
    removed.push({
      package_id: pid(`gate${g}`),
      label: `Runway 27L, ${clock(base)}, gate ${g}, hold`,
      removed_in_turn: 1,
      violations: [UNSAFE["GND-GATE-OVERLAP"].rule],
    });
  }
  if (inject && UNSAFE[inject]) {
    removed.push({
      package_id: pid(`inject${inject}`),
      label: `Injected: ${UNSAFE[inject].label}`,
      removed_in_turn: 1,
      violations: [UNSAFE[inject].rule],
      injected: true,
    });
  }

  const faults: Fault[] = [];
  let noGo: NoGo | null = null;

  if (sc.systemFault) {
    faults.push({
      kind: "missing_data",
      message: "Fuel on board is unknown for this flight, so the fuel rule cannot be checked.",
    });
    noGo = {
      kind: "NO_GO",
      reason_type: "SYSTEM_FAULT",
      binding_rules: [
        rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "organiser_workbook", null, 30, "min", "at_least", SRC_FUEL, "Cannot check fuel left at landing: fuel on board is unknown", "missing_data"),
      ],
      packages_considered: 24,
      nearest_package: null,
      nearest_violations: [],
      what_would_change: ["Supply fuel on board for this flight, then run it again."],
      reason: "The data needed to check the plans is missing. No plan was judged illegal.",
    };
  } else if (openRunways.length === 0) {
    noGo = {
      kind: "NO_GO",
      reason_type: "NOTHING_LEGAL",
      binding_rules: [UNSAFE["ATC-RWY-CLOSED"].rule],
      packages_considered: 24,
      nearest_package: {
        package_id: pid("nearest"),
        label: `Runway 27R, ${clock(base + 6)}, gate ${openGates[0] ?? "B12"}, hold`,
      },
      nearest_violations: [UNSAFE["ATC-RWY-CLOSED"].rule],
      what_would_change: ["Reopen runway 27L or 27R. Every other rule passes for the nearest plan."],
      reason: "Every runway is closed. All 24 plans use a closed runway.",
    };
  } else if (openGates.length === 0) {
    noGo = {
      kind: "NO_GO",
      reason_type: "NOTHING_LEGAL",
      binding_rules: [UNSAFE["GND-GATE-OVERLAP"].rule],
      packages_considered: 24,
      nearest_package: {
        package_id: pid("nearest"),
        label: `Runway ${openRunways[0]}, ${clock(base + 4)}, gate B12, hold`,
      },
      nearest_violations: [UNSAFE["GND-GATE-OVERLAP"].rule],
      what_would_change: ["Free one gate. Every other rule passes for the nearest plan."],
      reason: "Every gate is blocked. All 24 plans use a blocked gate.",
    };
  }

  const modelOff = mode === "off";
  const timedOut = !modelOff && sc.fallbackFault && !noGo;
  let path: Run["path"] = "consensus";
  if (noGo) path = "no_go";
  else if (modelOff || timedOut) path = "fallback";

  if (modelOff) {
    faults.push({
      kind: "model_off",
      message: "The model is switched off, so the agents did not run.",
    });
  }
  if (timedOut) {
    faults.push({
      kind: "timeout",
      domain: "pilot",
      turn: 1,
      message: "The pilot agent did not answer within the time limit. The rule-based fallback chose the plan.",
    });
  }

  const turns: Turn[] = [];
  if (!modelOff) {
    turns.push({
      turn: 1,
      responses: DOMAINS.filter((d) => !(timedOut && d === "pilot")).map((d) => ({
        domain: d,
        acceptable_count: d === "atc" ? 9 : d === "pilot" ? 6 : 4,
        ranking_summary:
          d === "atc" ? "Prefers the earliest slot on 27L" : d === "pilot" ? "Prefers a short hold and the most fuel left" : "Prefers gate B12, no gate change",
        reason_codes: d === "atc" ? ["Keeps arrivals evenly spaced"] : d === "pilot" ? ["Keeps fuel above the reserve"] : ["Keeps the gate gap", "Keeps the crew inside shift"],
        public_reason_classes: [],
      })),
    });
    if (!timedOut) {
      turns.push({
        turn: 2,
        responses: DOMAINS.map((d) => ({
          domain: d,
          acceptable_count: d === "atc" ? 3 : d === "pilot" ? 3 : 2,
          ranking_summary:
            d === "atc" ? "Now accepts the later slot" : d === "pilot" ? "Accepts a longer hold after seeing plans removed" : "Accepts gate B12 or B14",
          reason_codes: d === "ground" ? ["Gate gap holds for B12 and B14"] : ["Revised after seeing which plans were removed"],
          public_reason_classes: d === "atc" ? [] : ["Another domain found some plans infeasible", "Safety margin"],
        })),
      });
    }
  }
  if (noGo && sc.systemFault) turns.length = 0;

  const rwy = openRunways[0] ?? "27L";
  const gate = openGates.includes("B12") ? "B12" : (openGates[0] ?? "B12");
  const arrive = base + (rwy === "27R" ? 6 : 0) + (gate === "B12" ? 0 : 2);
  const label = `Runway ${rwy}, ${clock(arrive)}, gate ${gate}, hold`;

  let decision: Run["decision"];
  let card: Card | null = null;
  if (noGo) {
    decision = noGo;
  } else {
    decision = {
      kind: "DEAL",
      terms_hash: hash(`${sc.summary.scenario_id}${rwy}${arrive}${gate}`),
      package: { package_id: hash(label), label, runway_id: rwy, gate_id: gate },
      packages_considered: 24,
      packages_legal: 11 - removed.length + 2,
    };
    const next = sc.summary.next_leg;
    const facts: Fact[] = [
      { key: "arrival", label: "Arrival time", value: clock(arrive), provenance: "derived" },
      { key: "scheduled", label: "Scheduled arrival", value: sc.summary.scheduled_arrival, provenance: "real" },
      { key: "runway", label: "Runway", value: rwy, provenance: "synthetic" },
      { key: "gate", label: "Gate", value: gate, provenance: "synthetic" },
      { key: "handling", label: "Delay handling", value: "Hold at a fix", provenance: "derived" },
    ];
    const fieldHashes = {
      headline: hash(`headline:${label}`),
      authority: hash(`authority:${gate}:${rwy}:${arrive}`),
      rules: hash(`rules:${rwy}`),
      what_could_go_wrong: hash(`risks:${next ? next.flight_id : "none"}`),
    };
    card = {
      card_hash: hash(JSON.stringify(fieldHashes)),
      field_hashes: fieldHashes,
      action: `Land ${sc.summary.flight_id} at ${clock(arrive)} on runway ${rwy}, park at gate ${gate}, and absorb the delay in a hold.`,
      action_facts: facts,
      why: [
        path === "consensus"
          ? "Air traffic control, the pilot and ground all accepted this plan, and it passed every rule."
          : "The agents did not agree. This is the lowest-cost plan that passes every rule.",
        "It is the earliest arrival that keeps the fuel reserve and the gate gap.",
        ...(closedRunways.length || closedGates.length ? ["Plans using a closed runway or a blocked gate were removed first."] : []),
      ],
      risks: [
        { text: "Fuel left at landing is the tightest margin. A longer hold would break the fuel reserve.", rule_id: "PLT-FUEL-POLICY" },
        ...(next ? [{ text: `Any further delay reaches ${next.flight_id}, the same aircraft's next flight.` }] : []),
        { text: "Weather or traffic can change before the slot is confirmed. Sign-off checks the rules again." },
      ],
      airline_decisions: [
        { key: "gate", label: "Gate", value: gate, provenance: "synthetic" },
        {
          key: "next_leg",
          label: "Next flight",
          value: next ? `Keep ${next.flight_id} on its ${next.scheduled_departure} departure` : "No next flight",
          provenance: "derived",
        },
      ],
      requests: [
        { key: "arrival", label: "Arrival time", value: clock(arrive), provenance: "derived", to: "Air traffic control" },
        { key: "runway", label: "Runway", value: rwy, provenance: "synthetic", to: "Air traffic control" },
        { key: "handling", label: "Delay handling", value: "Hold at a fix", provenance: "derived", to: "Air traffic control and pilot in command" },
      ],
      rules: passingRules(rwy === "27R" ? 1 : 0),
    };
  }

  const head = hash(`${runId}:${path}`);
  return {
    run_id: runId,
    scenario_id: sc.summary.scenario_id,
    state_version: versionRoot(fieldVersions(closedRunways, closedGates)),
    field_versions: fieldVersions(closedRunways, closedGates),
    path,
    turns,
    removed_packages: removed,
    decision,
    card,
    model_notes:
      modelOff || sc.systemFault
        ? []
        : [
            { domain: "pilot", text: "Crew note says the first officer is on a long duty day, so a shorter hold would be better if it fits." },
            { domain: "ground", text: "Ramp reports one tug on another stand until about 15:00." },
          ],
    faults,
    log_head: head,
    airport: ap,
  };
}

/** Appends a log entry and moves the head on, as the real log does. */
function recordDecision(s: StoredRun, runId: string, kind: string, summary: string): string {
  const entryHash = hash(`${runId}:${kind}:${s.extraLog.length}`);
  s.extraLog.push({ seq: 0, kind, summary, hash: entryHash });
  s.run = { ...s.run, log_head: entryHash };
  return entryHash;
}

function recordRefused(s: StoredRun, runId: string, attempted: string): string {
  return recordDecision(
    s,
    runId,
    "decision_refused",
    `status: REFUSED_ALREADY_DECIDED; attempted: ${attempted}; final_decision: ${s.final}; issued: false`,
  );
}

function logFor(s: StoredRun): LogEntry[] {
  const r = s.run;
  const entries: [string, string][] = [
    ["scenario", `Loaded ${s.scenario.summary.flight_id} with provenance labels`],
    ["options", `${r.decision.kind === "DEAL" ? r.decision.packages_considered : 24} candidate plans listed`],
    ["rules", `${r.removed_packages.length} plans removed by the rules`],
    ...r.turns.flatMap((t): [string, string][] =>
      t.responses.map((x) => ["response", `Turn ${t.turn}: ${x.domain} accepted ${x.acceptable_count} plans`]),
    ),
    ["decision", r.path === "no_go" ? "No-go, handed to the duty manager" : `Chose by ${r.path}`],
  ];
  const base = entries.map(([kind, summary], i) => ({
    seq: i + 1,
    kind,
    summary,
    hash: hash(`${s.run.run_id}:${i}:${summary}`),
  }));
  return [...base, ...s.extraLog.map((e, i) => ({ ...e, seq: base.length + i + 1 }))];
}

function need(runId: string): StoredRun {
  const s = store.get(runId);
  if (!s) throw new Error(`Unknown run ${runId}`);
  return s;
}

export const mockBackend = {
  async listScenarios(params: { cause?: Cause; limit?: number }): Promise<ScenarioSummary[]> {
    await wait(200);
    let rows = MOCK_SCENARIOS.map((s) => s.summary);
    if (params.cause) rows = rows.filter((r) => r.cause === params.cause);
    return rows.slice(0, params.limit ?? 50);
  },

  async eligibleCount(): Promise<{ eligible_total: number }> {
    await wait(100);
    return { eligible_total: MOCK_SCENARIOS.length + MOCK_LOOKUP_ONLY.length };
  },

  async lookupFlight(query: LookupQuery): Promise<LookupResult> {
    await wait(250);
    const none = (reason: string, message: string): LookupResult => ({ status: "none", matches: [], total: 0, reason, message });
    if (!query.date.startsWith("2015-")) return none("outside_dataset", "The flight data covers 2015 only.");
    if (query.date.startsWith("2015-10-")) {
      return none(
        "october_excluded",
        "October 2015 is excluded from this data, because that month's airport codes are numeric, not the usual three letters.",
      );
    }
    if (query.flight_number === MOCK_BELOW_THRESHOLD_FLIGHT) {
      return none("below_thresholds", "That flight is in the data, but it is not a disruption case.");
    }
    const matches = [...MOCK_SCENARIOS, ...MOCK_LOOKUP_ONLY]
      .map((s) => s.summary)
      .filter((s) => {
        const [airline, number] = s.flight_id.split(" ");
        const [origin, , destination] = s.route.split(" ");
        return (
          number === String(query.flight_number) &&
          (!query.airline || query.airline.toUpperCase() === airline) &&
          (!query.origin || query.origin.toUpperCase() === origin) &&
          (!query.destination || query.destination.toUpperCase() === destination)
        );
      });
    if (matches.length === 0) {
      return none("not_in_data", `No flight numbered ${query.flight_number} matches that search on ${query.date} in the mock data.`);
    }
    return { status: matches.length === 1 ? "one" : "several", matches, total: matches.length, reason: null, message: null };
  },

  async createRun(body: {
    scenario_id: string;
    mode: RunMode;
    overrides?: RunOverrides;
  }): Promise<Run> {
    await wait(body.mode === "live" ? 900 : 450);
    const sc = [...MOCK_SCENARIOS, ...MOCK_LOOKUP_ONLY].find((s) => s.summary.scenario_id === body.scenario_id);
    if (!sc) throw new Error(`Unknown scenario ${body.scenario_id}`);
    const closedRunways = body.overrides?.closed_runways ?? [];
    const closedGates = body.overrides?.closed_gates ?? [];
    const runId = `mock-run-${++counter}`;
    const run = build(runId, sc, body.mode, closedRunways, closedGates, body.overrides?.inject_unsafe);
    store.set(runId, { scenario: sc, mode: body.mode, closedRunways, closedGates, run, extraLog: [] });
    return run;
  },

  async changeState(runId: string, change: StateChange): Promise<{ state_version: string }> {
    await wait(200);
    const s = need(runId);
    s.closedRunways = Array.from(new Set([...s.closedRunways, ...(change.closed_runways ?? [])]));
    s.closedGates = Array.from(new Set([...s.closedGates, ...(change.closed_gates ?? [])]));
    return { state_version: versionRoot(fieldVersions(s.closedRunways, s.closedGates)) };
  },

  async signoff(runId: string, body: SignoffRequest): Promise<SignoffResult> {
    await wait(350);
    const s = need(runId);
    const deal = s.run.decision;
    const card = s.run.card;
    if (deal.kind !== "DEAL" || !card) throw new Error("There is no plan to sign off");
    const current = fieldVersions(s.closedRunways, s.closedGates);
    const currentRoot = versionRoot(current);
    const violations: RuleResult[] = [];
    if (deal.package.gate_id && s.closedGates.includes(deal.package.gate_id)) violations.push(bare(UNSAFE["GND-GATE-OVERLAP"].rule));
    if (s.closedRunways.includes(deal.package.runway_id)) violations.push(bare(UNSAFE["ATC-RWY-CLOSED"].rule));

    const token = hash([body.terms_hash, body.state_version_seen, body.card_hash_seen].join("|"));
    if (s.final && !(s.final === "APPROVED" && usedTokens.has(token))) {
      return {
        status: "REFUSED_ALREADY_DECIDED",
        final_decision: s.final,
        violations: [],
        changed_fields: [],
        changed_card_fields: [],
        airline_decisions: [],
        requests: [],
        card_hash: card.card_hash,
        log_head: recordRefused(s, runId, "signoff"),
      };
    }
    let status: SignoffResult["status"];
    let changedFields: string[] = [];
    let changedCard: string[] = [];
    if (usedTokens.has(token)) status = "REFUSED_ALREADY_USED";
    else if (body.terms_hash !== deal.terms_hash) status = "REFUSED_PACKAGE_CHANGED";
    else if (body.state_version_seen !== currentRoot) {
      status = "REFUSED_STATE_CHANGED";
      changedFields = changedNames(body.field_versions_seen, body.state_version_seen, current);
    } else if (violations.length > 0) status = "REFUSED_RULES_FAILED";
    else if (!RUNWAYS.includes(deal.package.runway_id) || !GATES.includes(deal.package.gate_id)) {
      // As the real sign-off: only a package this flight's enumeration offers.
      status = "REFUSED_NOT_ELIGIBLE";
    } else if (body.card_hash_seen !== card.card_hash) {
      status = "REFUSED_CARD_CHANGED";
      const seen = body.card_field_hashes_seen;
      const now = card.field_hashes ?? {};
      changedCard =
        seen && hash(JSON.stringify(seen)) === body.card_hash_seen
          ? Object.keys(now).filter((n) => seen[n] !== now[n])
          : ["unattributed"];
      if (changedCard.length === 0) changedCard = ["unattributed"];
    } else status = "APPROVED";

    const approved = status === "APPROVED";
    if (approved) {
      usedTokens.add(token);
      s.final = "APPROVED";
      s.extraLog.push({
        seq: 0,
        kind: "signoff",
        summary: `Approved by ${body.decided_by}. ${body.requests_to_send ? "Requests issued" : "No requests issued"}, nothing executed.`,
        hash: hash(`${runId}:signoff:${body.decided_by}`),
      });
      s.run = { ...s.run, log_head: hash(`${runId}:head:signed`) };
    }
    return {
      status,
      violations,
      changed_fields: changedFields,
      changed_card_fields: changedCard,
      airline_decisions:
        approved && body.airline_decisions_approved ? [{ name: "gate_id", value: `gate ${deal.package.gate_id}` }] : [],
      requests:
        approved && body.requests_to_send
          ? [
              { name: "slot", value: `runway ${deal.package.runway_id} at ${card.action_facts.find((f) => f.key === "arrival")?.value ?? ""}` },
              { name: "action", value: "hold" },
            ]
          : [],
      card_hash: card.card_hash,
      log_head: s.run.log_head,
    };
  },

  async reject(runId: string, body: { decided_by: string; reason?: string }): Promise<DecisionResult> {
    await wait(250);
    const s = need(runId);
    if (s.run.decision.kind !== "DEAL") throw new Error("This run has no plan to reject: it ended in no-go.");
    if (s.final) return { status: "REFUSED_ALREADY_DECIDED", final_decision: s.final, log_head: recordRefused(s, runId, "reject") };
    s.final = "REJECTED";
    return {
      status: "REJECTED",
      final_decision: "REJECTED",
      log_head: recordDecision(s, runId, "plan_rejected", `decided_by: ${body.decided_by}; has_unverified_reason: ${Boolean(body.reason)}; issued: false`),
    };
  },

  async takeOver(runId: string, body: { decided_by: string; note?: string }): Promise<DecisionResult> {
    await wait(250);
    const s = need(runId);
    const decision = s.run.decision;
    if (decision.kind !== "NO_GO") throw new Error("This run has a plan: approve or reject it instead.");
    if (s.final) return { status: "REFUSED_ALREADY_DECIDED", final_decision: s.final, log_head: recordRefused(s, runId, "take_over") };
    s.final = "TAKEN_OVER";
    return {
      status: "TAKEN_OVER",
      final_decision: "TAKEN_OVER",
      log_head: recordDecision(
        s,
        runId,
        "case_taken_over",
        `reason_type: ${decision.reason_type}; decided_by: ${body.decided_by}; has_unverified_note: ${Boolean(body.note)}; issued: false`,
      ),
    };
  },

  async getSpread(runId: string): Promise<DelaySpread> {
    await wait(150);
    const s = need(runId);
    const { flight_id, route, scheduled_arrival, next_leg } = s.scenario.summary;
    return {
      flight_id,
      route,
      tail_number: "mock",
      scheduled_arrival,
      plan_arrival: null,
      plan_arrival_provenance: null,
      legs: next_leg
        ? [
            {
              flight_id: next_leg.flight_id,
              route: next_leg.route,
              scheduled_departure: next_leg.scheduled_departure,
              scheduled_arrival: "",
              provenance: "derived",
              projection: null,
              unprojected_reason: "The mock does not project this. Start the API for a scheduled projection.",
            },
          ]
        : [],
      note: "Mock sample data.",
    };
  },

  /** The mock's record of a run, marked as such, since no API can serve it. */
  consensusLogUrl(runId: string): string {
    const s = need(runId);
    const file = { format: "mock-consensus-log", mock: "Every figure is invented sample data.", run: s.run, entries: logFor(s) };
    return `data:application/json,${encodeURIComponent(JSON.stringify(file, null, 2))}`;
  },

  async getLog(runId: string): Promise<RunLog> {
    await wait(200);
    const s = need(runId);
    return { entries: logFor(s), verify: { valid: true, first_bad_seq: null, reason: null } };
  },

  async verifyLog(runId: string, body: { tamper?: boolean }): Promise<VerifyResult> {
    await wait(250);
    const s = need(runId);
    if (!body.tamper) return { valid: true, first_bad_seq: null, reason: null };
    const seq = Math.min(4, logFor(s).length);
    return {
      valid: false,
      first_bad_seq: seq,
      reason: `Entry ${seq} was edited. Its hash no longer matches the hash stored in entry ${seq + 1}.`,
    };
  },

  async getLimits(): Promise<WorkbookLimits> {
    await wait(100);
    return {
      title: "Where we differ from the challenge workbook (mock: start the API for the checked list)",
      items: [
        {
          id: "mock",
          limit: "Mock sample data",
          what_we_do: "The mock has no list of its own.",
          why: "The real list comes from the API.",
          checked_against: "mock",
        },
      ],
    };
  },

  async getHeadline(): Promise<Headline> {
    await wait(100);
    const rows = MOCK_EVALUATION.rows.slice(0, 2);
    return {
      status: "ok",
      rules_only: rows.map((r) => ({
        key: r.metric,
        label: r.metric,
        metric: r.metric,
        state: "measured",
        value: String(r.value),
        interval_text: null,
        n: r.n,
        evidence_class: r.evidence_class,
        commit: r.commit,
        mode: r.mode,
        seed: typeof r.seed === "number" ? r.seed : null,
        note: "Mock sample data",
      })),
      live: [],
      other: [],
    };
  },

  async getEvaluation(): Promise<Evaluation> {
    await wait(300);
    return MOCK_EVALUATION;
  },
};
