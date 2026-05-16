import test from "node:test";
import assert from "node:assert/strict";
import { CrdtEngine } from "../../src/peer.js";
import { sync } from "../../src/sync/protocol.js";

test("sync is idempotent", async () => {
  const a = new CrdtEngine({ peerId: "A", fkPolicy: "tombstone" });
  const b = new CrdtEngine({ peerId: "B", fkPolicy: "tombstone" });
  a.execute("INSERT INTO users VALUES ('u1', 'a@x.com', 'A')");
  await sync(a, b);
  const once = a.snapshotHash();
  await sync(a, b);
  assert.equal(a.snapshotHash(), once);
  assert.equal(a.snapshotHash(), b.snapshotHash());
});

