from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"


TESTS = [
    "five peers keep clock metadata bounded by writer count",
    "reference scenario converges with tombstone FK policy",
    "vector clock increment, merge, dominance, concurrency",
    "unique email loser is recoverable in conflict log",
    "MV-register keeps concurrent versions and drops dominated versions",
    "OR-set is add-wins for concurrent add and remove",
    "sync is idempotent",
]


ANALYSES: dict[str, dict[str, str]] = {
    "five peers keep clock metadata bounded by writer count": {
        "scenario": "Peers A, B, C, D, and E all write users, then sync in a chain so each peer gradually learns the others' histories.",
        "hard": "Distributed metadata can grow without bound if every sync stores redundant history instead of compact causal summaries.",
        "naive": "A naive implementation could attach every operation history to every value, causing metadata bloat and eventually making sync impractical.",
        "mechanism": "Vector-clock-style metadata stores one counter per writer; merge_clock uses max merge so each peer keeps the latest known count per writer.",
        "works": "Max merge is commutative, associative, and idempotent: A syncing before C or after C produces the same per-writer maxima, and repeated sync does not add duplicate clock entries. Final state does NOT depend on sync order.",
        "matters": "This protects convergence without unbounded metadata growth, which matters for real offline-first systems with many devices.",
    },
    "reference scenario converges with tombstone FK policy": {
        "scenario": "Peer A creates users and an order, peer B creates a duplicate email and updates Alice, and peer C deletes Alice after partial sync.",
        "hard": "This mixes concurrency, uniqueness, deletes, foreign keys, and multi-peer sync, so several invariants can interact badly.",
        "naive": "Replicas could pick different Alice rows, lose the order, disagree about the deleted user, or produce different snapshot hashes.",
        "mechanism": "OR-Set row tags model membership, MV-registers hold cell values, deterministic uniqueness arbitration records losers, and tombstones preserve deleted parent metadata.",
        "works": "Pairwise sync exchanges causal history; tag union, merge_clock max merge, and MV-register dominance checks are order-independent and idempotent. Conflicts are not prevented; they are resolved deterministically. Final state does NOT depend on sync order.",
        "matters": "This demonstrates end-to-end eventual consistency for a relational workload instead of only isolated CRDT primitives.",
    },
    "vector clock increment, merge, dominance, concurrency": {
        "scenario": "Peer A increments its logical clock twice, peer B increments independently, and the test compares merge, dominance, and concurrency.",
        "hard": "Distributed peers cannot rely on wall-clock time to decide causality because clocks drift and offline writes happen independently.",
        "naive": "Using timestamps could falsely order concurrent writes or let two replicas disagree about which write happened first.",
        "mechanism": "Logical/vector clocks track causal history, not real time. merge_clock takes the max counter per peer, dominance detects causal supersession, and concurrency detects no dominance.",
        "works": "Max merge is commutative, associative, and idempotent: merging A then B or B then A yields the same causal summary, and merging the same clock twice changes nothing.",
        "matters": "This is the base invariant that lets later MV-register, OR-Set, and conflict-resolution logic decide whether updates are newer or concurrent.",
    },
    "unique email loser is recoverable in conflict log": {
        "scenario": "Peer A creates Alice with one row id while peer B independently creates Alice Prime with the same email, then A and B sync.",
        "hard": "A unique constraint cannot be globally enforced while devices are offline and unable to coordinate before accepting writes.",
        "naive": "Both rows might remain live, different peers might choose different winners, or the losing row might be silently deleted.",
        "mechanism": "After merge, the engine groups rows by unique email, applies deterministic tie-breaking, keeps one winner, and stores losing row data in _conflict_log.",
        "works": "Once A, B, and C have the same candidate set, deterministic arbitration gives the same winner everywhere. Conflicts are not prevented; they are resolved deterministically. Final state does NOT depend on sync order.",
        "matters": "This preserves the database uniqueness invariant without losing user data, which is essential for conflict-safe offline creation.",
    },
    "MV-register keeps concurrent versions and drops dominated versions": {
        "scenario": "Peer A writes Alice, peer B concurrently writes Alice Prime, then a later A write observes both and writes Alice Cooper.",
        "hard": "The system must distinguish true concurrency from a later update that causally supersedes older values.",
        "naive": "Last-write-wins could discard a concurrent value incorrectly, while keeping all versions forever would expose stale conflicts after resolution.",
        "mechanism": "The MV-register keeps versions when neither vector clock dominates the other, and drops versions dominated by a later causal clock.",
        "works": "Version merge is commutative and associative because it computes the same non-dominated set regardless of order; it is idempotent because duplicate versions collapse to the same version key. Final state does NOT depend on sync order.",
        "matters": "This gives deterministic conflict handling for cell values while allowing later causally-aware writes to cleanly resolve prior concurrency.",
    },
    "OR-set is add-wins for concurrent add and remove": {
        "scenario": "Peer A adds row u1, peer B observes and removes that add tag, then peer A creates a new add tag before the states merge.",
        "hard": "Deletes should remove what they observed, but they must not erase a concurrent or later add they did not observe.",
        "naive": "A broad delete marker could permanently remove u1, causing data loss when A had legitimately re-added it.",
        "mechanism": "The OR-Set stores add tags and remove tags separately; remove only covers observed add tags, while the new add tag remains uncovered.",
        "works": "Union of add/remove tags is commutative, associative, and idempotent. Replaying the same remove tag changes nothing, and the uncovered add tag keeps the row present. Final state does NOT depend on sync order.",
        "matters": "This guarantees add-wins semantics, protecting offline inserts or recreations from uninformed deletes.",
    },
    "sync is idempotent": {
        "scenario": "Peer A inserts a user, syncs with peer B, then A and B run the same sync again.",
        "hard": "Network protocols retry. A distributed database must tolerate duplicate delivery without creating duplicate state.",
        "naive": "Repeated sync could duplicate rows, add duplicate versions, mutate hashes, or cause peers to drift after retries.",
        "mechanism": "sync exports/imports state, merge_clock takes max counters, OR-Set tags union, and MV-register versions are de-duplicated by stable version identity.",
        "works": "The merge operations are idempotent: applying the same knowledge twice has the same effect as applying it once. They are also commutative and associative, so retries and pairwise sync order do not change the final state.",
        "matters": "This is fundamental for eventual consistency because real sync channels rarely guarantee exactly-once delivery.",
    },
}


def run_node_tests() -> tuple[set[str], str, str, int]:
    completed = subprocess.run(
        ["npm", "test"],
        cwd=ENGINE,
        text=True,
        capture_output=True,
        check=False,
    )
    passed = set(re.findall(r"^✔ (.+?) \(", completed.stdout, flags=re.MULTILINE))
    return passed, completed.stdout, completed.stderr, completed.returncode


def built_in_analysis(test_name: str) -> str:
    analysis = ANALYSES[test_name]
    return "\n".join(
        [
            f"{test_name}:",
            f"1. Scenario: {analysis['scenario']}",
            f"2. Why this is hard: {analysis['hard']}",
            f"3. Failure in naive systems: {analysis['naive']}",
            f"4. Mechanism in this system: {analysis['mechanism']}",
            f"5. Why this works: {analysis['works']}",
            f"6. Why PASS matters: {analysis['matters']}",
        ]
    )


def ollama_analysis(test_name: str, model: str, timeout_seconds: int) -> str:
    analysis = ANALYSES[test_name]
    prompt = f"""
You are analyzing benchmark results of a CRDT-based distributed relational database system.
Generate deep, technically accurate reasoning for one Node engine test.

Use exactly this structure:

{test_name}:
1. Scenario: Explain what is happening between peers A, B, and C.
2. Why this is hard: Explain what makes this challenging in distributed systems.
3. Failure in naive systems: Explain what would go wrong without CRDT-based design.
4. Mechanism in this system: Mention relevant concepts: vector clocks, merge_clock max merge, dominance checks, MV-registers, OR-Set add/remove tags, deterministic tie-breaking, conflict log, tombstones, or sync idempotency.
5. Why this works: Explain using commutativity, associativity, and idempotency. Include why repeated syncs do not change the result when relevant.
6. Why PASS matters: Connect to convergence, determinism, eventual consistency, and conflict safety.

Critical instructions:
- Do not simply say the test passed.
- Use peers A, B, and C in the explanation.
- Explicitly mention concurrent updates and no dominance when relevant.
- Include this exact sentence when conflicts are relevant: "Conflicts are not prevented; they are resolved deterministically."
- Include this exact sentence: "Final state does NOT depend on sync order."
- Explain logical clocks as tracking causal history, not real time, when relevant.
- Keep the answer under 260 words.
- Do not mention that you are an AI.

Test name: {test_name}
Reference scenario: {analysis['scenario']}
Reference difficulty: {analysis['hard']}
Reference mechanism: {analysis['mechanism']}
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
        raise RuntimeError(error[-1] if error else f"exit code {completed.returncode}")
    output = re.sub(r"\n{3,}", "\n\n", completed.stdout.strip())
    if not output:
        raise RuntimeError("ollama returned an empty analysis")
    return output


def explain_test(
    test_name: str,
    *,
    use_ollama: bool,
    model: str,
    timeout_seconds: int,
    ollama_state: dict[str, str | bool],
) -> tuple[str, str]:
    if use_ollama and shutil.which("ollama") and not ollama_state.get("disabled"):
        try:
            return ollama_analysis(test_name, model, timeout_seconds), f"ollama:{model}"
        except Exception as exc:
            ollama_state["disabled"] = True
            ollama_state["error"] = str(exc)
    return built_in_analysis(test_name), "built-in-fallback"


def format_analysis(text: str, width: int = 96) -> str:
    lines = text.splitlines()
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            out.append("")
            continue
        heading = re.fullmatch(r".+:", line)
        section = re.match(r"^(\d+\.\s+[^:]+:)\s*(.*)$", line)
        if heading and not section:
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


def print_header(model: str, out_path: str, use_ollama: bool) -> None:
    line = "=" * 88
    print(line)
    print("CRDT ENGINE TEST ANALYSIS")
    print(line)
    print("Command       : npm test")
    print(f"LLM reasoning : {'ollama:' + model if use_ollama else 'built-in fallback'}")
    print(f"JSON report   : {out_path}")
    print(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="engine_test_report.json")
    parser.add_argument("--ollama-model", default="llama3.2")
    parser.add_argument("--ollama-timeout", type=int, default=60)
    parser.add_argument("--no-ollama", action="store_true")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    passed_names, stdout, stderr, returncode = run_node_tests()
    ollama_state: dict[str, str | bool] = {}
    results: list[dict[str, str]] = []

    if not args.json_only:
        print_header(args.ollama_model, args.out, not args.no_ollama)

    for test_name in TESTS:
        status = "pass" if test_name in passed_names and returncode == 0 else "fail"
        reason, provider = explain_test(
            test_name,
            use_ollama=not args.no_ollama,
            model=args.ollama_model,
            timeout_seconds=args.ollama_timeout,
            ollama_state=ollama_state,
        )
        result = {
            "test": test_name,
            "status": status,
            "reason": reason,
            "reason_provider": provider,
        }
        results.append(result)
        if not args.json_only:
            print()
            print(f"[{status.upper()}] {test_name}")
            print(f"Reason source: {provider}")
            print()
            print(format_analysis(reason))

    report: dict[str, Any] = {
        "passed": sum(result["status"] == "pass" for result in results),
        "failed": sum(result["status"] == "fail" for result in results),
        "ollama_error": ollama_state.get("error"),
        "node_returncode": returncode,
        "results": results,
    }
    if returncode != 0:
        report["node_stdout"] = stdout
        report["node_stderr"] = stderr

    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json_only:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print()
        print("=" * 88)
        print("SUMMARY")
        print("=" * 88)
        print(f"Passed : {report['passed']}")
        print(f"Failed : {report['failed']}")
        if report.get("ollama_error"):
            print(f"Ollama : unavailable, used built-in fallback ({report['ollama_error']})")
        print(f"Report : {args.out}")

    if returncode != 0 or report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
