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
