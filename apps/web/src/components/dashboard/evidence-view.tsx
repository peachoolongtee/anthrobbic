"use client";

import { useEffect, useState, type ReactNode } from "react";
import { FlaskConical } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, describeError, IS_MOCK, isUnreachable } from "@/lib/api";
import type { Evaluation, EvaluationRow, EvidenceClass, Headline, HeadlineItem, WorkbookLimits } from "@/lib/api-types";
import { EVIDENCE_LABEL } from "@/lib/labels";
import { EmptyPanel, ErrorPanel, LoadingBlock } from "@/components/dashboard/states";

type State =
  | { status: "loading" }
  | { status: "error"; message: string; unreachable: boolean }
  | { status: "ready"; data: Evaluation; headline: Headline | null };

function EvidenceBadge({ evidence }: { evidence: string | null }) {
  const ev = evidence ? (EVIDENCE_LABEL[evidence as EvidenceClass] ?? { name: evidence, detail: "" }) : null;
  if (!ev) return null;
  return (
    <Badge variant="secondary" title={ev.detail}>
      {ev.name}
    </Badge>
  );
}

function RunLine({ commit, mode, seed }: { commit: string | null; mode: string | null; seed: number | string | null }) {
  return (
    <span className="block font-mono text-xs text-muted-foreground">
      <span className="inline-block">{commit?.slice(0, 12)}</span>{" "}
      <span className="inline-block">
        {mode}, seed {seed}
      </span>
    </span>
  );
}

const FALLBACK_LIMITS_TITLE = "Where we differ from the challenge workbook";

/** Stated by requirement, whether or not an evaluation has run. */
function WorkbookDifferences() {
  const [limits, setLimits] = useState<WorkbookLimits | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    api
      .getLimits()
      .then((data) => live && setLimits(data))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);
  if (failed)
    return (
      <p className="text-sm text-muted-foreground">
        Could not load where we differ from the challenge workbook. The planning service did not answer.
      </p>
    );
  return (
    <details className="rounded-xl border border-border bg-card p-3">
      <summary className="cursor-pointer">
        <h3 id="differences-heading" className="inline font-display text-sm font-semibold">
          {limits?.title ?? FALLBACK_LIMITS_TITLE}
        </h3>
      </summary>
      {limits ? (
        <ul className="mt-1.5 space-y-1.5 text-sm">
          {limits.items.map((d) => (
            <li key={d.id}>
              <span className="font-medium">{d.limit}:</span> {d.what_we_do}{" "}
              <span className="text-muted-foreground">{d.why}</span>
            </li>
          ))}
        </ul>
      ) : (
        <LoadingBlock label="Loading the limits" lines={3} />
      )}
    </details>
  );
}

/** One card per measure: the run with the most cases, so small samples do not crowd it. */
function largest(items: HeadlineItem[]): HeadlineItem[] {
  const best = new Map<string, HeadlineItem>();
  for (const item of items) {
    const current = best.get(item.key);
    if (!current || (item.n ?? -1) > (current.n ?? -1)) best.set(item.key, item);
  }
  return [...best.values()];
}

function HeadlineRow({ item }: { item: HeadlineItem }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <dt className="min-w-0 text-xs text-muted-foreground">{item.label}</dt>
      {item.state === "absent" ? (
        <dd className="shrink-0 text-xs text-muted-foreground">Not in the results.</dd>
      ) : (
        <dd className="shrink-0 text-right tabular-nums">
          <span className="block font-display text-sm font-semibold">{item.value}</span>
          {item.interval_text && <span className="block text-[11px] text-muted-foreground">Interval {item.interval_text}</span>}
        </dd>
      )}
    </div>
  );
}

/** Items from one run: one evidence class, commit, mode and seed, named once at the top. */
function runsOf(items: HeadlineItem[]): HeadlineItem[][] {
  const runs = new Map<string, HeadlineItem[]>();
  for (const item of items) {
    const id = [item.evidence_class, item.commit, item.mode, item.seed].join("|");
    runs.set(id, [...(runs.get(id) ?? []), item]);
  }
  return [...runs.values()];
}

function HeadlineGroup({ title, detail, items }: { title: string; detail: string; items: HeadlineItem[] }) {
  if (items.length === 0) return null;
  return (
    <section aria-label={title} className="space-y-1.5 rounded-xl border border-border bg-card p-3">
      <div>
        <h3 className="font-display text-sm font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{detail}</p>
      </div>
      {runsOf(items).map((run) => (
        <div key={`${run[0].evidence_class}-${run[0].commit}`}>
          <div className="flex items-center gap-2 border-b border-border pb-1">
            <EvidenceBadge evidence={run[0].evidence_class} />
            <RunLine commit={run[0].commit} mode={run[0].mode} seed={run[0].seed} />
          </div>
          <dl className="divide-y divide-border">
            {run.map((item, i) => (
              <HeadlineRow key={`${item.key}-${i}`} item={item} />
            ))}
          </dl>
        </div>
      ))}
    </section>
  );
}

function EvidenceRow({ row }: { row: EvaluationRow }) {
  return (
    <TableRow className={row.arm === "unguarded_model" ? "bg-muted/50" : undefined}>
      <TableCell className="whitespace-normal [overflow-wrap:anywhere]">
        {row.metric}
        {row.note && <span className="block text-xs text-muted-foreground">{row.note}</span>}
        {row.arm === "unguarded_model" && (
          <Badge variant="outline" className="ml-2 border-destructive/50 text-destructive">
            Never eligible for sign-off
          </Badge>
        )}
      </TableCell>
      <TableCell className="whitespace-normal font-semibold">
        {String(row.value)}
        {(row.interval_text || row.interval) && (
          <span className="block text-xs font-normal text-muted-foreground">
            {row.interval_text ?? (row.interval ? `${row.interval[0]} to ${row.interval[1]}` : "")}
          </span>
        )}
        {IS_MOCK && (
          <Badge variant="outline" className="mt-1 flex border-warning/50 bg-warning-soft text-warning">
            Mock sample data
          </Badge>
        )}
      </TableCell>
      <TableCell className="whitespace-normal">{row.n ?? "none"}</TableCell>
      <TableCell className="whitespace-normal">
        <EvidenceBadge evidence={row.evidence_class} />
        <RunLine commit={row.commit} mode={row.mode} seed={row.seed} />
      </TableCell>
    </TableRow>
  );
}

function ResultsTable({ title, rows }: { title: string; rows: EvaluationRow[] }) {
  if (rows.length === 0) return null;
  return (
    <section aria-label={title} className="space-y-1">
      <h3 className="font-display text-sm font-semibold">{title}</h3>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[37%] whitespace-normal">Measure</TableHead>
            <TableHead className="w-[25%] whitespace-normal">Value</TableHead>
            <TableHead className="w-[12%] whitespace-normal">Cases</TableHead>
            <TableHead className="w-[26%] whitespace-normal">Evidence, run</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <EvidenceRow key={i} row={r} />
          ))}
        </TableBody>
      </Table>
    </section>
  );
}

const WITHOUT_A_MODEL = new Set(["rules_only", "test"]);

export function EvidenceView() {
  return <EvaluationResults differences={<WorkbookDifferences />} />;
}

/** Headline numbers first, so they show as the tab opens. `differences` shows in every state. */
function EvaluationResults({ differences }: { differences: ReactNode }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    Promise.all([api.getEvaluation(), api.getHeadline().catch(() => null)])
      .then(([data, headline]) => live && setState({ status: "ready", data, headline }))
      .catch((err) => live && setState({ status: "error", message: describeError(err), unreachable: isUnreachable(err) }));
    return () => {
      live = false;
    };
  }, [attempt]);

  const withDifferences = (panel: ReactNode) => (
    <div className="space-y-4">
      {panel}
      {differences}
    </div>
  );

  if (state.status === "loading") return withDifferences(<LoadingBlock label="Loading the evidence" lines={6} />);
  if (state.status === "error")
    return withDifferences(
      <ErrorPanel
        title="Could not load the evidence"
        message={state.message}
        unreachable={state.unreachable}
        onRetry={() => {
          setState({ status: "loading" });
          setAttempt((a) => a + 1);
        }}
      />,
    );

  const { rows, limits, status, failures = [] } = state.data;
  if (status === "unreadable")
    return withDifferences(<EmptyPanel title="Evaluation output could not be read">No numbers are shown. Run the evaluation command again.</EmptyPanel>);
  if (rows.length === 0 && limits.length === 0)
    return withDifferences(<EmptyPanel title="Not yet run">Run the evaluation command to generate the table. Nothing is typed in by hand.</EmptyPanel>);

  const headline = state.headline;
  const rulesOnly = rows.filter((r) => WITHOUT_A_MODEL.has(r.evidence_class));
  // Live reports carry small rules-only samples of their own. The headline and the
  // main table use the largest rules-only run; the rest stay available below.
  const mainCommit = largest(headline?.rules_only ?? [])[0]?.commit ?? null;
  const mainRows = rulesOnly.filter((r) => !mainCommit || r.commit.startsWith(mainCommit.slice(0, 12)) || mainCommit.startsWith(r.commit));
  const sampleRows = rulesOnly.filter((r) => !mainRows.includes(r));
  const withModel = rows.filter((r) => !WITHOUT_A_MODEL.has(r.evidence_class));

  return (
    <div className="space-y-4">
      {IS_MOCK && (
        <Alert>
          <FlaskConical aria-hidden />
          <AlertTitle>Mock sample data</AlertTitle>
          <AlertDescription>Every figure here was invented for the mock. None comes from a run.</AlertDescription>
        </Alert>
      )}
      {failures.length > 0 && (
        <Alert variant="destructive">
          <AlertTitle>A control failed in this run</AlertTitle>
          <AlertDescription>{failures.join(" ")}</AlertDescription>
        </Alert>
      )}
      {headline && (
        <div className="grid items-start gap-3 lg:grid-cols-2">
          <HeadlineGroup title="Rules only" detail="Code and rules, with no model. Read from the results file." items={largest(headline.rules_only)} />
          <div className="space-y-3">
            <HeadlineGroup title="Live model" detail="With the agents, live. Never compare with rules only." items={[...headline.live]} />
            <HeadlineGroup
              title="With the model: tuned and unseen flights"
              detail="Run with the agents on the tuning and held-out flights. Each set names its class. Never compare across classes."
              items={[...headline.other]}
            />
          </div>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Generated from run output. Numbers with different evidence classes must not be compared with each other.
      </p>
      {differences}
      {limits.length > 0 && (
        <details className="rounded-xl border border-border bg-card p-3">
          <summary className="cursor-pointer">
            <h3 className="inline font-display text-sm font-semibold">Limits: what these numbers do not show</h3>
          </summary>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm">
            {limits.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
      <ResultsTable title="Full results: rules only and tests" rows={mainRows} />
      <ResultsTable title="Full results: with the model" rows={withModel} />
      {sampleRows.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-medium">Rules-only rows from the smaller samples of the live runs</summary>
          <ResultsTable title="Rules only, on the live runs' samples" rows={sampleRows} />
        </details>
      )}
    </div>
  );
}
