import test from "node:test";
import assert from "node:assert/strict";
import { CrdtEngine } from "../../src/peer.js";
import { sync } from "../../src/sync/protocol.js";

test("five peers keep clock metadata bounded by writer count", async () => {
  const peers = ["A", "B", "C", "D", "E"].map((peerId) => new CrdtEngine({ peerId, fkPolicy: "tombstone" }));
  for (let i = 0; i < 25; i++) {
    const peer = peers[i % peers.length];
    peer.execute("INSERT INTO users (id, email, name) VALUES (?, ?, ?)", [`u${i}`, `u${i % 7}@x.com`, `User ${i}`]);
  }
  for (let round = 0; round < 4; round++) {
    for (let i = 0; i < peers.length - 1; i++) await sync(peers[i], peers[i + 1]);
  }
  const hash = peers[0].snapshotHash();
  assert.equal(peers.every((peer) => peer.snapshotHash() === hash), true);
  assert.equal(peers.every((peer) => peer.metadataStats().max_clock_entries_per_version <= peers.length), true);
});

