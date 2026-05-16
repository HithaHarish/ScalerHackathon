import test from "node:test";
import assert from "node:assert/strict";
import { CrdtEngine } from "../../src/peer.js";
import { sync } from "../../src/sync/protocol.js";

test("reference scenario converges with tombstone FK policy", async () => {
  const a = new CrdtEngine({ peerId: "A", fkPolicy: "tombstone" });
  const b = new CrdtEngine({ peerId: "B", fkPolicy: "tombstone" });
  const c = new CrdtEngine({ peerId: "C", fkPolicy: "tombstone" });
  a.execute("INSERT INTO users VALUES ('u1', 'alice@x.com', 'Alice')");
  a.execute("INSERT INTO users VALUES ('u2', 'bob@x.com', 'Bob')");
  b.execute("INSERT INTO users VALUES ('u3', 'alice@x.com', 'Alice Prime')");
  await sync(a, c);
  c.execute("DELETE FROM users WHERE id = 'u1'");
  a.execute("INSERT INTO orders VALUES ('o1', 'u1', 'pending', 1200)");
  a.execute("UPDATE users SET name = 'Alice Cooper' WHERE id = 'u1'");
  b.execute("UPDATE users SET email = 'alice@ex.org' WHERE id = 'u1'");
  for (let i = 0; i < 3; i++) {
    await sync(a, b);
    await sync(b, c);
    await sync(a, c);
  }
  assert.equal(a.snapshotHash(), b.snapshotHash());
  assert.equal(b.snapshotHash(), c.snapshotHash());
  assert.deepEqual(a.query("SELECT name, email FROM users WHERE id = 'u1'"), [{ name: "Alice Cooper", email: "alice@ex.org" }]);
  assert.equal(a.query("SELECT * FROM orders WHERE id = 'o1'").length, 1);
});

