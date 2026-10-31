import type { Transition, Variants } from "motion/react";

/**
 * Shared motion settings, so every animation in the app moves the same way.
 * Springs for things that move or change shape, a quick ease-out for things
 * that appear. MotionProvider turns all of it off for people who ask their
 * system for reduced motion.
 */

/** Pills, highlights and rows that glide to a new place or size. */
export const SPRING: Transition = { type: "spring", stiffness: 420, damping: 36, mass: 0.8 };

/** Content that appears: an ease-out that settles without overshoot. */
export const EASE_OUT: Transition = { duration: 0.45, ease: [0.22, 1, 0.36, 1] };

/** A container whose children rise into place one after another. */
export const STAGGER: Variants = {
  hidden: {},
  shown: { transition: { staggerChildren: 0.04 } },
};

/** A child of STAGGER: fades in while rising a short way. Transform and
 * opacity only, so it stays smooth beside the WebGL globe. */
export const RISE: Variants = {
  hidden: { opacity: 0, y: 10 },
  shown: { opacity: 1, y: 0, transition: { ...EASE_OUT, duration: 0.35 } },
};
