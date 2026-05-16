import test from "node:test";
import assert from "node:assert/strict";
import { concurrent, dominates, increment, mergeClock } from "../../src/crdt/causal_clock.js";

test("vector clock increment, merge, dominance, concurrency", () => {
  const a1 = increment({}, "A");
  const a2 = increment(a1, "A");
  const b1 = increment({}, "B");
  assert.deepEqual(a2, { A: 2 });
  assert.deepEqual(mergeClock(a2, b1), { A: 2, B: 1 });
  assert.equal(dominates(a2, a1), true);
  assert.equal(concurrent(a1, b1), true);
});

