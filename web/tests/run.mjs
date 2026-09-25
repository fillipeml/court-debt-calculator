/** Runs every *.test.mts file in this folder in its own Node process and aggregates the result.
 *  Run: npm test (Node 22.18+ strips types natively; older 22.x gets the flag). */
import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = dirname(fileURLToPath(import.meta.url));
const files = readdirSync(dir)
  .filter((f) => f.endsWith(".test.mts"))
  .sort();
const flags = process.features.typescript ? [] : ["--experimental-strip-types"];

let failed = 0;
for (const f of files) {
  console.log(`\n=== ${f}`);
  const r = spawnSync(process.execPath, [...flags, "--no-warnings", join(dir, f)], { stdio: "inherit" });
  if (r.status !== 0) failed++;
}
console.log(`\n${files.length - failed}/${files.length} test files passed`);
process.exit(failed ? 1 : 0);
