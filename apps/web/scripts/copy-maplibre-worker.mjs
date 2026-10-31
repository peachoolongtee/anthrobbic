// MapLibre runs its tile work in a Web Worker. Turbopack does not serve the
// worker file from node_modules, so copy it into public/ before dev and build,
// where the dashboard points MapLibre at it. The copy is git-ignored.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const source = require.resolve("maplibre-gl/dist/maplibre-gl-worker.mjs");
mkdirSync(new URL("../public/", import.meta.url), { recursive: true });
copyFileSync(source, new URL("../public/maplibre-gl-worker.mjs", import.meta.url));
