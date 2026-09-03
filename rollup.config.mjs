import resolve from "@rollup/plugin-node-resolve";
import typescript from "@rollup/plugin-typescript";
import terser from "@rollup/plugin-terser";

// One self-contained bundle. Lit is bundled in on purpose: /config/www/ is a flat
// directory of files, not a module graph, and a card that needs a second file to
// load is a card that half-works after a copy-paste.
const ts = () => typescript({ tsconfig: "./tsconfig.json", noEmit: false, declaration: false });

export default [
  {
    input: "src/day-spine-card.ts",
    output: { file: "dist/day-spine-card.js", format: "es", sourcemap: false },
    plugins: [resolve(), ts(), terser({ format: { comments: false } })],
  },
  // The harness: same card, plus the mock feeds, unminified so it can be read in
  // devtools. Never copied to /config/www/.
  {
    input: "src/dev-entry.ts",
    output: { file: "dev/dev-bundle.js", format: "es", sourcemap: true },
    plugins: [resolve(), ts()],
  },
];
