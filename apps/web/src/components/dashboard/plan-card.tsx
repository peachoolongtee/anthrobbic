import { Bot, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Card as PlanCardData, Deal, ModelNote } from "@/lib/api-types";
import { DOMAIN_LABEL } from "@/lib/labels";
import { ProvenanceBadge } from "@/components/dashboard/provenance-badge";
import { RuleList } from "@/components/dashboard/rule-line";

export function PlanCard({
  card,
  deal,
  modelNotes,
}: {
  card: PlanCardData;
  deal: Deal;
  modelNotes: ModelNote[];
}) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardDescription>Recovery plan</CardDescription>
          <CardTitle className="text-lg leading-snug">{card.action}</CardTitle>
          <CardDescription>
            Chosen from {deal.packages_legal} legal plans out of {deal.packages_considered} considered.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {card.action_facts.map((f) => (
              <div key={f.key} className="flex items-center justify-between gap-2 border-b py-1 text-sm">
                <dt className="text-muted-foreground">{f.label}</dt>
                <dd className="flex items-center gap-1.5 font-medium">
                  {f.value}
                  <ProvenanceBadge provenance={f.provenance} />
                </dd>
              </div>
            ))}
          </dl>

          <section aria-labelledby="why-heading">
            <h3 id="why-heading" className="text-sm font-semibold">
              Why this plan
            </h3>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
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
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
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

          <section aria-labelledby="rules-heading">
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
