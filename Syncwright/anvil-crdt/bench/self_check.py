from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_engine(spec: str):
    module_name, class_name = spec.split(":")
    return getattr(importlib.import_module(module_name), class_name)


def converge(*peers, rounds: int = 4) -> None:
    for _ in range(rounds):
        for i in range(len(peers)):
            for j in range(i + 1, len(peers)):
                peers[i].sync(peers[j])


def reference_scenario(Engine, fk_policy: str):
    a = Engine(peer_id="A", fk_policy=fk_policy)
    b = Engine(peer_id="B", fk_policy=fk_policy)
    c = Engine(peer_id="C", fk_policy=fk_policy)

    a.execute("INSERT INTO users VALUES ('u1', 'alice@x.com', 'Alice')")
    a.execute("INSERT INTO users VALUES ('u2', 'bob@x.com', 'Bob')")
    b.execute("INSERT INTO users VALUES ('u3', 'alice@x.com', 'Alice Prime')")

    a.sync(c)
    c.execute("DELETE FROM users WHERE id = 'u1'")

    a.execute("INSERT INTO orders VALUES ('o1', 'u1', 'pending', 1200)")
    a.execute("UPDATE users SET name = 'Alice Cooper' WHERE id = 'u1'")
    b.execute("UPDATE users SET email = 'alice@ex.org' WHERE id = 'u1'")

    converge(a, b, c)
    hashes = {peer.snapshot_hash() for peer in (a, b, c)}
    assert len(hashes) == 1, hashes

    alice_rows = a.query("SELECT * FROM users WHERE email = 'alice@x.com' OR email = 'alice@ex.org'")
    assert len(alice_rows) == 1, alice_rows
    conflicts = a.query("SELECT * FROM _conflict_log")
    assert conflicts and "Alice Prime" in conflicts[0]["loser_row_data"], conflicts

    order = a.query("SELECT * FROM orders WHERE id = 'o1'")
    if fk_policy == "tombstone":
        assert order and "users:u1" in a.dump_state()["tombstones"], a.dump_state()["tombstones"]
    elif fk_policy == "cascade":
        assert not order, order
    elif fk_policy == "orphan":
        assert order and order[0]["user_id"] is None, order

    u1 = a.query("SELECT name, email FROM users WHERE id = 'u1'")
    assert u1 == [{"name": "Alice Cooper", "email": "alice@ex.org"}], u1
    assert a.metadata_stats()["max_clock_entries_per_version"] <= 3
    return {"hash": next(iter(hashes)), "conflicts": conflicts, "u1": u1}


def idempotency_check(Engine, fk_policy: str):
    a = Engine(peer_id="A", fk_policy=fk_policy)
    b = Engine(peer_id="B", fk_policy=fk_policy)
    a.execute("INSERT INTO users VALUES ('u1', 'a@x.com', 'A')")
    b.execute("INSERT INTO orders VALUES ('o1', 'u1', 'pending', 10)")
    a.sync(b)
    first = a.snapshot_hash(), b.snapshot_hash()
    a.sync(b)
    second = a.snapshot_hash(), b.snapshot_hash()
    assert first == second, (first, second)


def empty_peer_check(Engine, fk_policy: str):
    a = Engine(peer_id="A", fk_policy=fk_policy)
    b = Engine(peer_id="B", fk_policy=fk_policy)
    for i in range(10):
        a.execute(f"INSERT INTO users VALUES ('u{i}', 'u{i}@x.com', 'User {i}')")
    a.sync(b)
    assert a.snapshot_hash() == b.snapshot_hash()
    b.sync(a)
    assert a.snapshot_hash() == b.snapshot_hash()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default="adapters.myteam:Engine")
    parser.add_argument("--fk-policy", default="tombstone", choices=["tombstone", "cascade", "orphan"])
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    Engine = load_engine(args.adapter)
    report = {
        "reference": reference_scenario(Engine, args.fk_policy),
        "idempotency": True,
        "empty_peer": True,
        "converged": True,
        "hash_match": True,
    }
    idempotency_check(Engine, args.fk_policy)
    empty_peer_check(Engine, args.fk_policy)

    print(json.dumps(report, indent=2, sort_keys=True))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()

