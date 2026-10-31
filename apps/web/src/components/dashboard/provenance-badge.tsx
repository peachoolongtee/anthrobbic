import { Badge } from "@/components/ui/badge";
import type { Provenance } from "@/lib/api-types";
import { PROVENANCE_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

const TONE: Record<Provenance, string> = {
  real: "bg-success-soft text-success",
  derived: "bg-info-soft text-info",
  synthetic: "bg-warning-soft text-warning",
};

/** Says where a value came from. The word is always shown, never colour alone. */
export function ProvenanceBadge({ provenance, className }: { provenance: Provenance; className?: string }) {
  const meta = PROVENANCE_LABEL[provenance];
  return (
    <Badge variant="outline" title={meta.detail} className={cn("border-transparent", TONE[provenance], className)}>
      {meta.name}
    </Badge>
  );
}

/**
 * The compact form: the first letter of the word in a small tinted square,
 * with the full word for screen readers and on hover.
 */
export function ProvenanceMark({ provenance, className }: { provenance: Provenance; className?: string }) {
  const meta = PROVENANCE_LABEL[provenance];
  return (
    <abbr
      title={`${meta.name}: ${meta.detail}`}
      className={cn(
        "inline-grid size-4 place-items-center rounded-[3px] font-sans text-[10px] leading-none font-semibold no-underline",
        TONE[provenance],
        className,
      )}
    >
      <span aria-hidden>{meta.name[0]}</span>
      <span className="sr-only">{meta.name}</span>
    </abbr>
  );
}
