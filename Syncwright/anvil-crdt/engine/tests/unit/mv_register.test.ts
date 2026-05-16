import test from "node:test";
import assert from "node:assert/strict";
import { mergeRegister, readRegister, writeRegister } from "../../src/crdt/mv_register.js";

test("MV-register keeps concurrent versions and drops dominated versions", () => {
  const a = writeRegister([], "Alice", "A", { A: 1 });
  const b = writeRegister([], "Alice Prime", "B", { B: 1 });
  const merged = mergeRegister(a, b);
  assert.equal(merged.length, 2);
  assert.equal(readRegister(merged), "Alice");
  const later = writeRegister(merged, "Alice Cooper", "A", { A: 2, B: 1 });
  assert.equal(later.length, 1);
  assert.equal(readRegister(later), "Alice Cooper");
});

