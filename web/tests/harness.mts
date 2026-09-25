/** Minimal test harness: no dependencies, runs on Node's native type stripping. */

let passed = 0;
let failed = 0;

export function check(name: string, cond: boolean, detail = ""): void {
  if (cond) {
    passed++;
    console.log(`  ok   ${name}`);
  } else {
    failed++;
    console.log(`  FAIL ${name} ${detail}`.trimEnd());
  }
}

export function equal(name: string, actual: unknown, expected: unknown): void {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  check(name, a === e, `expected ${e}, got ${a}`);
}

export function section(title: string): void {
  console.log(`\n[${title}]`);
}

export function done(): never {
  console.log(`\nResult: ${passed} ok, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}
