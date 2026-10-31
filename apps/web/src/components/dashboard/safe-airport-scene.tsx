"use client";

import type { ComponentProps } from "react";
import { AirportScene } from "@/components/dashboard/airport-scene";
import { VisualBoundary } from "@/components/dashboard/visual-boundary";

/**
 * The 3D airport inside an error boundary. If WebGL is missing or the scene
 * throws, a labelled panel takes its place and the dashboard keeps working.
 * Default export, so it can replace airport-scene in a next/dynamic import.
 */
export function SafeAirportScene(props: ComponentProps<typeof AirportScene>) {
  return (
    <VisualBoundary label="3D airport view" detail="Graphics are not available here. Use the runway and gate controls as normal.">
      <AirportScene {...props} />
    </VisualBoundary>
  );
}

export default SafeAirportScene;
