import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import * as esbuild from "esbuild";

const ref = process.env.MEGACHESS_REF || "main";
mkdirSync("viz/demo/dist", { recursive: true });
await esbuild.build({
  entryPoints: ["viz/demo/main.tsx"],
  bundle: true,
  format: "esm",
  outfile: `viz/demo/dist/app.${ref}.js`,
  jsx: "automatic",
  define: { "process.env.NODE_ENV": '"production"' },
});
writeFileSync("viz/demo/dist/index.html", readFileSync("viz/demo/index.html", "utf8").replaceAll("__REF__", ref));
