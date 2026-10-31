import { Bot, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Card as PlanCardData, Deal, ModelNote, Run } from "@/lib/api-types";
import { DOMAIN_LABEL } from "@/lib/labels";
import { FallbackNotice } from "@/components/dashboard/fallback-notice";
import { ProvenanceBadge } from "@/components/dashboard/provenance-badge";
import { RuleList } from "@/components/dashboard/rule-line";

export function PlanCard({
  run,
  card,
  deal,
  modelNotes,
}: {
  run: Run;
  card: PlanCardData;
  deal: Deal;
  modelNotes: ModelNote[];
}) {
  return (
    <div className="space-y-3">
      <Card size="sm">
        <CardHeader>
          <CardTitle className="text-base leading-snug">{card.action}</CardTitle>
          <CardDescription>
            Chosen from {deal.packages_legal} legal plans out of {deal.packages_considered} considered.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <FallbackNotice run={run} onlyFaults />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
            {card.action_facts.map((f) => (
              <div key={f.key} className="text-sm">
                <dt className="text-xs text-muted-foreground">{f.label}</dt>
                <dd className="flex flex-wrap items-center gap-1 font-medium">
                  {f.value}
                  <ProvenanceBadge provenance={f.provenance} />
                </dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-muted-foreground">
            <strong className="font-semibold text-foreground">Real</strong> = US DOT record
            {" · "}
            <strong className="font-semibold text-foreground">Derived</strong> = computed from it
            {" · "}
            <strong className="font-semibold text-foreground">Synthetic</strong> = invented for this demo
          </p>

          <div className="grid gap-x-6 gap-y-3 md:grid-cols-2">
            <section aria-labelledby="why-heading">
              <h3 id="why-heading" className="text-sm font-semibold">
                Why this plan
              </h3>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-5 text-sm">
                {card.why.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="risks-heading">
              <h3 id="risks-heading" className="flex items-center gap-1.5 text-sm font-semibold">
                <TriangleAlert aria-hidden className="size-4 text-warning" />
                What could go wrong
              </h3>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-5 text-sm">
                {card.risks.map((r, i) => (
                  <li key={i}>
                    {r.text}
                    {r.rule_id && (
                      <>
                        {" "}
                        <span className="font-mono text-xs text-muted-foreground">({r.rule_id})</span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section aria-labelledby="rules-heading" className="border-t pt-2">
            <h3 id="rules-heading" className="text-sm font-semibold">
              Limits this plan was checked against
            </h3>
            <p className="text-xs text-muted-foreground">
              Every rule held. Policy and assumption limits are our own and are not regulations.
            </p>
            <RuleList rules={card.rules} result="held" />
          </section>
        </CardContent>
      </Card>

      <ModelNotes notes={modelNotes} />
    </div>
  );
}

/** Separate from the card on purpose. The rules never read these. */
function ModelNotes({ notes }: { notes: ModelNote[] }) {
  if (notes.length === 0) return null;
  return (
    <section
      aria-labelledby="notes-heading"
      className="rounded-lg border border-dashed bg-muted/50 p-3 text-sm"
    >
      <h3 id="notes-heading" className="flex flex-wrap items-center gap-2 font-semibold">
        <Bot aria-hidden className="size-4" />
        Notes from the model
        <Badge variant="outline" className="border-warning/50 bg-warning-soft text-warning">
          Unverified
        </Badge>
      </h3>
      <p className="text-xs text-muted-foreground">
        Written by a language model. Not checked, and not used to decide anything above.
      </p>
      <ul className="mt-2 space-y-1">
        {notes.map((n, i) => (
          <li key={i}>
            <span className="font-medium">{DOMAIN_LABEL[n.domain]}:</span> {n.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
