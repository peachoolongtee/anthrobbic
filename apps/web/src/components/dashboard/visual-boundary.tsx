"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { ImageOff } from "lucide-react";
import { cn } from "@/lib/utils";

/** A plain labelled panel for a visual that could not be drawn. */
export function VisualFallback({
  label,
  detail = "Graphics are not available here. The rest of the page works as normal.",
  className,
}: {
  label: string;
  detail?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        "flex size-full flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-border bg-card/40 p-4 text-center",
        className,
      )}
    >
      <ImageOff aria-hidden className="size-5 text-muted-foreground" />
      <p className="text-sm font-medium">{label} unavailable</p>
      <p className="max-w-xs text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}

/**
 * Keeps a WebGL or load failure inside one visual (map, 3D scene, globe):
 * it is replaced by a labelled panel and the rest of the page keeps working.
 */
export class VisualBoundary extends Component<
  { label: string; detail?: string; className?: string; fallback?: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.warn(`${this.props.label} failed to draw:`, error.message, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return this.props.fallback ?? <VisualFallback label={this.props.label} detail={this.props.detail} className={this.props.className} />;
  }
}
