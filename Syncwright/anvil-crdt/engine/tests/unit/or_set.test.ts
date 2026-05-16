import test from "node:test";
import assert from "node:assert/strict";
import { OrSet } from "../../src/crdt/or_set.js";

test("OR-set is add-wins for concurrent add and remove", () => {
  const a = new OrSet();
  const b = new OrSet();
  a.add("u1", "A", { A: 1 });
  b.merge(a);
  b.remove("u1", b.observedTags("u1"));
  a.add("u1", "A", { A: 2 });
  a.merge(b);
  b.merge(a);
  assert.equal(a.contains("u1"), true);
  assert.equal(b.contains("u1"), true);
});

