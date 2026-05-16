from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
L3_RUNNER = ROOT / "Anvil-P-E" / "bench-p01-crdt" / "run.py"


ESSENTIAL_PROTOCOLS = [
    "OR-Set row membership with add/remove tags",
    "Per-cell MV-registers for independent column merges",
    "Vector-clock max merge with dominance checks",
    "Post-merge uniqueness grouping with deterministic arbitration",
    "Conflict log for recoverable uniqueness losers",
    "Tombstone FK policy with chain repair after writes/imports",
    "Idempotent pairwise sync and deterministic snapshot hashing",
]


SCENARIO_GUIDE: dict[str, dict[str, str]] = {
    "reference": {
        "scenario": "Duplicate users, a parent delete, an order pointing at that deleted user, and concurrent column updates are merged across three peers.",
        "risk": "This mixes uniqueness, FK policy, tombstones, and cell-level updates in one trace.",
        "mechanism": "Rows merge through OR-Set add/remove tags; cells merge through MV-register clocks. Email collisions are grouped after merge and resolved by deterministic arbitration, while the order remains attached to the tombstoned user.",
        "causal": "Concurrent cell writes have no dominance relationship, so name and email changes are preserved independently before visible values are chosen.",
    },
    "cell-level-strict": {
        "scenario": "Two peers update different columns of the same observed row while offline.",
        "risk": "A row-level last-writer-wins merge would keep one update and erase the other.",
        "mechanism": "Each column has its own MV-register, so the name write and email write merge separately instead of competing at row granularity.",
        "causal": "Because the column writes are concurrent, neither clock dominates the other; dominance is checked per cell, preserving both updates.",
    },
    "chaos": {
        "scenario": "The reference trace is replayed, but final sync pairs are shuffled by seed.",
        "risk": "Order-sensitive metadata can make peers converge per seed but produce different hashes across seeds.",
        "mechanism": "Merge uses max vector-clock entries, add/remove tag union, and recomputes conflicts from the merged state instead of from sync history.",
        "causal": "Canonical snapshot hashing ignores benchmark-scoped peer labels, so equivalent causal histories compare the same across sync permutations.",
    },
    "randomized": {
        "scenario": "Generated inserts, updates, deletes, and syncs are interleaved across multiple peers.",
        "risk": "Random orderings expose silent row loss, duplicate email survival, and non-idempotent second syncs.",
        "mechanism": "Every inserted row is tracked through OR-Set membership. Email collisions are grouped post-merge; losers stay recoverable through conflict records instead of disappearing.",
        "causal": "Repeated syncs merge the same causal dots and registers, so the second pass should leave the snapshot unchanged.",
    },
    "stretch:composite_uniqueness": {
        "scenario": "Peers insert memberships that collide on `(user_id, team_id)` while offline.",
        "risk": "Single-column uniqueness logic can miss tuple collisions or drop losing rows.",
        "mechanism": "The merged state is grouped by the full composite key. One deterministic winner remains on the original tuple; losers are retained with conflict-safe rewritten unique values and logged original data.",
        "causal": "Winner selection is based on row clocks and stable tie-breaks, so all peers choose the same row after exchanging histories.",
    },
    "stretch:multi_level_fk": {
        "scenario": "An organization root is deleted while users and orders beneath it are created or learned on other peers.",
        "risk": "FK handling can stop after one level, leaving users or orders pointing at deleted parents.",
        "mechanism": "After every write/import, FK repair walks declared references and applies the tombstone policy through the full organization -> users -> orders chain.",
        "causal": "Repair only reacts to known deletes or tombstones, so a child is not removed merely because its parent has not synced in yet.",
    },
    "stretch:high_density": {
        "scenario": "Six peers insert the same email concurrently, alongside non-conflicting users.",
        "risk": "A replace-style implementation may satisfy uniqueness by silently deleting most inserts.",
        "mechanism": "Post-merge grouping by email selects one deterministic winner. The other inserts remain present under conflict-safe email values, with original emails stored in the conflict log.",
        "causal": "All inserts are concurrent, so arbitration uses stable clocks/tie-breaks rather than arrival order.",
    },
    "stretch:long_run": {
        "scenario": "A longer randomized workload mixes collisions, deletes, updates, and many sync rounds.",
        "risk": "Rare interleavings can reveal metadata drift, non-idempotent sync, or conflict rows being lost.",
        "mechanism": "Bounded vector clocks, OR-Set rows, per-cell MV-registers, and deterministic uniqueness repair are applied repeatedly after sync.",
        "causal": "Dominated cell versions are compacted, while concurrent versions remain available for deterministic reads and conflict repair.",
    },
}


def base_scenario(name: str) -> str:
    if name.startswith("chaos:"):
        return "chaos"
    if name.startswith("randomized:"):
        return "randomized"
    if name.startswith("stretch:long_run"):
        return "stretch:long_run"
    return name


def run_l3(args: argparse.Namespace) -> tuple[dict[str, Any] | None, str, str, int]:
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(L3_RUNNER),
        "--adapter",
        args.adapter,
        "--fk-policy",
        args.fk_policy,
        "--out",
        str(out_path),
    ]
    if args.smoke:
        cmd += [
            "--chaos-seeds",
            "1",
            "--randomized-seeds",
            "101",
            "--long-run-seeds",
            "31415",
            "--long-run-ops",
            str(args.smoke_long_run_ops),
        ]
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = None
    if out_path.exists():
        report = json.loads(out_path.read_text(encoding="utf-8"))
    return report, completed.stdout, completed.stderr, completed.returncode


def assertion_summary(scenario: dict[str, Any]) -> str:
    assertions = scenario.get("assertions", [])
    passed = [item["name"] for item in assertions if item.get("passed")]
    failed = [item["name"] for item in assertions if not item.get("passed")]
    chunks = []
    if passed:
        chunks.append(f"passed assertions: {', '.join(passed)}")
    if failed:
        chunks.append(f"failed assertions: {', '.join(failed)}")
    return "; ".join(chunks) if chunks else "no assertions reported"


def assertion_badge(scenario: dict[str, Any]) -> str:
    failed = [item["name"] for item in scenario.get("assertions", []) if not item.get("passed")]
    if failed:
        return "failed: " + ", ".join(failed)
    passed = [item["name"] for item in scenario.get("assertions", []) if item.get("passed")]
    return "passed: " + ", ".join(passed)


def built_in_analysis(scenario: dict[str, Any]) -> str:
    name = scenario["scenario"]
    guide = SCENARIO_GUIDE.get(base_scenario(name), SCENARIO_GUIDE["reference"])
    return "\n".join(
        [
            f"{name}:",
            f"- Case: {guide['scenario']}",
            f"- Risk: {guide['risk']}",
            f"- Mechanism: {guide['mechanism']}",
            f"- Causal note: {guide['causal']}",
            f"- Result: {assertion_badge(scenario)}",
        ]
    )


def ollama_analysis(scenario: dict[str, Any], model: str, timeout: int) -> str:
    name = scenario["scenario"]
    guide = SCENARIO_GUIDE.get(base_scenario(name), SCENARIO_GUIDE["reference"])
    prompt = f"""
You are analyzing a CRDT distributed relational database benchmark scenario.
Do not merely restate pass/fail. Generate a compact end-user friendly explanation.

Use exactly this structure:

{name}:
- Case: one short sentence on what peers do.
- Risk: one short sentence on the failure this scenario catches.
- Mechanism: one scenario-specific sentence. Tie the mechanism directly to this case.
- Causal note: one short sentence explaining why clocks/dominance matter here.
- Result: summarize pass/fail assertions in one short sentence.

Style rules:
- Keep the whole answer under 120 words.
- Use bullets exactly as shown. No long paragraphs.
- Do not repeat generic phrases like "commutative, associative, and idempotent" unless absolutely necessary.
- For uniqueness, mention post-merge grouping and deterministic winner selection.
- For FK, mention propagation/repair through the declared FK chain.
- For concurrent cell updates, mention no dominance and preserving both writes.
- For randomized/chaos, mention interleaving coverage or sync-order independence.

Scenario name: {name}
Case: {guide['scenario']}
Risk: {guide['risk']}
Mechanism: {guide['mechanism']}
Causal note: {guide['causal']}
Assertions: {assertion_summary(scenario)}
""".strip()
    completed = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        lines = (completed.stderr or completed.stdout).strip().splitlines()
        raise RuntimeError(lines[-1] if lines else f"exit code {completed.returncode}")
    output = re.sub(r"\n{3,}", "\n\n", completed.stdout.strip())
    if not output:
        raise RuntimeError("ollama returned an empty analysis")
    return output


def explain(
    scenario: dict[str, Any],
    *,
    use_ollama: bool,
    model: str,
    timeout: int,
    state: dict[str, str | bool],
) -> tuple[str, str]:
    if use_ollama and shutil.which("ollama") and not state.get("disabled"):
        try:
            return ollama_analysis(scenario, model, timeout), f"ollama:{model}"
        except Exception as exc:
            state["disabled"] = True
            state["error"] = str(exc)
    return built_in_analysis(scenario), "built-in-fallback"


def format_block(text: str, width: int = 96) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            out.append("")
            continue
        section = re.match(r"^(\d+\.\s+[^:]+:)\s*(.*)$", line)
        bullet = re.match(r"^-\s+([^:]+):\s*(.*)$", line)
        if re.fullmatch(r".+:", line) and not section:
            out.append(f"    {line}")
        elif bullet:
            label, body = bullet.groups()
            prefix = f"    - {label}: "
            wrapped = textwrap.wrap(
                body,
                width=width,
                initial_indent=prefix,
                subsequent_indent=" " * len(prefix),
                break_long_words=False,
                break_on_hyphens=False,
            )
            out.extend(wrapped or [prefix.rstrip()])
        elif section:
            label, body = section.groups()
            out.append(f"    {label}")
            if body:
                out.extend(textwrap.wrap(body, width=width, initial_indent="      ", subsequent_indent="      ", break_long_words=False, break_on_hyphens=False))
        else:
            out.extend(textwrap.wrap(line, width=width, initial_indent="      ", subsequent_indent="      ", break_long_words=False, break_on_hyphens=False))
    return "\n".join(out)


def print_header(args: argparse.Namespace) -> None:
    line = "=" * 88
    print(line)
    print("ANVIL P-01 L3 BENCHMARK ANALYSIS")
    print(line)
    print(f"Benchmark     : {L3_RUNNER.relative_to(ROOT)}")
    print(f"Adapter       : {args.adapter}")
    print(f"FK policy     : {args.fk_policy}")
    print(f"Mode          : {'smoke' if args.smoke else 'full L3'}")
    print(f"LLM reasoning : {'ollama:' + args.ollama_model if not args.no_ollama else 'built-in fallback'}")
    print(f"L3 report     : {args.out}")
    print(f"Analysis JSON : {args.analysis_out}")
    print(line)


def print_summary(
    report: dict[str, Any],
    results: list[dict[str, Any]],
    args: argparse.Namespace,
    analysis_report: dict[str, Any],
) -> None:
    final = report.get("l3_final_score", {})
    core_axes = report.get("core_score", {}).get("axes", {})
    stretch_axes = report.get("stretch_score", {}).get("axes", {})
    pass_count = sum(r["status"] == "pass" for r in results)
    fail_count = sum(r["status"] == "fail" for r in results)

    print()
    print("=" * 88)
    print("SUMMARY")
    print("=" * 88)
    print(f"L3 score : {final.get('value')} / {final.get('max')}")
    print(f"Scenarios: {pass_count} pass, {fail_count} fail")
    print(f"Mode     : {'smoke' if args.smoke else 'full L3'}")
    print(f"FK policy: {args.fk_policy}")
    print()
    print("Essential protocols used:")
    for protocol in ESSENTIAL_PROTOCOLS:
        print(f"  - {protocol}")
    print()
    print("Essential checks:")
    for name, passed in {**core_axes, **stretch_axes}.items():
        print(f"  - {name}: {'pass' if passed else 'fail'}")
    if analysis_report.get("ollama_error"):
        print()
        print(f"Ollama   : unavailable, used built-in fallback ({analysis_report['ollama_error']})")
    print()
    print(f"Report   : {args.out}")
    print(f"Analysis : {args.analysis_out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default="benchmarks.l3_adapter:Engine")
    parser.add_argument("--fk-policy", choices=["tombstone", "cascade", "orphan"], default="tombstone")
    parser.add_argument("--out", default="benchmarks/l3_report.json")
    parser.add_argument("--analysis-out", default="benchmarks/l3_analysis_report.json")
    parser.add_argument("--smoke", action="store_true", help="Use reduced seed lists and a shorter long-run for quick local validation.")
    parser.add_argument("--smoke-long-run-ops", type=int, default=50)
    parser.add_argument("--ollama-model", default="llama3.2")
    parser.add_argument("--ollama-timeout", type=int, default=60)
    parser.add_argument("--no-ollama", action="store_true")
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--strict-exit", action="store_true", help="Exit with the underlying L3 benchmark code when the score is below its threshold.")
    args = parser.parse_args()

    if not args.json_only:
        print_header(args)

    report, stdout, stderr, returncode = run_l3(args)
    if report is None:
        raise SystemExit(f"L3 benchmark did not produce {args.out}\n{stderr}")

    ollama_state: dict[str, str | bool] = {}
    results = []
    for scenario in report.get("scenarios", []):
        reason, provider = explain(
            scenario,
            use_ollama=not args.no_ollama,
            model=args.ollama_model,
            timeout=args.ollama_timeout,
            state=ollama_state,
        )
        failed_assertions = [item["name"] for item in scenario.get("assertions", []) if not item.get("passed")]
        status = "pass" if not failed_assertions else "fail"
        item = {
            "scenario": scenario["scenario"],
            "status": status,
            "failed_assertions": failed_assertions,
            "reason": reason,
            "reason_provider": provider,
        }
        results.append(item)

    analysis_report = {
        "l3_final_score": report.get("l3_final_score"),
        "core_score": report.get("core_score"),
        "stretch_score": report.get("stretch_score"),
        "benchmark_returncode": returncode,
        "essential_protocols": ESSENTIAL_PROTOCOLS,
        "ollama_error": ollama_state.get("error"),
        "results": results,
    }
    out_path = ROOT / args.analysis_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(analysis_report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json_only:
        print(json.dumps(analysis_report, indent=2, sort_keys=True))
    else:
        print_summary(report, results, args, analysis_report)
        print()
        print("=" * 88)
        print("LLM Justification")
        print("=" * 88)
        displayed_analysis: dict[str, str] = {}
        scenarios_by_name = {scenario["scenario"]: scenario for scenario in report.get("scenarios", [])}
        for item in results:
            scenario = scenarios_by_name[item["scenario"]]
            scenario_base = base_scenario(item["scenario"])
            repeat_of = displayed_analysis.get(scenario_base)
            print()
            print(f"[{item['status'].upper()}] {item['scenario']}")
            print(f"Assertions   : {assertion_summary(scenario)}")
            if repeat_of and item["status"] == "pass":
                print(f"Analysis     : same case family as {repeat_of}; details kept in JSON")
                print(format_block(f"- Result: {assertion_badge(scenario)}"))
            else:
                print(f"Analysis     : {item['reason_provider']}")
                print(format_block(item["reason"]))
                displayed_analysis[scenario_base] = item["scenario"]

    if args.strict_exit and returncode != 0:
        raise SystemExit(returncode)


if __name__ == "__main__":
    main()
