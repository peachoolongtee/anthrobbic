"use client";

import { useState } from "react";
import { useDashboard } from "@/hooks/use-dashboard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CAUSE_LABEL } from "@/lib/labels";
import { BreakItDock } from "@/components/dashboard/break-it-dock";
import { EvidenceView } from "@/components/dashboard/evidence-view";
import { FlightList } from "@/components/dashboard/flight-list";
import { LogView } from "@/components/dashboard/log-view";
import { ModeBanner } from "@/components/dashboard/mode-banner";
import { NegotiationView } from "@/components/dashboard/negotiation-view";
import { NoDealView } from "@/components/dashboard/no-deal-view";
import { OutcomeStrip } from "@/components/dashboard/outcome-strip";
import { PlanCard } from "@/components/dashboard/plan-card";
import { SignoffPanel } from "@/components/dashboard/signoff-panel";
import { EmptyPanel, ErrorPanel, LoadingBlock } from "@/components/dashboard/states";

type Tab = "plan" | "negotiation" | "log" | "evidence";

export function Dashboard() {
  const d = useDashboard();
  const [tab, setTab] = useState<Tab>("plan");

  const run = d.runState.status === "ready" ? d.runState.run : null;
  const running = d.runState.status === "loading";
  const selected =
    d.scenarios.status === "ready" ? d.scenarios.data.find((s) => s.scenario_id === d.selectedId) : undefined;

  const pickFlight = (id: string) => {
    setTab("plan");
    d.select(id);
  };

  return (
    <div className="flex min-h-screen flex-col lg:h-screen">
      <ModeBanner mode={d.mode} onModeChange={d.setMode} disabled={running || d.selectedId === null} />

      <div className="grid min-h-0 flex-1 lg:grid-cols-[17.5rem_minmax(0,1fr)_21rem]">
        <aside className="flex min-h-0 flex-col border-b p-3 max-lg:max-h-[28rem] lg:border-r lg:border-b-0">
          <FlightList
            scenarios={d.scenarios}
            cause={d.cause}
            onCauseChange={d.changeCause}
            query={d.query}
            onQueryChange={d.setQuery}
            selectedId={d.selectedId}
            onSelect={pickFlight}
            onRetry={d.retryScenarios}
          />
        </aside>

        <main className="min-w-0 space-y-4 p-4 lg:overflow-y-auto" aria-busy={running}>
          <div>
            <h1 className="text-lg font-semibold">
              {selected ? `${selected.flight_id}, ${selected.route}` : "Arrival recovery"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {selected
                ? `${CAUSE_LABEL[selected.cause]} delay. What to do, why, and what could go wrong.`
                : "What to do, why, and what could go wrong."}
            </p>
          </div>

          {run && !running && <OutcomeStrip run={run} />}

          <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
            <TabsList variant="line" aria-label="Views" className="w-full justify-start border-b">
              <TabsTrigger value="plan" className="flex-none px-3">
                Recovery plan
              </TabsTrigger>
              <TabsTrigger value="negotiation" className="flex-none px-3">
                Negotiation
              </TabsTrigger>
              <TabsTrigger value="log" className="flex-none px-3">
                Log
              </TabsTrigger>
              <TabsTrigger value="evidence" className="flex-none px-3">
                Evidence
              </TabsTrigger>
            </TabsList>

            <TabsContent value="plan" className="pt-3">
              <RunGate d={d} running={running} run={run} empty="Pick a delayed flight">
                {run && run.decision.kind === "DEAL" && run.card && (
                  <PlanCard card={run.card} deal={run.decision} modelNotes={run.model_notes} />
                )}
                {run && run.decision.kind === "NO_DEAL" && <NoDealView decision={run.decision} />}
              </RunGate>
            </TabsContent>

            <TabsContent value="negotiation" className="pt-3">
              <RunGate d={d} running={running} run={run} empty="Pick a delayed flight">
                {run && <NegotiationView run={run} />}
              </RunGate>
            </TabsContent>

            <TabsContent value="log" className="pt-3">
              <RunGate d={d} running={running} run={run} empty="Pick a delayed flight">
                {run && (
                  <LogView
                    key={`${run.run_id}:${run.log_head}`}
                    runId={run.run_id}
                    logHead={run.log_head}
                    tamper={d.tamper}
                  />
                )}
              </RunGate>
            </TabsContent>

            <TabsContent value="evidence" className="pt-3">
              <EvidenceView />
            </TabsContent>
          </Tabs>
        </main>

        <aside className="border-t p-3 lg:overflow-y-auto lg:border-t-0 lg:border-l">
          <SignoffPanel run={running ? null : run} signoff={d.signoff} onApprove={d.approve} onNewPlan={d.rerun} />
        </aside>
      </div>

      <BreakItDock
        run={run}
        overrides={d.overrides}
        busy={d.busy}
        disabled={running}
        outcome={d.outcome}
        onRunway={(id) => {
          setTab("plan");
          d.closeRunway(id);
        }}
        onGate={(id) => {
          setTab("plan");
          d.blockGate(id);
        }}
        onUnsafe={(rule) => {
          setTab("negotiation");
          d.injectUnsafe(rule);
        }}
        onStale={d.changeAfterViewing}
        onTamper={() => {
          setTab("log");
          d.tamperLog();
        }}
        onReset={d.reset}
      />
    </div>
  );
}

/** Shared loading, error and empty handling for the views that need a run. */
function RunGate({
  d,
  running,
  run,
  empty,
  children,
}: {
  d: ReturnType<typeof useDashboard>;
  running: boolean;
  run: unknown;
  empty: string;
  children: React.ReactNode;
}) {
  if (running) return <LoadingBlock label="Running the negotiation" lines={6} />;
  if (d.runState.status === "error")
    return (
      <ErrorPanel
        title="Could not make a recovery plan"
        message={d.runState.message}
        unreachable={d.runState.unreachable}
        onRetry={d.rerun}
      />
    );
  if (!run)
    return (
      <EmptyPanel title={empty}>
        {d.scenarios.status === "ready" && d.scenarios.data.length === 0
          ? "There are no delayed flights to recover."
          : "Choose a flight on the left. Its recovery plan appears here."}
      </EmptyPanel>
    );
  return <>{children}</>;
}
