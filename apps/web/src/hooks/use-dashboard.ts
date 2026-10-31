"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, describeError, isUnreachable } from "@/lib/api";
import type {
  Cause,
  DecisionResult,
  LookupQuery,
  Run,
  RunMode,
  RunOverrides,
  ScenarioSummary,
  SignoffResult,
  VerifyResult,
} from "@/lib/api-types";
import { verifyReasonLabel } from "@/lib/labels";

type Load<T> =
  | { status: "loading" }
  | { status: "error"; message: string; unreachable: boolean }
  | { status: "ready"; data: T };

type RunState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string; unreachable: boolean }
  | { status: "ready"; run: Run; mode: RunMode };

export type SignoffState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; result: SignoffResult };

/** Reject or take-over, which issue nothing and need no ticked boxes. */
export type DecisionState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; result: DecisionResult };

export type LookupState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "none"; message: string }
  | { status: "several"; matches: ScenarioSummary[]; total: number }
  | { status: "found"; flightId: string };

export type BreakKind = "runway" | "gate" | "unsafe" | "stale" | "tamper";

export interface BreakOutcome {
  kind: BreakKind;
  tone: "info" | "ok" | "bad";
  title: string;
  detail?: string;
}

export const DECIDED_BY = "Duty manager (demo, not authenticated)";

/** The API's maximum for one list. */
const LIST_LIMIT = 200;

export function useDashboard() {
  const [cause, setCause] = useState<Cause | "all">("all");
  const [query, setQuery] = useState("");
  const [scenarios, setScenarios] = useState<Load<ScenarioSummary[]>>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setModeState] = useState<RunMode>("recorded");
  const [overrides, setOverrides] = useState<RunOverrides>({});
  const [runState, setRunState] = useState<RunState>({ status: "idle" });
  const [signoff, setSignoff] = useState<SignoffState>({ status: "idle" });
  const [decision, setDecision] = useState<DecisionState>({ status: "idle" });
  const [sameAsRejected, setSameAsRejected] = useState(false);
  // Flights found by the lookup stay at the top of the list for this session.
  const [found, setFound] = useState<ScenarioSummary[]>([]);
  const [lookup, setLookup] = useState<LookupState>({ status: "idle" });
  const [rulesOnlyFlight, setRulesOnlyFlight] = useState<string | null>(null);
  const lookupSeq = useRef(0);
  // For this page only: to say so if a new plan is the one just rejected. It does
  // not change what the backend plans.
  const rejected = useRef<{ scenarioId: string; terms: string } | null>(null);
  const [outcome, setOutcome] = useState<BreakOutcome | null>(null);
  const [tamper, setTamper] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState<BreakKind | null>(null);
  const runSeq = useRef(0);
  const selectedRef = useRef<string | null>(null);

  const startRun = useCallback(
    async (scenarioId: string, runMode: RunMode, ov: RunOverrides): Promise<Run | null> => {
      const seq = ++runSeq.current;
      setRunState({ status: "loading" });
      setSignoff({ status: "idle" });
      setDecision({ status: "idle" });
      setTamper(null);
      try {
        const run = await api.createRun({ scenario_id: scenarioId, mode: runMode, overrides: ov });
        if (seq !== runSeq.current) return null;
        setSameAsRejected(
          run.decision.kind === "DEAL" &&
            rejected.current?.scenarioId === scenarioId &&
            rejected.current.terms === run.decision.terms_hash,
        );
        setRunState({ status: "ready", run, mode: runMode });
        return run;
      } catch (err) {
        if (seq !== runSeq.current) return null;
        setRunState({ status: "error", message: describeError(err), unreachable: isUnreachable(err) });
        return null;
      }
    },
    [],
  );

  const fetchScenarios = useCallback(
    (c: Cause | "all") => {
      api
        .listScenarios(c === "all" ? { limit: LIST_LIMIT } : { cause: c, limit: LIST_LIMIT })
        .then((data) => {
          setScenarios({ status: "ready", data });
          if (selectedRef.current === null && data.length > 0) {
            // A flight picked on the home page arrives as ?flight=<scenario_id>.
            const linked = new URLSearchParams(window.location.search).get("flight");
            const flight = data.find((row) => row.scenario_id === linked) ?? data[0];
            selectedRef.current = flight.scenario_id;
            setSelectedId(flight.scenario_id);
            // Open on replay only when this row has saved answers to replay.
            const first: RunMode = flight.has_recording === false ? "off" : "recorded";
            setModeState(first);
            void startRun(flight.scenario_id, first, {});
          }
        })
        .catch((err: unknown) => {
          setScenarios({ status: "error", message: describeError(err), unreachable: isUnreachable(err) });
        });
    },
    [startRun],
  );

  useEffect(() => {
    fetchScenarios("all");
  }, [fetchScenarios]);

  const retryScenarios = useCallback(() => {
    setScenarios({ status: "loading" });
    fetchScenarios(cause);
  }, [cause, fetchScenarios]);

  const changeCause = useCallback(
    (c: Cause | "all") => {
      setCause(c);
      setScenarios({ status: "loading" });
      fetchScenarios(c);
    },
    [fetchScenarios],
  );

  const select = useCallback(
    (scenarioId: string) => {
      selectedRef.current = scenarioId;
      setSelectedId(scenarioId);
      setOverrides({});
      setOutcome(null);
      setRulesOnlyFlight(null);
      void startRun(scenarioId, mode, {});
    },
    [mode, startRun],
  );

  /** Select and run a looked-up flight. Replay only runs what was saved, and this
   *  never moves to Live on its own. */
  const openFound = useCallback(
    (flight: ScenarioSummary) => {
      const rulesOnly = mode === "recorded" && flight.has_recording === false;
      const runMode: RunMode = rulesOnly ? "off" : mode;
      setFound((rows) => [flight, ...rows.filter((r) => r.scenario_id !== flight.scenario_id)]);
      selectedRef.current = flight.scenario_id;
      setSelectedId(flight.scenario_id);
      setOverrides({});
      setOutcome(null);
      setModeState(runMode);
      setRulesOnlyFlight(rulesOnly ? flight.flight_id : null);
      setLookup({ status: "found", flightId: flight.flight_id });
      void startRun(flight.scenario_id, runMode, {});
    },
    [mode, startRun],
  );

  const findFlight = useCallback(
    async (query: LookupQuery) => {
      const seq = ++lookupSeq.current;
      setLookup({ status: "loading" });
      try {
        const result = await api.lookupFlight(query);
        if (seq !== lookupSeq.current) return;
        if (result.status === "one") openFound(result.matches[0]);
        else if (result.status === "several") setLookup({ status: "several", matches: result.matches, total: result.total });
        else setLookup({ status: "none", message: result.message ?? "No eligible flight matches that search." });
      } catch (err) {
        if (seq !== lookupSeq.current) return;
        setLookup({ status: "error", message: describeError(err) });
      }
    },
    [openFound],
  );

  const setMode = useCallback(
    (m: RunMode) => {
      setModeState(m);
      setOutcome(null);
      setRulesOnlyFlight(null);
      if (selectedRef.current) void startRun(selectedRef.current, m, overrides);
    },
    [overrides, startRun],
  );

  const rerun = useCallback(() => {
    if (selectedRef.current) void startRun(selectedRef.current, mode, overrides);
  }, [mode, overrides, startRun]);

  const reset = useCallback(() => {
    setOverrides({});
    setOutcome(null);
    if (selectedRef.current) void startRun(selectedRef.current, mode, {});
  }, [mode, startRun]);

  /** Re-run with new overrides, then describe what the API returned. */
  const breakWith = useCallback(
    async (kind: BreakKind, next: RunOverrides, title: string) => {
      if (!selectedRef.current) return;
      setBusy(kind);
      setOverrides(next);
      setOutcome(null);
      const run = await startRun(selectedRef.current, mode, next);
      setBusy(null);
      if (!run) {
        setOutcome({ kind, tone: "bad", title: "The run failed", detail: "See the error on the plan." });
        return;
      }
      const injected = run.removed_packages.filter((p) => p.injected);
      if (kind === "unsafe") {
        const first = injected[0];
        const closedFor = run.injection?.closed_for_check;
        setOutcome(
          first
            ? {
                kind,
                tone: "ok",
                title: "Caught before it could be chosen",
                detail: `${[...new Set(first.violations.map((v) => v.rule_id))].join(", ")} removed it. It is listed under Plans the rules removed.${
                  closedFor ? ` No runway was closed, so ${closedFor} was treated as closed for this check only.` : ""
                }`,
              }
            : {
                kind,
                tone: "bad",
                title: "The unsafe plan was not reported as removed",
                detail: "The API did not mark any removed plan as injected.",
              },
        );
        return;
      }
      setOutcome({
        kind,
        tone: run.path === "no_go" ? "bad" : "info",
        title,
        detail:
          run.decision.kind === "NO_GO"
            ? run.decision.reason_type === "NOTHING_LEGAL"
              ? "No-go: nothing is legal. See the plan view."
              : "No-go: system fault. See the plan view."
            : "A new recovery plan was made. Compare it with the one before.",
      });
    },
    [mode, startRun],
  );

  const closeRunway = useCallback(
    (id: string) => {
      const set = new Set(overrides.closed_runways ?? []);
      if (set.has(id)) set.delete(id);
      else set.add(id);
      void breakWith(
        "runway",
        { ...overrides, closed_runways: [...set] },
        set.has(id) ? `Runway ${id} closed` : `Runway ${id} reopened`,
      );
    },
    [overrides, breakWith],
  );

  const blockGate = useCallback(
    (id: string) => {
      const set = new Set(overrides.closed_gates ?? []);
      if (set.has(id)) set.delete(id);
      else set.add(id);
      void breakWith(
        "gate",
        { ...overrides, closed_gates: [...set] },
        set.has(id) ? `Gate ${id} blocked` : `Gate ${id} freed`,
      );
    },
    [overrides, breakWith],
  );

  /** A preset: several existing overrides at once, with a title saying how it is modelled. */
  const disrupt = useCallback(
    (kind: "runway" | "gate", next: RunOverrides, title: string) => {
      void breakWith(kind, next, title);
    },
    [breakWith],
  );

  const injectUnsafe = useCallback(
    (ruleId: string) => {
      void breakWith("unsafe", { ...overrides, inject_unsafe: ruleId }, "Unsafe plan injected");
    },
    [overrides, breakWith],
  );

  /** Change the airport on the server while the old plan stays on screen. */
  const changeAfterViewing = useCallback(async () => {
    if (runState.status !== "ready") return;
    const { run } = runState;
    const gate = run.decision.kind === "DEAL" ? run.decision.package.gate_id : null;
    if (!gate) {
      setOutcome({ kind: "stale", tone: "bad", title: "There is no plan to change under", detail: "Make a recovery plan first." });
      return;
    }
    setBusy("stale");
    try {
      await api.changeState(run.run_id, { closed_gates: [gate] });
      // The next plan must be made for the airport as it is now.
      setOverrides((o) => ({ ...o, closed_gates: [...new Set([...(o.closed_gates ?? []), gate])] }));
      setOutcome({
        kind: "stale",
        tone: "info",
        title: `Gate ${gate} was blocked after you looked`,
        detail: "The plan on screen is now out of date. Try to approve it.",
      });
    } catch (err) {
      setOutcome({ kind: "stale", tone: "bad", title: "Could not change the airport", detail: describeError(err) });
    } finally {
      setBusy(null);
    }
  }, [runState]);

  const tamperLog = useCallback(async () => {
    if (runState.status !== "ready") return;
    setBusy("tamper");
    try {
      const result = await api.verifyLog(runState.run.run_id, { tamper: true });
      setTamper(result);
      setOutcome({
        kind: "tamper",
        tone: result.valid ? "bad" : "ok",
        title: result.valid ? "The tampered log passed. That is a failure." : "Tampering detected",
        detail: result.valid
          ? undefined
          : `${verifyReasonLabel(result.reason) || "The log no longer checks out."}${
              result.first_bad_seq !== null ? ` First bad entry: ${result.first_bad_seq}.` : ""
            }`,
      });
    } catch (err) {
      setOutcome({ kind: "tamper", tone: "bad", title: "Could not check the log", detail: describeError(err) });
    } finally {
      setBusy(null);
    }
  }, [runState]);

  const approve = useCallback(
    async (decisions: boolean, requests: boolean) => {
      if (runState.status !== "ready") return;
      const { run } = runState;
      if (run.decision.kind !== "DEAL" || !run.card) return;
      setSignoff({ status: "loading" });
      try {
        const result = await api.signoff(run.run_id, {
          terms_hash: run.decision.terms_hash,
          state_version_seen: run.state_version,
          card_hash_seen: run.card.card_hash,
          decided_by: DECIDED_BY,
          airline_decisions_approved: decisions,
          requests_to_send: requests,
          field_versions_seen: run.field_versions,
          card_field_hashes_seen: run.card.field_hashes,
        });
        setSignoff({ status: "done", result });
      } catch (err) {
        setSignoff({ status: "error", message: describeError(err) });
      }
    },
    [runState],
  );

  const reject = useCallback(
    async (reason: string) => {
      if (runState.status !== "ready") return;
      setDecision({ status: "loading" });
      try {
        const text = reason.trim();
        const result = await api.reject(runState.run.run_id, {
          decided_by: DECIDED_BY,
          ...(text ? { reason: text } : {}),
        });
        const { run } = runState;
        if (result.status === "REJECTED" && run.decision.kind === "DEAL") {
          rejected.current = { scenarioId: run.scenario_id, terms: run.decision.terms_hash };
        }
        setDecision({ status: "done", result });
      } catch (err) {
        setDecision({ status: "error", message: describeError(err) });
      }
    },
    [runState],
  );

  const takeOver = useCallback(
    async (note: string) => {
      if (runState.status !== "ready") return;
      setDecision({ status: "loading" });
      try {
        const text = note.trim();
        const result = await api.takeOver(runState.run.run_id, {
          decided_by: DECIDED_BY,
          ...(text ? { note: text } : {}),
        });
        setDecision({ status: "done", result });
      } catch (err) {
        setDecision({ status: "error", message: describeError(err) });
      }
    },
    [runState],
  );

  const resetSignoff = useCallback(() => setSignoff({ status: "idle" }), []);

  return {
    cause,
    changeCause,
    query,
    setQuery,
    scenarios,
    retryScenarios,
    selectedId,
    select,
    found,
    lookup,
    findFlight,
    openFound,
    rulesOnlyFlight,
    mode,
    setMode,
    overrides,
    runState,
    rerun,
    reset,
    signoff,
    approve,
    decision,
    sameAsRejected,
    reject,
    takeOver,
    resetSignoff,
    outcome,
    busy,
    tamper,
    closeRunway,
    blockGate,
    disrupt,
    injectUnsafe,
    changeAfterViewing,
    tamperLog,
  };
}
