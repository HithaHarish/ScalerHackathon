from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_engine(spec: str):
    module_name, class_name = spec.split(":")
    return getattr(importlib.import_module(module_name), class_name)


def run_seed(Engine, seed: int, peers_count: int, ops_count: int, fk_policy: str) -> dict:
    rng = random.Random(seed)
    peers = [Engine(peer_id=chr(ord("A") + i), fk_policy=fk_policy) for i in range(peers_count)]
    user_ids: list[str] = []
    for op in range(ops_count):
        peer = rng.choice(peers)
        choice = rng.choice(["insert_user", "update_user", "insert_order", "delete_user"])
        if choice == "insert_user" or not user_ids:
            uid = f"u{seed}_{op}"
            email = f"user{rng.randrange(max(1, ops_count // 4))}@x.com"
            peer.execute("INSERT INTO users (id, email, name) VALUES (?, ?, ?)", (uid, email, f"User {op}"))
            user_ids.append(uid)
        elif choice == "update_user":
            uid = rng.choice(user_ids)
            peer.execute("UPDATE users SET name = ? WHERE id = ?", (f"Name {seed}-{op}", uid))
        elif choice == "insert_order":
            uid = rng.choice(user_ids)
            peer.execute("INSERT INTO orders (id, user_id, status, total_cents) VALUES (?, ?, ?, ?)", (f"o{seed}_{op}", uid, "pending", op))
        else:
            uid = rng.choice(user_ids)
            peer.execute("DELETE FROM users WHERE id = ?", (uid,))

    for _ in range(5):
        order = list(range(peers_count))
        rng.shuffle(order)
        for i in range(len(order) - 1):
            peers[order[i]].sync(peers[order[i + 1]])
    for _ in range(4):
        for i in range(peers_count):
            for j in range(i + 1, peers_count):
                peers[i].sync(peers[j])

    hashes = [peer.snapshot_hash() for peer in peers]
    stats = [peer.metadata_stats() for peer in peers]
    return {
        "seed": seed,
        "converged": len(set(hashes)) == 1,
        "hash_match": len(set(hashes)) == 1,
        "hash": hashes[0],
        "metadata_ok": all(stat["max_clock_entries_per_version"] <= peers_count for stat in stats),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default="adapters.myteam:Engine")
    parser.add_argument("--fk-policy", default="tombstone")
    parser.add_argument("--randomized-seeds", nargs="*", type=int, default=[9999, 31415, 27182])
    parser.add_argument("--rand-peers", type=int, default=5)
    parser.add_argument("--rand-ops", type=int, default=150)
    parser.add_argument("--out", default="report.json")
    args = parser.parse_args()

    Engine = load_engine(args.adapter)
    results = [run_seed(Engine, seed, args.rand_peers, args.rand_ops, args.fk_policy) for seed in args.randomized_seeds]
    report = {
        "converged": all(result["converged"] for result in results),
        "hash_match": all(result["hash_match"] for result in results),
        "metadata_ok": all(result["metadata_ok"] for result in results),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not (report["converged"] and report["hash_match"] and report["metadata_ok"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
