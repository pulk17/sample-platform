// Self-check for src/lib/diff.ts. Run: node web/scripts/diff.check.ts
import assert from "node:assert/strict";

import { diffRows, wordDiff } from "../src/lib/diff.ts";

const changed = (segs: { text: string; changed: boolean }[]) =>
  segs.filter((s) => s.changed).map((s) => s.text);

// A 40 ms timing shift marks only the millisecond digits.
const [l, r] = wordDiff("00:00:01,480|00:00:03,520|TLT|hi", "00:00:01,480|00:00:03,560|TLT|hi");
assert.deepEqual(changed(l), ["520"]);
assert.deepEqual(changed(r), ["560"]);

// An inserted space is the only change.
const [l2, r2] = wordDiff("My,um...", "My, um...");
assert.deepEqual(changed(l2), []);
assert.deepEqual(changed(r2), [" "]);

// Removed/added runs are interleaved pairwise; headers dropped; "--" line kept.
const rows = diffRows(
  ["--- expected", "+++ actual", "@@ -1,3 +1,3 @@", " same", "-a 1", "-b 1", "--- x", "+a 2", "+b 2"].join("\n"),
);
assert.deepEqual(
  rows.map((x) => x.kind),
  ["hunk", "ctx", "del", "add", "del", "add", "del"],
);
assert.equal(rows[6].segs[0].text, "-- x");

console.log("diff.check: ok");
