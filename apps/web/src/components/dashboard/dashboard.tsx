"use client";

import { useState } from "react";
import { useDashboard } from "@/hooks/use-dashboard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CircleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CAUSE_LABEL, FINAL_DECISION_LABEL, isApproved, refusalBanner, signoffStatusLabel } from "@/lib/labels";
import { BreakItDock } from "@/components/dashboard/break-it-dock";
import { EvidenceView } from "@/components/dashboard/evidence-view";
import { FlightList } from "@/components/dashboard/flight-list";
import { LogView } from "@/components/dashboard/log-view";
import { ModeBanner } from "@/components/dashboard/mode-banner";
import { NegotiationView } from "@/components/dashboard/negotiation-view";
import { NoGoView } from "@/components/dashboard/no-go-view";
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

  // A refused sign-off leaves the plan on screen out of date until a new one is made.
  const refused = d.signoff.status === "done" && !isApproved(d.signoff.result.status) ? d.signoff.result : null;
  const banner = refused ? refusalBanner(refused.status) : null;
  const dimmed = banner?.outOfDate === true;

  const pickFlight = (id: string) => {
    setTab("plan");
    d.select(id);
  };

  return (
    <div className="flex min-h-screen flex-col lg:h-screen">
      <ModeBanner mode={d.mode} onModeChange={d.setMode} disabled={running || d.selectedId === null} />

      <div className="grid min-h-0 flex-1 lg:grid-cols-[14rem_minmax(0,1fr)_18rem] lg:grid-rows-[minmax(0,1fr)]">
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

        <main className="min-w-0 space-y-2 p-3 lg:overflow-y-auto" aria-busy={running}>
          <h1 className="flex flex-wrap items-baseline gap-x-2 text-base font-semibold">
            {selected ? `${selected.flight_id}, ${selected.route}` : "Arrival recovery"}
            <span className="text-sm font-normal text-muted-foreground">
              {selected ? `${CAUSE_LABEL[selected.cause]} delay` : "What to do, why, and what could go wrong"}
            </span>
          </h1>

          {d.sameAsRejected && (
            <p role="status" className="rounded-lg border border-warning/50 bg-warning-soft px-3 py-2 text-sm">
              <strong>This is the same plan you rejected.</strong> Nothing about the flight or the airport changed, and
              the system keeps no memory of rejected plans. Change something below, or handle the case yourself.
            </p>
          )}

          {refused && banner && (
            <div
              role="alert"
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-destructive bg-destructive px-3 py-2 text-sm text-background"
            >
              <CircleAlert aria-hidden className="size-4 shrink-0" />
              <span className="flex-1">
                <strong>{banner.lead}</strong>{" "}
                {banner.outOfDate
                  ? `Sign-off refused: ${signoffStatusLabel(refused.status).title.replace(/^Refused: /, "")}`
                  : `${refused.final_decision ? `${FINAL_DECISION_LABEL[refused.final_decision]} ` : ""}${signoffStatusLabel(refused.status).detail}`}
              </span>
              {banner.outOfDate && (
                <Button size="sm" variant="secondary" onClick={d.rerun}>
                  Make a new recovery plan
                </Button>
              )}
            </div>
          )}

          <div className={dimmed ? "opacity-50" : undefined}>{run && !running && <OutcomeStrip run={run} />}</div>

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

            <TabsContent value="plan" className={dimmed ? "pt-2 opacity-50" : "pt-2"}>
              <RunGate d={d} running={running} run={run} empty="Pick a delayed flight">
                {run && run.decision.kind === "DEAL" && run.card && (
                  <PlanCard run={run} card={run.card} deal={run.decision} modelNotes={run.model_notes} />
                )}
                {run && run.decision.kind === "NO_GO" && <NoGoView decision={run.decision} />}
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
          <SignoffPanel
            run={running ? null : run}
            signoff={d.signoff}
            decision={d.decision}
            onApprove={d.approve}
            onReject={d.reject}
            onTakeOver={d.takeOver}
            onNewPlan={d.rerun}
          />
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
  if (d.runState.status === "idle" && d.scenarios.status === "loading")
    return <LoadingBlock label="Loading flights" lines={6} />;
  if (d.runState.status === "idle" && d.scenarios.status === "error")
    return (
      <ErrorPanel
        title="Cannot reach the planning service"
        message={d.scenarios.message}
        unreachable={d.scenarios.unreachable}
        onRetry={d.retryScenarios}
      />
    );
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
