"use client";

import { Fragment, useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, describeError, IS_MOCK, isUnreachable } from "@/lib/api";
import type { Evaluation, EvaluationRow } from "@/lib/api-types";
import { EVIDENCE_LABEL } from "@/lib/labels";
import { EmptyPanel, ErrorPanel, LoadingBlock } from "@/components/dashboard/states";

type State =
  | { status: "loading" }
  | { status: "error"; message: string; unreachable: boolean }
  | { status: "ready"; data: Evaluation };

const COLUMNS = 6;

function EvidenceRow({ row }: { row: EvaluationRow }) {
  const ev = EVIDENCE_LABEL[row.evidence_class] ?? { name: row.evidence_class, detail: "" };
  return (
    <TableRow className={row.arm === "unguarded_model" ? "bg-muted/50" : undefined}>
      <TableCell className="whitespace-normal">
        {row.metric}
        {row.arm === "unguarded_model" && (
          <Badge variant="outline" className="ml-2 border-destructive/50 text-destructive">
            Never eligible for sign-off
          </Badge>
        )}
      </TableCell>
      <TableCell className="font-semibold">
        {String(row.value)}
        {IS_MOCK && (
          <Badge variant="outline" className="mt-1 flex border-warning/50 bg-warning-soft text-warning">
            Mock sample data
          </Badge>
        )}
      </TableCell>
      <TableCell>{row.interval ? `${row.interval[0]} to ${row.interval[1]}` : "none"}</TableCell>
      <TableCell>{row.n}</TableCell>
      <TableCell>
        <Badge variant="secondary" title={ev.detail}>
          {ev.name}
        </Badge>
      </TableCell>
      <TableCell className="font-mono text-xs whitespace-normal">
        {row.commit}
        <br />
        {row.mode}, seed {row.seed}
      </TableCell>
    </TableRow>
  );
}

export function EvidenceView() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .getEvaluation()
      .then((data) => live && setState({ status: "ready", data }))
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

  const { rows, limits } = state.data;
  if (rows.length === 0 && limits.length === 0)
    return <EmptyPanel title="No evaluation yet">Run the evaluation command to generate the table. Nothing is typed in by hand.</EmptyPanel>;

  const guarded = rows.filter((r) => r.arm !== "unguarded_model");
  const comparison = rows.filter((r) => r.arm === "unguarded_model");

  return (
    <div className="space-y-3">
      {IS_MOCK && (
        <Alert>
          <FlaskConical aria-hidden />
          <AlertTitle>Mock sample data</AlertTitle>
          <AlertDescription>
            Every figure here was invented for the mock. None comes from a run.
          </AlertDescription>
        </Alert>
      )}
      <p className="text-xs text-muted-foreground">
        Generated from run output. Numbers with different evidence classes must not be compared with each other.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Measure</TableHead>
            <TableHead>Value</TableHead>
            <TableHead>Interval</TableHead>
            <TableHead>Cases</TableHead>
            <TableHead>Evidence</TableHead>
            <TableHead>Run</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {guarded.map((r, i) => (
            <EvidenceRow key={`g-${i}`} row={r} />
          ))}
          {comparison.length > 0 && (
            <>
              <TableRow className="bg-muted hover:bg-muted">
                <TableHead colSpan={COLUMNS} className="whitespace-normal">
                  For comparison: the same model with no rule check. It is never eligible for sign-off.
                </TableHead>
              </TableRow>
              {comparison.map((r, i) => (
                <EvidenceRow key={`c-${i}`} row={r} />
              ))}
            </>
          )}
          {limits.length > 0 && (
            <>
              <TableRow className="bg-muted hover:bg-muted">
                <TableHead colSpan={COLUMNS} className="whitespace-normal">
                  Limits: what these numbers do not show
                </TableHead>
              </TableRow>
              {limits.map((l, i) => (
                <Fragment key={`l-${i}`}>
                  <TableRow>
                    <TableCell colSpan={COLUMNS} className="whitespace-normal">
                      {l}
                    </TableCell>
                  </TableRow>
                </Fragment>
              ))}
            </>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
