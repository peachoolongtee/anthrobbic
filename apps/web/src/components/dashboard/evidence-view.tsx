"use client";

import { useEffect, useState } from "react";
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
      <span className="block">{commit?.slice(0, 12)}</span>
      <span className="block">
        {mode}, seed {seed}
      </span>
    </span>
  );
}

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
  if (!limits) return <LoadingBlock label="Loading the limits" lines={3} />;
  return (
    <section aria-labelledby="differences-heading" className="rounded-xl border border-border bg-card p-3">
      <h3 id="differences-heading" className="font-display text-sm font-semibold">
        {limits.title}
      </h3>
      <ul className="mt-1.5 space-y-1.5 text-sm">
        {limits.items.map((d) => (
          <li key={d.id}>
            <span className="font-medium">{d.limit}:</span> {d.what_we_do}{" "}
            <span className="text-muted-foreground">{d.why}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function HeadlineCard({ item }: { item: HeadlineItem }) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <p className="text-xs text-muted-foreground">{item.label}</p>
      {item.state === "absent" ? (
        <p className="mt-1 text-sm text-muted-foreground">Not in the results.</p>
      ) : (
        <>
          <p className="mt-0.5 font-display text-lg font-semibold tabular-nums">{item.value}</p>
          {item.interval_text && <p className="text-xs text-muted-foreground">Interval {item.interval_text}</p>}
          <div className="mt-1 space-y-0.5">
            <EvidenceBadge evidence={item.evidence_class} />
            <RunLine commit={item.commit} mode={item.mode} seed={item.seed} />
          </div>
        </>
      )}
    </div>
  );
}

function HeadlineGroup({ title, detail, items }: { title: string; detail: string; items: HeadlineItem[] }) {
  if (items.length === 0) return null;
  return (
    <section aria-label={title} className="space-y-1.5">
      <div>
        <h3 className="font-display text-sm font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{detail}</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {items.map((item, i) => (
          <HeadlineCard key={`${item.key}-${i}`} item={item} />
        ))}
      </div>
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
  return (
    <div className="space-y-4">
      <WorkbookDifferences />
      <EvaluationResults />
    </div>
  );
}

function EvaluationResults() {
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

  if (state.status === "loading") return <LoadingBlock label="Loading the evidence" lines={6} />;
  if (state.status === "error")
    return (
      <ErrorPanel
        title="Could not load the evidence"
        message={state.message}
        unreachable={state.unreachable}
        onRetry={() => {
          setState({ status: "loading" });
          setAttempt((a) => a + 1);
        }}
      />
    );

  const { rows, limits, status, failures = [] } = state.data;
  if (status === "unreadable")
    return <EmptyPanel title="Evaluation output could not be read">No numbers are shown. Run the evaluation command again.</EmptyPanel>;
  if (rows.length === 0 && limits.length === 0)
    return <EmptyPanel title="Not yet run">Run the evaluation command to generate the table. Nothing is typed in by hand.</EmptyPanel>;

  const headline = state.headline;
  const rulesOnly = rows.filter((r) => WITHOUT_A_MODEL.has(r.evidence_class));
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
        <>
          <HeadlineGroup title="Rules only" detail="Code and rules, with no model. Read from the results file." items={[...headline.rules_only]} />
          <HeadlineGroup title="Live model" detail="With the agents, live. Never compare with rules only." items={[...headline.live]} />
          <HeadlineGroup title="Other evidence" detail="Other classes of evidence. Never compare across classes." items={[...headline.other]} />
        </>
      )}
      <p className="text-xs text-muted-foreground">
        Generated from run output. Numbers with different evidence classes must not be compared with each other.
      </p>
      <ResultsTable title="Full results: rules only and tests" rows={rulesOnly} />
      <ResultsTable title="Full results: with the model" rows={withModel} />
      {limits.length > 0 && (
        <section aria-label="Limits" className="space-y-1">
          <h3 className="font-display text-sm font-semibold">Limits: what these numbers do not show</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {limits.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
