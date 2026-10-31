"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  Box,
  CircleAlert,
  FileText,
  FlaskConical,
  Map as MapIcon,
  MessagesSquare,
  ScrollText,
  X,
  type LucideIcon,
} from "lucide-react";
import { useDashboard } from "@/hooks/use-dashboard";
import { Button } from "@/components/ui/button";
import { isApproved, signoffStatusLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { AgentStrip } from "@/components/dashboard/agent-strip";
import { AirportMap } from "@/components/dashboard/airport-map";
import { BreakItDock } from "@/components/dashboard/break-it-dock";
import { EvidenceView } from "@/components/dashboard/evidence-view";
import { FlightList } from "@/components/dashboard/flight-list";
import { FlightMap } from "@/components/dashboard/flight-map";
import { LogView } from "@/components/dashboard/log-view";
import { ModeBanner } from "@/components/dashboard/mode-banner";
import { NegotiationView } from "@/components/dashboard/negotiation-view";
import { NoDealView } from "@/components/dashboard/no-deal-view";
import { PlanCard } from "@/components/dashboard/plan-card";
import { PlanSummary } from "@/components/dashboard/plan-summary";
import { SignoffPanel } from "@/components/dashboard/signoff-panel";
import { EmptyPanel, ErrorPanel, LoadingBlock } from "@/components/dashboard/states";

type Tab = "details" | "negotiation" | "log" | "evidence";

const TABS: { id: Tab; label: string; Icon: LucideIcon }[] = [
  { id: "details", label: "Plan", Icon: FileText },
  { id: "negotiation", label: "Negotiation", Icon: MessagesSquare },
  { id: "log", label: "Log", Icon: ScrollText },
  { id: "evidence", label: "Evidence", Icon: FlaskConical },
];

const NO_FLIGHTS: never[] = [];

// The 3D airport loads only when chosen, so three.js stays off the first load.
const AirportScene = dynamic(() => import("@/components/dashboard/airport-scene"), {
  ssr: false,
  loading: () => <div className="size-full bg-background" />,
});

type View = "map" | "airport";
/** Floating panel surface used over the map on large screens. */
// Frosted glass: a strong blur, a slight saturation lift and a thin top
// highlight. Opaque enough that text keeps its contrast over the map.
const PANEL =
  "rounded-2xl border border-white/10 bg-card/70 shadow-xl shadow-black/40 backdrop-blur-xl backdrop-saturate-150 [box-shadow:inset_0_1px_0_0_rgb(255_255_255/0.06),0_20px_40px_-12px_rgb(0_0_0/0.5)]";

export function Dashboard() {
  const d = useDashboard();
  const [tab, setTab] = useState<Tab | null>(null);
  const [view, setView] = useState<View>("map");
  // The clear area between the panels, where the map frames the route.
  const clearArea = useRef<HTMLDivElement>(null);

  const run = d.runState.status === "ready" ? d.runState.run : null;
  const running = d.runState.status === "loading";
  const selected =
    d.scenarios.status === "ready" ? d.scenarios.data.find((s) => s.scenario_id === d.selectedId) : undefined;

  // A refused sign-off leaves the plan on screen out of date until a new one is made.
  const refused = d.signoff.status === "done" && !isApproved(d.signoff.result.status) ? d.signoff.result : null;

  const pickFlight = (id: string) => {
    setTab(null);
    d.select(id);
  };
  const toggleTab = (t: Tab) => setTab((cur) => (cur === t ? null : t));

  return (
    <div className="flex min-h-screen flex-col lg:h-screen">
      <ModeBanner mode={d.mode} onModeChange={d.setMode} disabled={running || d.selectedId === null} />

      <div className="relative flex flex-1 flex-col gap-3 p-3 lg:block lg:min-h-0 lg:overflow-hidden lg:p-0">
        {/* Backdrop: the flight map or the 3D airport. Full-bleed on large
            screens, a box above the panels on small ones. */}
        {view === "map" ? (
          <FlightMap
            flights={d.scenarios.status === "ready" ? d.scenarios.data : NO_FLIGHTS}
            selected={selected}
            frame={clearArea}
            className="relative h-72 rounded-2xl border border-border lg:absolute lg:inset-0 lg:h-auto lg:rounded-none lg:border-0"
          />
        ) : (
          <div className="relative h-96 overflow-hidden rounded-2xl border border-border lg:absolute lg:inset-0 lg:h-auto lg:rounded-none lg:border-0">
            <AirportScene
              run={running ? null : run}
              flightId={selected?.flight_id ?? null}
              overrides={d.overrides}
              disabled={running || d.busy !== null || run === null}
              onRunway={(id) => {
                setTab(null);
                d.closeRunway(id);
              }}
              onGate={(id) => {
                setTab(null);
                d.blockGate(id);
              }}
            />
          </div>
        )}

        {/* Flights */}
        <aside
          className={cn(
            PANEL,
            "relative flex max-h-[26rem] flex-col p-3 lg:absolute lg:top-3 lg:bottom-3 lg:left-3 lg:z-10 lg:max-h-none lg:w-[19rem]",
          )}
        >
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

        {/* Map stage, between the two panels */}
        <main
          aria-busy={running}
          className="relative flex flex-col gap-3 lg:pointer-events-none lg:absolute lg:inset-y-0 lg:right-[24.5rem] lg:left-[20.5rem] lg:gap-0 [&>*]:pointer-events-auto"
        >
          {/* Not drawn: marks the space below the agent strip and above the
              runway inset, for framing the route. Hidden on small screens. */}
          <div ref={clearArea} aria-hidden className="pointer-events-none! absolute inset-x-0 top-14 bottom-[19rem] max-lg:hidden" />
          <div className="flex justify-center lg:absolute lg:top-3 lg:left-1/2 lg:-translate-x-1/2">
            <AgentStrip run={running ? null : run} />
          </div>

          {/* Map or 3D airport */}
          <div
            role="group"
            aria-label="Backdrop"
            className="flex w-fit items-center gap-0.5 rounded-xl border border-border bg-card/85 p-1 backdrop-blur lg:absolute lg:top-16 lg:left-0"
          >
            {(
              [
                { id: "map", label: "Map", Icon: MapIcon },
                { id: "airport", label: "Airport 3D", Icon: Box },
              ] as const
            ).map(({ id, label, Icon }) => (
              <button
                key={id}
                type="button"
                aria-pressed={view === id}
                onClick={() => setView(id)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                  view === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Icon aria-hidden className="size-4" />
                {label}
              </button>
            ))}
          </div>

          {/* Runways and gates: select one to close it. The 3D view has its own. */}
          {view === "map" && (
          <section
            aria-label="Runways and gates"
            className={cn(
              PANEL,
              "p-2 lg:absolute lg:right-0 lg:bottom-[7.75rem] lg:w-[21rem]",
              running && "opacity-60",
            )}
          >
            <AirportMap
              run={run}
              overrides={d.overrides}
              disabled={running || d.busy !== null || run === null}
              onRunway={(id) => {
                setTab(null);
                d.closeRunway(id);
              }}
              onGate={(id) => {
                setTab(null);
                d.blockGate(id);
              }}
            />
          </section>
          )}

          {/* Drawer with the detail views */}
          {tab && (
            <section
              aria-label={TABS.find((t) => t.id === tab)?.label}
              className={cn(
                PANEL,
                "relative z-10 flex flex-col bg-card/95 animate-in fade-in slide-in-from-bottom-4 duration-200 lg:absolute lg:inset-x-0 lg:top-3 lg:bottom-[7.25rem]",
              )}
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2">
                <h2 className="font-display text-base font-semibold">{TABS.find((t) => t.id === tab)?.label}</h2>
                <Button size="icon-sm" variant="ghost" aria-label="Close" onClick={() => setTab(null)}>
                  <X aria-hidden />
                </Button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {tab === "details" && (
                  <RunGate d={d} running={running} run={run}>
                    {run && run.decision.kind === "DEAL" && run.card && (
                      <PlanCard card={run.card} deal={run.decision} modelNotes={run.model_notes} />
                    )}
                    {run && run.decision.kind === "NO_DEAL" && <NoDealView decision={run.decision} />}
                  </RunGate>
                )}
                {tab === "negotiation" && (
                  <RunGate d={d} running={running} run={run}>
                    {run && <NegotiationView run={run} />}
                  </RunGate>
                )}
                {tab === "log" && (
                  <RunGate d={d} running={running} run={run}>
                    {run && (
                      <LogView key={`${run.run_id}:${run.log_head}`} runId={run.run_id} logHead={run.log_head} tamper={d.tamper} />
                    )}
                  </RunGate>
                )}
                {tab === "evidence" && <EvidenceView />}
              </div>
            </section>
          )}

          <div className="z-10 flex flex-col items-center gap-2 lg:absolute lg:inset-x-0 lg:bottom-3">
            <BreakItDock
                run={run}
                overrides={d.overrides}
                busy={d.busy}
                disabled={running}
                outcome={d.outcome}
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
            <nav
              aria-label="Views"
              className="flex items-center gap-0.5 rounded-xl border border-border bg-card/85 p-1 backdrop-blur"
            >
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  aria-pressed={tab === t.id}
                  title={t.label}
                  onClick={() => toggleTab(t.id)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                    tab === t.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  <t.Icon aria-hidden className="size-4" />
                  <span className="max-xl:sr-only">{t.label}</span>
                </button>
              ))}
            </nav>
          </div>
        </main>

        {/* Plan and sign-off */}
        <aside
          className={cn(
            PANEL,
            "relative space-y-4 p-4 lg:absolute lg:top-3 lg:right-3 lg:bottom-3 lg:z-10 lg:w-[23rem] lg:overflow-y-auto",
          )}
        >
          {refused && (
            <div role="alert" className="space-y-2 rounded-xl border border-destructive/60 bg-destructive-soft p-3 text-sm">
              <p className="flex items-start gap-2">
                <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-destructive" />
                <span>
                  <strong>Out of date.</strong>{" "}
                  {signoffStatusLabel(refused.status).title.replace(/^Refused: /, "")}
                </span>
              </p>
              <Button size="sm" variant="secondary" onClick={d.rerun}>
                Make a new recovery plan
              </Button>
            </div>
          )}

          <div className={refused ? "opacity-50" : undefined}>
            <PlanSummary flight={selected} run={running ? null : run} onDetails={() => setTab("details")} />
          </div>

          <RunGate d={d} running={running} run={run} compact>
            <SignoffPanel run={running ? null : run} signoff={d.signoff} onApprove={d.approve} onNewPlan={d.rerun} />
          </RunGate>
        </aside>
      </div>
    </div>
  );
}

/** Shared loading, error and empty handling for the views that need a run. */
function RunGate({
  d,
  running,
  run,
  compact = false,
  children,
}: {
  d: ReturnType<typeof useDashboard>;
  running: boolean;
  run: unknown;
  compact?: boolean;
  children: React.ReactNode;
}) {
  if (running) return <LoadingBlock label="Agents negotiating" lines={compact ? 3 : 6} />;
  if (d.runState.status === "idle" && d.scenarios.status === "loading")
    return <LoadingBlock label="Loading flights" lines={compact ? 3 : 6} />;
  if (d.runState.status === "idle" && d.scenarios.status === "error")
    return (
      <ErrorPanel
        title="Cannot reach the planning service"
        message={d.scenarios.message}
        unreachable={d.scenarios.unreachable}
        compact={compact}
        onRetry={d.retryScenarios}
      />
    );
  if (d.runState.status === "error")
    return (
      <ErrorPanel
        title="Could not make a recovery plan"
        message={d.runState.message}
        unreachable={d.runState.unreachable}
        compact={compact}
        onRetry={d.rerun}
      />
    );
  if (!run)
    return (
      <EmptyPanel title="Pick a flight">
        {d.scenarios.status === "ready" && d.scenarios.data.length === 0 ? "No delayed flights to recover." : null}
      </EmptyPanel>
    );
  return <>{children}</>;
}
