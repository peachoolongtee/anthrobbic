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
  Domain,
  Evaluation,
  Fact,
  Fault,
  LogEntry,
  NoDeal,
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
import { MOCK_EVALUATION, MOCK_SCENARIOS, type MockScenario } from "@/lib/mock/fixtures";

const RUNWAYS = ["27L", "27R"];
const GATES = ["B12", "B14", "C3"];
const DOMAINS: Domain[] = ["atc", "pilot", "ground"];

interface StoredRun {
  scenario: MockScenario;
  mode: RunMode;
  closedRunways: string[];
  closedGates: string[];
  run: Run;
  version: number;
  extraLog: LogEntry[];
}

const store = new Map<string, StoredRun>();
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

const SRC_WAKE = "FAA JO 7110.65 para 5-5-4 (legacy classes)";
const SRC_FUEL = "Airline policy, shaped on 14 CFR 121.639";
const SRC_ASSUMED = "Assumption: demo default, not from a regulation";

function passingRules(offset: number): RuleResult[] {
  return [
    rule("ATC-WAKE-SEP", "atc", "Spacing behind the aircraft ahead", "confirmed", 6, 5, "NM", "at_least", SRC_WAKE, "Spacing is enough."),
    rule("ATC-RWY-THROUGHPUT", "atc", "Arrivals per hour on the runway", "assumption", 26 + offset, 30, "arrivals/h", "at_most", SRC_ASSUMED, "Runway is not over its rate."),
    rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "policy", 57 - offset * 3, 45, "min", "at_least", SRC_FUEL, "Reserve is kept."),
    rule("GND-GATE-OVERLAP", "ground", "Gap before the next aircraft at the gate", "assumption", 25, 20, "min", "at_least", SRC_ASSUMED, "Gate is free."),
    rule("GND-TURNAROUND", "ground", "Time to turn the aircraft round", "assumption", 48, 45, "min", "at_least", SRC_ASSUMED, "Turnaround fits."),
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
    rule: rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "policy", 31, 45, "min", "at_least", SRC_FUEL, "Lands with less fuel than the policy keeps in reserve."),
  },
  "ATC-RWY-CLOSED": {
    label: "Use a closed runway",
    rule: rule("ATC-RWY-CLOSED", "atc", "Runway is open", "assumption", 1, 0, "closed runways used", "at_most", "Scenario state", "The plan uses a runway that is closed."),
  },
  "ATC-WAKE-SEP": {
    label: "Land 3 NM behind a heavy aircraft",
    rule: rule("ATC-WAKE-SEP", "atc", "Spacing behind the aircraft ahead", "confirmed", 3, 5, "NM", "at_least", SRC_WAKE, "Spacing is less than the minimum."),
  },
  "GND-GATE-OVERLAP": {
    label: "Park at an occupied gate",
    rule: rule("GND-GATE-OVERLAP", "ground", "Gap before the next aircraft at the gate", "assumption", -10, 20, "min", "at_least", SRC_ASSUMED, "Another aircraft is still at the gate."),
  },
};

function build(
  runId: string,
  sc: MockScenario,
  mode: RunMode,
  closedRunways: string[],
  closedGates: string[],
  inject: string | undefined,
  version: number,
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
        rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "policy", 41, 45, "min", "at_least", SRC_FUEL, "Lands with less fuel than the policy keeps in reserve."),
      ],
    });
    removed.push({
      package_id: pid("wake"),
      label: `Runway 27R, ${clock(base + 2)}, gate B14, vector`,
      removed_in_turn: 1,
      violations: [
        rule("ATC-WAKE-SEP", "atc", "Spacing behind the aircraft ahead", "confirmed", 4, 5, "NM", "at_least", SRC_WAKE, "Spacing is less than the minimum."),
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
  let noDeal: NoDeal | null = null;

  if (sc.systemFault) {
    faults.push({
      kind: "missing_data",
      message: "Fuel on board is unknown for this flight, so the fuel rule cannot be checked.",
    });
    noDeal = {
      kind: "NO_DEAL",
      reason_type: "SYSTEM_FAULT",
      binding_rules: [
        rule("PLT-FUEL-POLICY", "pilot", "Fuel left at landing", "policy", null, 45, "min", "at_least", SRC_FUEL, "Fuel on board is unknown, so the rule fails closed.", "missing_data"),
      ],
      packages_considered: 24,
      nearest_package: null,
      nearest_violations: [],
      what_would_change: ["Supply fuel on board for this flight, then run it again."],
      reason: "The data needed to check the plans is missing. No plan was judged illegal.",
    };
  } else if (openRunways.length === 0) {
    noDeal = {
      kind: "NO_DEAL",
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
    noDeal = {
      kind: "NO_DEAL",
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
  const timedOut = !modelOff && sc.fallbackFault && !noDeal;
  let path: Run["path"] = "consensus";
  if (noDeal) path = "no_deal";
  else if (modelOff || timedOut) path = "fallback";

  if (!noDeal && modelOff) {
    faults.push({
      kind: "model_off",
      message: "The model is switched off, so the agents did not negotiate. The rule-based fallback chose the plan.",
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
  if (noDeal && sc.systemFault) turns.length = 0;

  const rwy = openRunways[0] ?? "27L";
  const gate = openGates.includes("B12") ? "B12" : (openGates[0] ?? "B12");
  const arrive = base + (rwy === "27R" ? 6 : 0) + (gate === "B12" ? 0 : 2);
  const label = `Runway ${rwy}, ${clock(arrive)}, gate ${gate}, hold`;

  let decision: Run["decision"];
  let card: Card | null = null;
  if (noDeal) {
    decision = noDeal;
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
    card = {
      card_hash: hash(`card:${label}:${closedRunways.join()}:${closedGates.join()}:${version}:${mode}`),
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
        { text: "Fuel left at landing is the tightest margin. A longer hold would break the fuel policy.", rule_id: "PLT-FUEL-POLICY" },
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

  const head = hash(`${runId}:${version}:${path}`);
  return {
    run_id: runId,
    scenario_id: sc.summary.scenario_id,
    state_version: version,
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

function logFor(s: StoredRun): LogEntry[] {
  const r = s.run;
  const entries: [string, string][] = [
    ["scenario", `Loaded ${s.scenario.summary.flight_id} with provenance labels`],
    ["options", `${r.decision.kind === "DEAL" ? r.decision.packages_considered : 24} candidate plans listed`],
    ["rules", `${r.removed_packages.length} plans removed by the rules`],
    ...r.turns.flatMap((t): [string, string][] =>
      t.responses.map((x) => ["response", `Turn ${t.turn}: ${x.domain} accepted ${x.acceptable_count} plans`]),
    ),
    ["decision", r.path === "no_deal" ? "No agreement, handed to the duty manager" : `Chose by ${r.path}`],
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

  async createRun(body: {
    scenario_id: string;
    mode: RunMode;
    overrides?: RunOverrides;
  }): Promise<Run> {
    await wait(body.mode === "live" ? 900 : 450);
    const sc = MOCK_SCENARIOS.find((s) => s.summary.scenario_id === body.scenario_id);
    if (!sc) throw new Error(`Unknown scenario ${body.scenario_id}`);
    const closedRunways = body.overrides?.closed_runways ?? [];
    const closedGates = body.overrides?.closed_gates ?? [];
    const runId = `mock-run-${++counter}`;
    const run = build(runId, sc, body.mode, closedRunways, closedGates, body.overrides?.inject_unsafe, 1);
    store.set(runId, { scenario: sc, mode: body.mode, closedRunways, closedGates, run, version: 1, extraLog: [] });
    return run;
  },

  async changeState(runId: string, change: StateChange): Promise<{ state_version: number }> {
    await wait(200);
    const s = need(runId);
    s.closedRunways = Array.from(new Set([...s.closedRunways, ...(change.closed_runways ?? [])]));
    s.closedGates = Array.from(new Set([...s.closedGates, ...(change.closed_gates ?? [])]));
    s.version += 1;
    return { state_version: s.version };
  },

  async signoff(runId: string, body: SignoffRequest): Promise<SignoffResult> {
    await wait(350);
    const s = need(runId);
    const deal = s.run.decision;
    if (deal.kind !== "DEAL") throw new Error("There is no plan to sign off");
    const changed: string[] = [];
    const violations: RuleResult[] = [];
    if (body.state_version_seen !== s.version) {
      for (const g of s.closedGates) {
        if (deal.package.gate_id === g) {
          changed.push(`Gate ${g} is now blocked`);
          violations.push(UNSAFE["GND-GATE-OVERLAP"].rule);
        }
      }
      for (const r of s.closedRunways) {
        if (deal.package.runway_id === r) {
          changed.push(`Runway ${r} is now closed`);
          violations.push(UNSAFE["ATC-RWY-CLOSED"].rule);
        }
      }
      if (changed.length === 0) changed.push("Airport state changed after the plan was shown");
      return {
        status: "REFUSED_STATE_CHANGED",
        changed_fields: changed,
        violations,
        requests: [],
        airline_decisions: [],
        log_head: s.run.log_head,
      };
    }
    if (s.run.card && body.card_hash_seen !== s.run.card.card_hash) {
      return {
        status: "REFUSED_CARD_CHANGED",
        changed_fields: ["The card on screen is not the card the server holds"],
        violations: [],
        requests: [],
        airline_decisions: [],
        log_head: s.run.log_head,
      };
    }
    const card = s.run.card!;
    s.extraLog.push({
      seq: 0,
      kind: "signoff",
      summary: `Approved by ${body.decided_by}. Requests issued, nothing executed.`,
      hash: hash(`${runId}:signoff:${body.decided_by}`),
    });
    const head = hash(`${runId}:head:signed`);
    s.run = { ...s.run, log_head: head };
    return {
      status: "APPROVED",
      changed_fields: [],
      violations: [],
      requests: card.requests.filter((r) => body.requests_to_send.includes(r.key)),
      airline_decisions: card.airline_decisions.filter((d) => body.airline_decisions_approved.includes(d.key)),
      log_head: head,
    };
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

  async getEvaluation(): Promise<Evaluation> {
    await wait(300);
    return MOCK_EVALUATION;
  },
};
