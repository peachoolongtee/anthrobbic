import type { ReactNode } from "react";
import { CircleAlert, Inbox, WifiOff } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { API_URL } from "@/lib/env";
import { IS_MOCK } from "@/lib/api";

export function ErrorPanel({
  title,
  message,
  onRetry,
  unreachable,
  compact,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
  unreachable?: boolean;
  /** Short form for a narrow column. The full explanation is shown elsewhere. */
  compact?: boolean;
}) {
  const Icon = unreachable ? WifiOff : CircleAlert;
  return (
    <Alert variant="destructive">
      <Icon aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {unreachable && !IS_MOCK && !compact && (
          <>
            <p className="mt-1">
              The planning service is not answering, so no recovery plan can be made or signed off until it is back.
              Your flight data has not been touched. Ask whoever runs this screen to start the service, then try
              again.
            </p>
            <details className="mt-1">
              <summary className="cursor-pointer font-medium">For the person running it</summary>
              <p className="mt-1">
                The dashboard looks for the service at <span className="font-mono">{API_URL}</span>. Start it with{" "}
                <span className="font-mono">pnpm dev:api</span>, or build the dashboard with{" "}
                <span className="font-mono">NEXT_PUBLIC_API_MODE=mock</span> to use sample data.
              </p>
            </details>
          </>
        )}
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            Try again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function EmptyPanel({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border border-dashed px-4 py-8 text-center">
      <Inbox aria-hidden className="size-5 text-muted-foreground" />
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}

export function LoadingBlock({ label, lines = 4 }: { label: string; lines?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-2">
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={i === 0 ? "h-6 w-2/3" : "h-4 w-full"} />
      ))}
    </div>
  );
}
