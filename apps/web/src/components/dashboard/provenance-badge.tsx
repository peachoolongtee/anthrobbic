import { Badge } from "@/components/ui/badge";
import type { Provenance } from "@/lib/api-types";
import { PROVENANCE_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

// Provenance is metadata, not status, so every kind shares one neutral tone
// and is told apart by its word or letter. Synthetic gets a dashed outline.
const TONE: Record<Provenance, string> = {
  real: "border border-transparent bg-muted text-foreground",
  derived: "border border-transparent bg-muted text-muted-foreground",
  synthetic: "border border-dashed border-muted-foreground/60 bg-transparent text-muted-foreground",
};

/** Says where a value came from. The word is always shown, never colour alone. */
export function ProvenanceBadge({ provenance, className }: { provenance: Provenance; className?: string }) {
  const meta = PROVENANCE_LABEL[provenance];
  return (
    <Badge variant="outline" title={meta.detail} className={cn(TONE[provenance], className)}>
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
        "inline-grid size-[1.125rem] place-items-center rounded-[3px] font-sans text-xs leading-none font-semibold no-underline",
        TONE[provenance],
        className,
      )}
    >
      <span aria-hidden>{meta.name[0]}</span>
      <span className="sr-only">{meta.name}</span>
    </abbr>
  );
}
