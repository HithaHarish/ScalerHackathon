import test from "node:test";
import assert from "node:assert/strict";
import { CrdtEngine } from "../../src/peer.js";
import { sync } from "../../src/sync/protocol.js";

test("unique email loser is recoverable in conflict log", async () => {
  const a = new CrdtEngine({ peerId: "A", fkPolicy: "tombstone" });
  const b = new CrdtEngine({ peerId: "B", fkPolicy: "tombstone" });
  a.execute("INSERT INTO users VALUES ('u1', 'alice@x.com', 'Alice')");
  b.execute("INSERT INTO users VALUES ('u3', 'alice@x.com', 'Alice Prime')");
  await sync(a, b);
  assert.equal(a.query("SELECT * FROM users WHERE email = 'alice@x.com'").length, 1);
  assert.match(a.query("SELECT * FROM _conflict_log")[0].loser_row_data, /Alice Prime/);
});

