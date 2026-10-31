import { useSyncExternalStore } from "react";

let cached: boolean | undefined;

function probe(): boolean {
  if (cached === undefined) {
    try {
      const canvas = document.createElement("canvas");
      cached = Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
    } catch {
      cached = false;
    }
  }
  return cached;
}

const subscribe = () => () => {};

/** True when this browser can make a WebGL context. Assumed true on the server. */
export function useWebGL(): boolean {
  return useSyncExternalStore(subscribe, probe, () => true);
}
