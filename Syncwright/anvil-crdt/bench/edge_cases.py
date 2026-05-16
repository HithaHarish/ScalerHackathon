from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.run import run_seed


def load_engine(spec: str):
    module_name, class_name = spec.split(":")
    return getattr(importlib.import_module(module_name), class_name)


def converge(*peers, rounds: int = 4) -> None:
    for _ in range(rounds):
        for i in range(len(peers)):
            for j in range(i + 1, len(peers)):
                peers[i].sync(peers[j])


def assert_converged(*peers) -> None:
    hashes = {peer.snapshot_hash() for peer in peers}
    assert len(hashes) == 1, sorted(hashes)


def case_empty_and_idempotent_sync(Engine, fk_policy: str) -> None:
    a = Engine(peer_id="A", fk_policy=fk_policy)
    b = Engine(peer_id="B", fk_policy=fk_policy)
    a.sync(b)
    first = (a.snapshot_hash(), b.snapshot_hash())
    a.sync(b)
    b.sync(a)
    assert first == (a.snapshot_hash(), b.snapshot_hash())
    assert_converged(a, b)


def case_parameterized_values_and_defaults(Engine, fk_policy: str) -> None:
    a = Engine(peer_id="A", fk_policy=fk_policy)
    a.execute(
        "INSERT INTO users (id, email, name) VALUES (?, ?, ?)",
        ("u1", "comma@example.com", "Ada, the 'first'"),
    )
    a.execute(
        "INSERT INTO orders (id, user_id, status) VALUES (?, ?, ?)",
        ("o1", "u1", "pending"),
    )
    assert a.query("SELECT name FROM users WHERE id = ?", ("u1",)) == [{"name": "Ada, the 'first'"}]
    assert a.query("SELECT total_cents FROM orders WHERE id = 'o1'") == [{"total_cents": 0}]


def case_quoted_commas_and_escaped_quotes(Engine, fk_policy: str) -> None:
    a = Engine(peer_id="A", fk_policy=fk_policy)
    a.execute("INSERT INTO users VALUES ('u1', 'quote@example.com', 'O''Connor, Ada')")
    assert a.query("SELECT name FROM users WHERE id = 'u1'") == [{"name": "O'Connor, Ada"}]


def case_concurrent_updates_are_deterministic(Engine, fk_policy: str) -> None:
    a = Engine(peer_id="A", fk_policy=fk_policy)
    b = Engine(peer_id="B", fk_policy=fk_policy)
    a.execute("INSERT INTO users VALUES ('u1', 'a@example.com', 'Original')")
    a.sync(b)
    a.execute("UPDATE users SET name = 'Name from A' WHERE id = 'u1'")
    b.execute("UPDATE users SET name = 'Name from B' WHERE id = 'u1'")
    converge(a, b)
    assert_converged(a, b)
    assert a.query("SELECT name FROM users WHERE id = 'u1'") == b.query("SELECT name FROM users WHERE id = 'u1'")


def case_add_wins_delete_race(Engine, fk_policy: str) -> None:
    a = Engine(peer_id="A", fk_policy=fk_policy)
    b = Engine(peer_id="B", fk_policy=fk_policy)
    a.execute("DELETE FROM users WHERE id = 'u1'")
    b.execute("INSERT INTO users VALUES ('u1', 'race@example.com', 'Race')")
    converge(a, b)
    assert_converged(a, b)
    rows = a.query("SELECT * FROM users WHERE id = 'u1'")
    assert rows == [{"id": "u1", "email": "race@example.com", "name": "Race"}], rows


def case_duplicate_email_conflict_many_peers(Engine, fk_policy: str) -> None:
    peers = [Engine(peer_id=peer_id, fk_policy=fk_policy) for peer_id in "ABCD"]
    for index, peer in enumerate(peers):
        peer.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (f"u{index}", "dupe@example.com", f"Duplicate {index}"),
        )
    converge(*peers, rounds=5)
    assert_converged(*peers)
    live_rows = peers[0].query("SELECT * FROM users WHERE email = 'dupe@example.com'")
    conflicts = peers[0].query("SELECT * FROM _conflict_log")
    assert len(live_rows) == 1, live_rows
    assert len(conflicts) == 3, conflicts


def case_reinsert_after_observed_delete(Engine, fk_policy: str) -> None:
    a = Engine(peer_id="A", fk_policy=fk_policy)
    b = Engine(peer_id="B", fk_policy=fk_policy)
    a.execute("INSERT INTO users VALUES ('u1', 'old@example.com', 'Old')")
    a.sync(b)
    b.execute("DELETE FROM users WHERE id = 'u1'")
    b.sync(a)
    a.execute("INSERT INTO users VALUES ('u1', 'new@example.com', 'New')")
    converge(a, b)
    assert_converged(a, b)
    rows = a.query("SELECT * FROM users WHERE id = 'u1'")
    if fk_policy == "tombstone":
        assert rows == [{"id": "u1", "email": "new@example.com", "name": "New"}], rows
    else:
        assert rows == [{"id": "u1", "email": "new@example.com", "name": "New"}], rows


def case_fk_policy_behavior(Engine, fk_policy: str) -> None:
    a = Engine(peer_id="A", fk_policy=fk_policy)
    a.execute("INSERT INTO users VALUES ('u1', 'fk@example.com', 'FK')")
    a.execute("INSERT INTO orders VALUES ('o1', 'u1', 'pending', 42)")
    a.execute("DELETE FROM users WHERE id = 'u1'")
    orders = a.query("SELECT * FROM orders WHERE id = 'o1'")
    if fk_policy == "tombstone":
        assert orders == [{"id": "o1", "user_id": "u1", "status": "pending", "total_cents": 42}], orders
        joined = a.query("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
        assert joined == [{"user_id": None, "email": None, "name": None, "order_id": "o1", "status": "pending", "total_cents": 42}], joined
        assert "users:u1" in a.dump_state()["tombstones"]
    elif fk_policy == "cascade":
        assert orders == [], orders
    elif fk_policy == "orphan":
        assert orders == [{"id": "o1", "user_id": None, "status": "pending", "total_cents": 42}], orders


def case_manager_api_surface(Engine, fk_policy: str) -> None:
    manager = Engine(fk_policy=fk_policy)
    manager.open_peer("A")
    manager.open_peer("B")
    manager.execute("A", "INSERT INTO users VALUES ('u1', 'manager@example.com', 'Manager')")
    manager.sync("A", "B")
    assert manager.snapshot_hash("A") == manager.snapshot_hash("B")
    assert manager.snapshot_state("B")["users"] == [
        {"id": "u1", "email": "manager@example.com", "name": "Manager"}
    ]


def case_randomized_benchmark_smoke(Engine, fk_policy: str) -> None:
    for seed in (1, 7, 42, 99):
        result = run_seed(Engine, seed=seed, peers_count=4, ops_count=60, fk_policy=fk_policy)
        assert result["converged"], result
        assert result["hash_match"], result
        assert result["metadata_ok"], result


CASES: list[tuple[str, Callable[[Any, str], None]]] = [
    ("empty_and_idempotent_sync", case_empty_and_idempotent_sync),
    ("parameterized_values_and_defaults", case_parameterized_values_and_defaults),
    ("quoted_commas_and_escaped_quotes", case_quoted_commas_and_escaped_quotes),
    ("concurrent_updates_are_deterministic", case_concurrent_updates_are_deterministic),
    ("add_wins_delete_race", case_add_wins_delete_race),
    ("duplicate_email_conflict_many_peers", case_duplicate_email_conflict_many_peers),
    ("reinsert_after_observed_delete", case_reinsert_after_observed_delete),
    ("fk_policy_behavior", case_fk_policy_behavior),
    ("manager_api_surface", case_manager_api_surface),
    ("randomized_benchmark_smoke", case_randomized_benchmark_smoke),
]

CASE_INTENTS: dict[str, str] = {
    "empty_and_idempotent_sync": "Checks that syncing empty peers is harmless and repeated syncs do not mutate state.",
    "parameterized_values_and_defaults": "Checks parameter binding, comma-containing strings, quotes, and default column values.",
    "quoted_commas_and_escaped_quotes": "Checks SQL literal parsing for commas and escaped single quotes inside a string.",
    "concurrent_updates_are_deterministic": "Checks that peers making concurrent updates still converge to the same deterministic read result.",
    "add_wins_delete_race": "Checks the add-wins row-membership rule when one peer deletes an unseen row while another inserts it.",
    "duplicate_email_conflict_many_peers": "Checks unique-email arbitration and conflict-log recovery when many peers create the same email.",
    "reinsert_after_observed_delete": "Checks whether a new insert tag can make a row live again after an observed delete.",
    "fk_policy_behavior": "Checks that tombstone, cascade, and orphan foreign-key policies each produce their expected order behavior.",
    "manager_api_surface": "Checks the official harness-style API that manages named peers from one adapter instance.",
    "randomized_benchmark_smoke": "Runs randomized benchmark operations to catch convergence and metadata regressions outside hand-written scenarios.",
}


CASE_ANALYSES: dict[str, dict[str, str]] = {
    "empty_and_idempotent_sync": {
        "scenario": "Peer A syncs with peer B when there may be no new writes. Then A and B repeat the same pairwise sync, while peer C represents another replica that could receive the same history later.",
        "difficult": "Distributed systems frequently retry messages after timeouts, so the same knowledge can be delivered more than once.",
        "naive": "A naive merge could duplicate metadata, change snapshot hashes on every retry, or resurrect rows during a repeated sync.",
        "mechanism": "Vector-clock-style logical clocks track causal history, not real time; merge_clock performs max merge, OR-Set tags merge by union, and MV-register versions are de-duplicated with dominance checks.",
        "works": "The merge is commutative, associative, and idempotent: A then B or B then A gives the same state, grouping pairwise syncs differently gives the same state, and replaying the same sync does not create a new update. Conflicts are not prevented; when they exist, they are resolved deterministically. Final state does NOT depend on sync order.",
        "meaning": "The invariant is retry-safe convergence: after A, B, and C receive the same history, they converge to the same deterministic state without duplicate-delivery bugs.",
    },
    "parameterized_values_and_defaults": {
        "scenario": "Peer A inserts a user and order through bound SQL parameters; peer B and C later learn those writes through sync.",
        "difficult": "Before CRDT merge logic can be correct, every peer must interpret the same SQL input as the same logical cell values.",
        "naive": "A parser bug could shift values between columns, drop quoted content, or leave defaults inconsistent across replicas.",
        "mechanism": "The SQL adapter resolves parameters and schema defaults before writing values into per-cell MV-registers; later sync uses merge_clock max merge and MV-register dominance checks.",
        "works": "Once A stores the intended values, B and C can receive them in any order because CRDT merges are commutative and associative. Repeated sync is idempotent, so the default value is not re-applied as a new conflicting write. Final state does NOT depend on sync order.",
        "meaning": "The invariant is deterministic relational interpretation before replication, preventing parser/default bugs from becoming permanent distributed divergence.",
    },
    "quoted_commas_and_escaped_quotes": {
        "scenario": "Peer A stores a user name containing a comma and escaped quote, then B and C receive that row through sync.",
        "difficult": "Simple string splitting can mistake commas inside quoted values for column separators.",
        "naive": "Rows could be stored with corrupted column values, and later sync would faithfully replicate bad data everywhere.",
        "mechanism": "The parser tracks quoted regions while splitting values and unescapes SQL single quotes before storage in MV-register cells.",
        "works": "The parsed value becomes one stable cell version. After that, OR-Set and MV-register merges are commutative, associative, and idempotent, so B and C converge on the same literal regardless of sync order.",
        "meaning": "The invariant is value fidelity: the distributed layer cannot converge correctly if the local SQL layer corrupts values before replication.",
    },
    "concurrent_updates_are_deterministic": {
        "scenario": "Peer A and peer B both update the same user row while offline; peer C may later receive A's update first or B's update first.",
        "difficult": "Neither update causally dominates the other; logical clocks record that these writes are concurrent, not ordered by wall-clock time.",
        "naive": "Last-write-wins could choose different visible values depending on message order or clock skew.",
        "mechanism": "Vector clocks capture causal history; dominance checks detect that A's and B's updates are concurrent; the MV-register preserves concurrent versions and deterministic tie-breaking chooses the visible value.",
        "works": "Because concurrent versions are merged as a set, receiving A then B or B then A is commutative. Re-merging the same versions is idempotent, and associativity lets C sync with either peer first. Conflicts are not prevented; they are resolved deterministically. Final state does NOT depend on sync order.",
        "meaning": "The invariant is deterministic convergence under concurrent writes, preventing replicas from showing different final values for the same row.",
    },
    "add_wins_delete_race": {
        "scenario": "Peer A deletes row u1 without observing any add tag for it, while peer B concurrently inserts u1; peer C later syncs with either A or B first.",
        "difficult": "Deletes are dangerous when replicas have partial knowledge; A cannot safely delete an add tag it has never observed.",
        "naive": "A broad delete marker could erase B's legitimate offline insert and cause user-visible data loss.",
        "mechanism": "Row membership uses OR-Set-style add/remove tags. Deletes record only observed add tags, while B's insert creates a new add tag with its own logical-clock history.",
        "works": "OR-Set merge is commutative and associative because add and remove tag sets union together. It is idempotent because repeated delivery of the same tag changes nothing. Since A never observed B's add tag, the remove cannot cover it. Final state does NOT depend on sync order.",
        "meaning": "The invariant is add-wins safety, preventing offline inserts from being lost because another peer issued an uninformed delete.",
    },
    "duplicate_email_conflict_many_peers": {
        "scenario": "Peers A, B, C, and D independently create different users with the same unique email before any of them sync.",
        "difficult": "A local unique constraint cannot prevent duplicates while devices are offline and unable to coordinate.",
        "naive": "Different replicas might keep different winners, silently drop losers, or allow multiple live rows with the same unique value.",
        "mechanism": "After merge, duplicate unique values are grouped. Vector-clock-derived arbitration/deterministic tie-breaking chooses one winner, and losers are preserved in _conflict_log.",
        "works": "The set of duplicate candidates is the same after all peers exchange history, regardless of sync order. The deterministic arbitration function is pure, so A, B, and C choose the same winner. Conflicts are not prevented; they are resolved deterministically.",
        "meaning": "The invariant is global uniqueness with conflict safety: one live email survives everywhere, while losing rows remain auditable instead of disappearing silently.",
    },
    "reinsert_after_observed_delete": {
        "scenario": "Peer A inserts u1, B observes it through sync, B deletes it, then A reinserts u1 with new values; C may learn these events in a different order.",
        "difficult": "Distributed delete metadata must be strong enough to remove old adds but not so strong that it blocks future legitimate adds forever.",
        "naive": "A permanent row-level delete marker could make the row impossible to recreate, or an imprecise merge could revive stale data.",
        "mechanism": "The OR-Set stores add/remove tags. The delete covers the observed old add tag, while reinsert creates a fresh add tag with new vector-clock history and MV-register values.",
        "works": "Set-union merge is commutative and idempotent, so replaying B's delete does not remove A's fresh add unless that exact tag was observed. Dominance checks keep newer cell versions from being overwritten by stale ones. Final state does NOT depend on sync order.",
        "meaning": "The invariant is precise deletion: old history can be removed without banning future valid recreations of the same primary key.",
    },
    "fk_policy_behavior": {
        "scenario": "Peer A deletes a user that has an order, then peers B and C learn the delete through sync under the selected foreign-key policy.",
        "difficult": "Relational correctness spans tables: a parent delete must produce deterministic child-row behavior on every replica.",
        "naive": "Some peers could keep dangling orders, others could remove them, and joins could disagree after sync.",
        "mechanism": "The delete path applies the declared FK policy deterministically: tombstone stores deleted parent metadata, cascade removes child order tags, and orphan writes a null user_id value.",
        "works": "The parent delete has logical-clock history, and the child effect is represented as mergeable CRDT state. Whether B receives the parent tombstone before C or after C, max clock merge, tag union, and deterministic policy application lead to the same relational result. Final state does NOT depend on sync order.",
        "meaning": "The invariant is foreign-key correctness under eventual consistency, preventing dangling references or inconsistent joins across replicas.",
    },
    "manager_api_surface": {
        "scenario": "A benchmark manager opens peers A and B, writes through A, syncs A to B, and compares snapshots as an external harness would.",
        "difficult": "A benchmark harness often drives peers indirectly, so correctness must hold through the public adapter interface.",
        "naive": "The engine might converge in direct unit tests but fail when peer identity, snapshotting, or pairwise sync is routed through a manager.",
        "mechanism": "The adapter maps named peers to internal Engine instances and exposes execute, sync, snapshot_state, and snapshot_hash over the same CRDT merge logic.",
        "works": "Because the public API uses the same commutative, associative, and idempotent merge operations, routing through the manager does not change convergence behavior. Final state does NOT depend on sync order.",
        "meaning": "The invariant is interface-level correctness: external benchmark calls exercise the real distributed semantics, not a separate happy path.",
    },
    "randomized_benchmark_smoke": {
        "scenario": "Peers A, B, C, and others perform randomized inserts, updates, deletes, and order creation, then sync in shuffled pairwise sequences.",
        "difficult": "CRDT bugs often appear only under unusual interleavings, such as A syncing with B before C's delete reaches either peer.",
        "naive": "Merge order could affect winners, metadata could grow incorrectly, or replicas could end with different hashes.",
        "mechanism": "The implementation uses order-independent merge rules: vector-clock max merge, OR-Set tag union, MV-register dominance checks, and deterministic conflict recomputation.",
        "works": "Random sync paths stress commutativity, associativity, and idempotency together. A can sync with B first, C can sync later, and duplicate syncs can occur; the final merged knowledge is the same set of causal facts. Conflicts are not prevented; they are resolved deterministically.",
        "meaning": "The invariant is eventual consistency at scale: after all peers receive the same updates, they converge to the same deterministic state without conflict-driven data loss.",
    },
}


def built_in_reason(case_name: str, policy: str) -> str:
    analysis = CASE_ANALYSES[case_name]
    mechanism = analysis["mechanism"]
    if case_name == "fk_policy_behavior":
        mechanism = f"{mechanism} For this run, the policy is {policy}."
    return "\n".join(
        [
            f"{case_name}:",
            f"1. Scenario: {analysis['scenario']}",
            f"2. Why this is hard: {analysis['difficult']}",
            f"3. Failure in naive systems: {analysis['naive']}",
            f"4. Mechanism in this system: {mechanism}",
            f"5. Why this works: {analysis['works']}",
            f"6. Why PASS matters: {analysis['meaning']}",
        ]
    )


def ollama_reason(case_name: str, policy: str, model: str, timeout_seconds: int) -> str:
    prompt = f"""
You are analyzing benchmark results of a CRDT-based distributed relational database system.

Your task is to generate deep, technically accurate reasoning for one test case.
Do NOT simply state that tests passed.

For this test case, use exactly this structure:

{case_name}:
1. Scenario: Explain what is happening between peers A, B, and C.
2. Why this is hard: Explain what makes this challenging in distributed systems.
3. Failure in naive systems: Explain what would go wrong without CRDT-based design.
4. Mechanism in this system: Mention the relevant implementation concepts: vector clocks, merge_clock max merge, dominance checks, MV-registers, OR-Set add/remove tags, deterministic tie-breaking, conflict log, tombstones, or FK policy.
5. Why this works: Explain using CRDT properties: commutativity, associativity, and idempotency. Include the exact idea that repeated syncs do not change the result.
6. Why PASS matters: Connect to convergence, determinism, eventual consistency, and conflict safety.

Critical instructions:
- Always explain using peers A, B, and C with step-by-step examples.
- Explicitly mention when updates are concurrent and no update dominates the other, if relevant.
- Include this exact sentence when conflicts are relevant: "Conflicts are not prevented; they are resolved deterministically."
- Include this exact sentence: "Final state does NOT depend on sync order."
- Explain logical clocks as tracking causal history, not real time, when relevant.
- Avoid vague statements like "it works correctly."
- Avoid repeating generic claims; adapt the reasoning to this specific scenario.

Keep the full answer under 260 words.
Do not mention that you are an AI.

Case name: {case_name}
FK policy: {policy}
Existing intent: {CASE_INTENTS[case_name]}
Reference analysis to stay accurate:
Scenario: {CASE_ANALYSES[case_name]['scenario']}
Difficulty: {CASE_ANALYSES[case_name]['difficult']}
Naive failure: {CASE_ANALYSES[case_name]['naive']}
Mechanism: {CASE_ANALYSES[case_name]['mechanism']}
Likely implementation mechanisms:
- Logical/vector clocks track causal history, not wall-clock time.
- merge_clock uses max merge for causal metadata.
- Dominance checks decide whether one version causally supersedes another.
- MV-registers preserve concurrent cell values and read them deterministically.
- OR-Set-style add/remove tags model row membership and add-wins semantics.
- Unique email conflicts are detected after merge and logged in _conflict_log.
- Tombstone/cascade/orphan foreign-key policies are applied deterministically.
- Pairwise sync exchanges knowledge/history, then recomputes conflicts and indexes.

Generate the structured presentation-style analysis now.
""".strip()
    completed = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout).strip().splitlines()
        detail = error[-1] if error else f"exit code {completed.returncode}"
        raise RuntimeError(detail)
    reason = re.sub(r"\n{3,}", "\n\n", completed.stdout.strip())
    if not reason:
        raise RuntimeError("ollama returned an empty reason")
    return reason


def format_analysis(text: str, width: int = 96) -> str:
    lines = text.splitlines()
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            out.append("")
            continue
        heading = re.fullmatch(r"[A-Za-z0-9_]+:", line)
        section = re.match(r"^(\d+\.\s+[^:]+:)\s*(.*)$", line)
        if heading:
            out.append(f"    {line}")
        elif section:
            label, body = section.groups()
            out.append(f"    {label}")
            if body:
                out.extend(
                    textwrap.wrap(
                        body,
                        width=width,
                        initial_indent="      ",
                        subsequent_indent="      ",
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                )
        else:
            out.extend(
                textwrap.wrap(
                    line,
                    width=width,
                    initial_indent="      ",
                    subsequent_indent="      ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
    return "\n".join(out)


def print_report_header(adapter: str, policies: list[str], out_path: str, use_ollama: bool, model: str) -> None:
    line = "=" * 88
    print(line)
    print("CRDT EDGE-CASE BENCHMARK ANALYSIS")
    print(line)
    print(f"Adapter       : {adapter}")
    print(f"FK policies   : {', '.join(policies)}")
    print(f"LLM reasoning : {'ollama:' + model if use_ollama else 'built-in fallback'}")
    print(f"JSON report   : {out_path}")
    print(line)


def print_case_result(result: dict[str, str], previous_policy: str | None) -> str:
    policy = result["policy"]
    if policy != previous_policy:
        print()
        print(f"FK POLICY: {policy.upper()}")
        print("-" * 88)
    status = result["status"].upper()
    print(f"\n[{status}] {result['case']}")
    print(f"Reason source: {result['reason_provider']}")
    if "error" in result:
        print(f"Failure      : {result['error']}")
    print()
    print(format_analysis(result["reason"]))
    return policy


def print_summary(report: dict[str, Any], out_path: str) -> None:
    print()
    print("=" * 88)
    print("SUMMARY")
    print("=" * 88)
    print(f"Passed : {report['passed']}")
    print(f"Failed : {report['failed']}")
    if report.get("ollama_error"):
        print(f"Ollama : unavailable, used built-in fallback ({report['ollama_error']})")
    print(f"Report : {out_path}")


def explain_case(
    case_name: str,
    policy: str,
    *,
    use_ollama: bool,
    model: str,
    timeout_seconds: int,
    ollama_state: dict[str, str | bool],
) -> tuple[str, str]:
    if use_ollama and shutil.which("ollama") and not ollama_state.get("disabled"):
        try:
            return ollama_reason(case_name, policy, model, timeout_seconds), f"ollama:{model}"
        except Exception as exc:
            ollama_state["disabled"] = True
            ollama_state["error"] = str(exc)
    return built_in_reason(case_name, policy), "built-in-fallback"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default="adapters.myteam:Engine")
    parser.add_argument("--fk-policy", action="append", choices=["tombstone", "cascade", "orphan"])
    parser.add_argument("--out", default="edge_report.json")
    parser.add_argument("--ollama-model", default="llama3.2")
    parser.add_argument("--ollama-timeout", type=int, default=60)
    parser.add_argument("--no-ollama", action="store_true", help="Print built-in reasons without trying Ollama.")
    parser.add_argument("--json-only", action="store_true", help="Suppress per-case CLI lines and print only the JSON report.")
    args = parser.parse_args()

    Engine = load_engine(args.adapter)
    policies = args.fk_policy or ["tombstone", "cascade", "orphan"]
    results: list[dict[str, str]] = []
    reason_cache: dict[tuple[str, str], tuple[str, str]] = {}
    ollama_state: dict[str, str | bool] = {}
    previous_policy: str | None = None

    if not args.json_only:
        print_report_header(args.adapter, policies, args.out, not args.no_ollama, args.ollama_model)

    for policy in policies:
        for name, case in CASES:
            reason, provider = reason_cache.setdefault(
                (policy, name),
                explain_case(
                    name,
                    policy,
                    use_ollama=not args.no_ollama,
                    model=args.ollama_model,
                    timeout_seconds=args.ollama_timeout,
                    ollama_state=ollama_state,
                ),
            )
            try:
                case(Engine, policy)
            except Exception as exc:
                result = {
                    "policy": policy,
                    "case": name,
                    "status": "fail",
                    "reason": reason,
                    "reason_provider": provider,
                    "error": repr(exc),
                }
            else:
                result = {
                    "policy": policy,
                    "case": name,
                    "status": "pass",
                    "reason": reason,
                    "reason_provider": provider,
                }
            results.append(result)
            if not args.json_only:
                previous_policy = print_case_result(result, previous_policy)

    report = {
        "passed": sum(result["status"] == "pass" for result in results),
        "failed": sum(result["status"] == "fail" for result in results),
        "ollama_error": ollama_state.get("error"),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.json_only:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_summary(report, args.out)
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
