"use client";

import { useEffect, useRef } from "react";
import { animate, motion, useInView, useMotionValue, useReducedMotion, useTransform } from "motion/react";

const fmt = new Intl.NumberFormat("en-US");

/**
 * A whole number that counts up from zero the first time it scrolls into
 * view. Shows the final value at once when the system asks for reduced
 * motion. Use `as="tspan"` inside an SVG <text>. The text updates through a
 * motion value, so counting re-renders nothing.
 */
export function CountUp({
  value,
  format = (n) => fmt.format(n),
  as = "span",
}: {
  value: number;
  format?: (n: number) => string;
  as?: "span" | "tspan";
}) {
  const ref = useRef<HTMLSpanElement & SVGTSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const count = useMotionValue(reduce ? value : 0);
  const text = useTransform(count, (n) => format(Math.round(n)));

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      count.set(value);
      return;
    }
    const controls = animate(count, value, {
      duration: Math.min(1.4, 0.5 + Math.log10(Math.max(value, 1)) * 0.15),
      ease: [0.22, 1, 0.36, 1],
    });
    return () => controls.stop();
  }, [count, inView, reduce, value]);

  const Tag = as === "tspan" ? motion.tspan : motion.span;
  return (
    <Tag ref={ref} className="tabular-nums">
      {text}
    </Tag>
  );
}
