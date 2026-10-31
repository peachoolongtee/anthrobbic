"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical } from "lucide-react";
import { IS_MOCK } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Airliner } from "@/components/landing/airliner";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/dashboard/flights", label: "Flights" },
];

/** Brand, the two dashboard pages, and the sample-data tag. */
export function AppNav() {
  const path = usePathname();
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Link
        href="/"
        className="flex items-center gap-2 rounded-md font-display text-base font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Airliner className="size-5 -rotate-45 text-beacon" />
        <span className="max-md:sr-only">Arrival recovery</span>
      </Link>
      <nav aria-label="Pages" className="flex items-center gap-0.5 rounded-full border border-border bg-card/60 p-0.5">
        {LINKS.map((l) => {
          const on = path === l.href;
          return (
            <Link
              key={l.href}
              href={l.href}
              aria-current={on ? "page" : undefined}
              className={cn(
                "rounded-full px-3 py-1 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                on ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
      {IS_MOCK && (
        <span
          title="No backend and no model. Run outcomes are invented; 2015 figures are real."
          className="inline-flex items-center gap-1 rounded-md bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning"
        >
          <FlaskConical aria-hidden className="size-3.5" />
          <span className="max-sm:sr-only">Sample data</span>
        </span>
      )}
    </div>
  );
}
