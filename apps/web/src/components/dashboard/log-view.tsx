"use client";

import { useEffect, useState } from "react";
import { CircleAlert, CircleCheck } from "lucide-react";
import { api, describeError, isUnreachable } from "@/lib/api";
import type { RunLog, VerifyResult } from "@/lib/api-types";
import { cn } from "@/lib/utils";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyPanel, ErrorPanel, LoadingBlock } from "@/components/dashboard/states";

type State =
  | { status: "loading" }
  | { status: "error"; message: string; unreachable: boolean }
  | { status: "ready"; log: RunLog };

/** Mount with a `key` of run and log head so it reloads when either changes. */
export function LogView({
  runId,
  logHead,
  tamper,
}: {
  runId: string;
  logHead: string;
  tamper: VerifyResult | null;
}) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .getLog(runId)
      .then((log) => live && setState({ status: "ready", log }))
      .catch((err) => live && setState({ status: "error", message: describeError(err), unreachable: isUnreachable(err) }));
    return () => {
      live = false;
    };
  }, [runId, logHead, attempt]);

  if (state.status === "loading") return <LoadingBlock label="Loading the log" lines={5} />;
  if (state.status === "error")
    return (
      <ErrorPanel
        title="Could not load the log"
        message={state.message}
        unreachable={state.unreachable}
        onRetry={() => {
          setState({ status: "loading" });
          setAttempt((a) => a + 1);
        }}
      />
    );
  const { log } = state;
  if (log.entries.length === 0) return <EmptyPanel title="The log is empty">Nothing has been recorded for this run yet.</EmptyPanel>;

  return (
    <div className="space-y-3">
      <div className="space-y-2 text-sm">
        <p
          className={cn(
            "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5",
            log.verify.valid ? "border-success/40 bg-success-soft" : "border-destructive/40 bg-destructive-soft",
          )}
        >
          {log.verify.valid ? (
            <CircleCheck aria-hidden className="size-4 text-success" />
          ) : (
            <CircleAlert aria-hidden className="size-4 text-destructive" />
          )}
          <span>
            <strong>{log.verify.valid ? "The log checks out." : "The log does not check out."}</strong>{" "}
            {log.verify.reason ?? ""}
          </span>
        </p>
        {tamper && (
          <p
            className={cn(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5",
              tamper.valid ? "border-destructive/40 bg-destructive-soft" : "border-success/40 bg-success-soft",
            )}
          >
            {tamper.valid ? <CircleAlert aria-hidden className="size-4 text-destructive" /> : <CircleCheck aria-hidden className="size-4 text-success" />}
            <span>
              <strong>Tampered copy: {tamper.valid ? "not detected." : "detected."}</strong>{" "}
              {tamper.reason ?? ""}
              {tamper.first_bad_seq !== null && ` First bad entry: ${tamper.first_bad_seq}.`}
            </span>
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Each entry holds the hash of the one before, so an edit breaks the chain. The chain alone cannot catch a
          full rewrite. The head below is recorded on the sign-off so it can be compared.
        </p>
        <p className="font-mono text-xs break-all">
          <span className="font-sans font-medium">Log head </span>
          {logHead}
        </p>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">No.</TableHead>
            <TableHead>What happened</TableHead>
            <TableHead className="hidden sm:table-cell">Hash</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {log.entries.map((e) => {
            const bad = tamper && tamper.first_bad_seq === e.seq;
            return (
              <TableRow key={e.seq} className={cn(bad && "bg-destructive-soft")}>
                <TableCell>{e.seq}</TableCell>
                <TableCell className="whitespace-normal">
                  <span className="text-xs text-muted-foreground">{e.kind}</span>
                  <br />
                  {e.summary}
                  {bad && <strong className="ml-2 text-destructive">First bad entry</strong>}
                </TableCell>
                <TableCell className="hidden font-mono text-xs sm:table-cell">{e.hash}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
