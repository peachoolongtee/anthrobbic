import { CircleCheck, CircleX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RuleResult } from "@/lib/api-types";
import { RULE_STATUS_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

function limitText(rule: RuleResult): string {
  if (rule.limit === null) return "unknown";
  const prefix = rule.direction === "at_least" ? "at least " : rule.direction === "at_most" ? "at most " : "";
  return `${prefix}${rule.limit} ${rule.unit}`.trim();
}

const STATUS_TONE: Record<NonNullable<RuleResult["status"]>, string> = {
  confirmed: "bg-success-soft text-success",
  policy: "bg-warning-soft text-warning",
  assumption: "bg-muted text-muted-foreground",
};

/**
 * One rule in one format everywhere: rule ID, observed value, limit, unit,
 * source. `result` says whether this rule held (plan summary) or was broken (refusal).
 */
export function RuleLine({ rule, result }: { rule: RuleResult; result: "held" | "broken" }) {
  const status = rule.status ? RULE_STATUS_LABEL[rule.status] : null;
  const Icon = result === "held" ? CircleCheck : CircleX;
  return (
    <li className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 py-2 text-sm">
      <Icon
        aria-hidden
        className={cn("mt-0.5 size-4", result === "held" ? "text-success" : "text-destructive")}
      />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-xs font-semibold">{rule.rule_id}</span>
          <span className="sr-only">{result === "held" ? "held" : "broken"}</span>
          {/* Held: the requirement. Broken: what the plan does wrong, never a red mark on the requirement. */}
          <span className={result === "broken" ? "font-medium" : undefined}>
            {result === "broken" ? rule.message : (rule.label ?? rule.message)}
          </span>
          {status && rule.status && (
            <Badge variant="outline" title={status.detail} className={cn("border-transparent", STATUS_TONE[rule.status])}>
              {status.name}
            </Badge>
          )}
        </div>
        <dl className="mt-0.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs">
          <div className="flex gap-1">
            <dt className="text-muted-foreground">Observed</dt>
            <dd className="font-semibold text-foreground">
              {rule.observed === null ? "unknown" : `${rule.observed} ${rule.unit}`}
            </dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-muted-foreground">Limit</dt>
            <dd className="font-medium text-foreground">{limitText(rule)}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-muted-foreground">Source</dt>
            <dd className="text-foreground">{rule.source}</dd>
          </div>
        </dl>
      </div>
    </li>
  );
}

export function RuleList({ rules, result }: { rules: RuleResult[]; result: "held" | "broken" }) {
  return (
    <ul className="divide-y">
      {rules.map((r, i) => (
        <RuleLine key={`${r.rule_id}-${i}`} rule={r} result={result} />
      ))}
    </ul>
  );
}
