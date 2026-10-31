"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, describeError, isUnreachable } from "@/lib/api";
import type {
  Cause,
  Run,
  RunMode,
  RunOverrides,
  ScenarioSummary,
  SignoffResult,
  VerifyResult,
} from "@/lib/api-types";

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

export type BreakKind = "runway" | "gate" | "unsafe" | "stale" | "tamper";

export interface BreakOutcome {
  kind: BreakKind;
  tone: "info" | "ok" | "bad";
  title: string;
  detail?: string;
}

export const DECIDED_BY = "Duty manager";

export function useDashboard() {
  const [cause, setCause] = useState<Cause | "all">("all");
  const [query, setQuery] = useState("");
  const [scenarios, setScenarios] = useState<Load<ScenarioSummary[]>>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setModeState] = useState<RunMode>("recorded");
  const [overrides, setOverrides] = useState<RunOverrides>({});
  const [runState, setRunState] = useState<RunState>({ status: "idle" });
  const [signoff, setSignoff] = useState<SignoffState>({ status: "idle" });
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
      setTamper(null);
      try {
        const run = await api.createRun({ scenario_id: scenarioId, mode: runMode, overrides: ov });
        if (seq !== runSeq.current) return null;
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
        .listScenarios(c === "all" ? { limit: 50 } : { cause: c, limit: 50 })
        .then((data) => {
          setScenarios({ status: "ready", data });
          if (selectedRef.current === null && data.length > 0) {
            selectedRef.current = data[0].scenario_id;
            setSelectedId(data[0].scenario_id);
            void startRun(data[0].scenario_id, "recorded", {});
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
      void startRun(scenarioId, mode, {});
    },
    [mode, startRun],
  );

  const setMode = useCallback(
    (m: RunMode) => {
      setModeState(m);
      setOutcome(null);
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
        setOutcome(
          first
            ? {
                kind,
                tone: "ok",
                title: "Caught before it could be chosen",
                detail: `${first.violations.map((v) => v.rule_id).join(", ")} removed it. Open Negotiation to see why.`,
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
        tone: run.path === "no_deal" ? "bad" : "info",
        title,
        detail:
          run.decision.kind === "NO_DEAL"
            ? run.decision.reason_type === "NOTHING_LEGAL"
              ? "No agreement: nothing is legal. See the plan view."
              : "No agreement: system fault. See the plan view."
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
          : `${result.reason ?? "The log no longer checks out."}${
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
    async (decisions: string[], requests: string[]) => {
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
        });
        setSignoff({ status: "done", result });
      } catch (err) {
        setSignoff({ status: "error", message: describeError(err) });
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
    mode,
    setMode,
    overrides,
    runState,
    rerun,
    reset,
    signoff,
    approve,
    resetSignoff,
    outcome,
    busy,
    tamper,
    closeRunway,
    blockGate,
    injectUnsafe,
    changeAfterViewing,
    tamperLog,
  };
}
