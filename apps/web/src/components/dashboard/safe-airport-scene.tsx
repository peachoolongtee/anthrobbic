"use client";

import type { ComponentProps } from "react";
import { AirportScene } from "@/components/dashboard/airport-scene";
import { VisualBoundary, VisualFallback } from "@/components/dashboard/visual-boundary";
import { useWebGL } from "@/hooks/use-webgl";

const DETAIL = "Graphics are not available here. The flat airport diagram and the rest of the page work as normal.";

/**
 * The 3D airport inside an error boundary. If WebGL is missing or the scene
 * throws, a labelled panel takes its place and the dashboard keeps working.
 * Default export, so it can replace airport-scene in a next/dynamic import.
 */
export function SafeAirportScene(props: ComponentProps<typeof AirportScene>) {
  const webgl = useWebGL();
  if (!webgl) return <VisualFallback label="3D airport view" detail={DETAIL} />;
  return (
    <VisualBoundary label="3D airport view" detail={DETAIL}>
      <AirportScene {...props} />
    </VisualBoundary>
  );
}

export default SafeAirportScene;
