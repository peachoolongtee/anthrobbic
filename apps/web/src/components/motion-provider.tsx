"use client";

import { MotionConfig } from "motion/react";
import { SPRING } from "@/lib/motion";

/** Gives every animation the shared spring, and drops movement when the system asks for reduced motion. */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user" transition={SPRING}>
      {children}
    </MotionConfig>
  );
}
