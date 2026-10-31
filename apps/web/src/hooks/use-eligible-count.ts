import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** How many eligible flights the data holds, from the API. Null until known, or if it does not answer. */
export function useEligibleCount(): number | null {
  const [total, setTotal] = useState<number | null>(null);
  useEffect(() => {
    let live = true;
    api
      .eligibleCount()
      .then((r) => live && setTotal(r.eligible_total))
      .catch(() => {
        // Callers read the same without the figure, so nothing is shown.
      });
    return () => {
      live = false;
    };
  }, []);
  return total;
}
