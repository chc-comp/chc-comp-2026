#!/usr/bin/env python3
"""
Majority-vote relabeling of CHC-COMP benchmark verdicts.

Reads all solver result XML files, collects verdicts per benchmark,
computes a majority vote, and:
  1. Updates the .yml task definition files with the new verdict.
  2. Updates expectedVerdict attributes and recomputes category columns
     in all BenchExec result XML files in the data directory.
Adds YAML comments documenting which solvers support or oppose the verdict.

Usage:
    python3 majority-vote-relabel.py <benchmarks_dir> <data_dir> [--dry-run]

Example:
    python3 majority-vote-relabel.py \\
        chc-comp26-benchmarks \\
        results
"""

import argparse
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
import yaml
from collections import defaultdict


# Pattern matching plain solver result files (not model-gen, validator, or fixed)
_PLAIN_RESULT_RE = re.compile(
    r'^([a-z0-9]+)\.\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}'
    r'\.results\.CHC-COMP2025_check-sat(?:\.([^.]+))?\.xml$'
)


def discover_solver_files(data_dir):
    """Auto-discover plain solver result XML files from data_dir.
    Returns {solver_name: [filepath, ...]}.
    For each solver, the aggregate file (no category suffix) is preferred;
    if no aggregate exists, all per-category files are used.
    """
    aggregate = {}   # {solver: path}
    per_cat = {}     # {solver: [path, ...]}
    for fname in sorted(os.listdir(data_dir)):
        m = _PLAIN_RESULT_RE.match(fname)
        if not m:
            continue
        solver, cat = m.group(1), m.group(2)
        fpath = os.path.join(data_dir, fname)
        if cat is None:
            aggregate[solver] = fpath
        else:
            per_cat.setdefault(solver, []).append(fpath)
    result = {}
    for solver in set(aggregate) | set(per_cat):
        if solver in aggregate:
            result[solver] = [aggregate[solver]]
        else:
            result[solver] = per_cat[solver]
    return result

BENCH_PREFIX_MARKER = "chc-comp25-benchmarks/"


def normalize_bench_path(name):
    """Extract the benchmark-relative path from an XML run name attribute.
    E.g. '../../../chc-comp25-benchmarks/foo/bar.yml' -> 'foo/bar.yml'
    """
    idx = name.find(BENCH_PREFIX_MARKER)
    if idx >= 0:
        return name[idx + len(BENCH_PREFIX_MARKER):]
    return name


def parse_result_xml(filepath):
    """Parse a BenchExec XML result file, returning {benchmark_path: verdict}."""
    results = {}
    tree = ET.parse(filepath)
    for run in tree.getroot().iter("run"):
        bench = normalize_bench_path(run.get("name", ""))
        status = None
        for col in run.findall("column"):
            if col.get("title") == "status":
                status = col.get("value")
                break
        if status in ("true", "false"):
            results[bench] = status
    return results


def collect_all_verdicts(data_dir):
    """Collect verdicts from all auto-discovered plain solver result files.
    Returns: {benchmark_path: {solver_name: verdict}}
    """
    solver_files = discover_solver_files(data_dir)
    all_verdicts = defaultdict(dict)
    for solver, filepaths in solver_files.items():
        for filepath in filepaths:
            results = parse_result_xml(filepath)
            for bench, verdict in results.items():
                all_verdicts[bench][solver] = verdict
    return all_verdicts


def update_xml_files(data_dir, computed_verdicts, dry_run=False):
    """Update expectedVerdict attributes and recompute category columns in all
    BenchExec result XML files directly inside data_dir.

    computed_verdicts: {benchmark_path: verdict} where verdict is
        "true", "false", or "inconsistent".
    """
    files_updated = 0
    runs_changed = 0

    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".xml"):
            continue
        filepath = os.path.join(data_dir, fname)

        with open(filepath, "rb") as f:
            original_bytes = f.read()

        tree = ET.parse(filepath)
        root = tree.getroot()
        if root.tag != "result":
            continue

        file_changed = 0
        for run in root.iter("run"):
            bench = normalize_bench_path(run.get("name", ""))
            if bench not in computed_verdicts:
                continue

            new_verdict = computed_verdicts[bench]  # "true", "false", or "inconsistent"
            old_expected = run.get("expectedVerdict")  # "true", "false", or None
            new_expected = new_verdict if new_verdict in ("true", "false") else None

            if old_expected == new_expected:
                continue

            # Update expectedVerdict attribute
            if new_expected is None:
                run.attrib.pop("expectedVerdict", None)
            else:
                run.set("expectedVerdict", new_expected)

            # Recompute category for definite solver answers (true/false)
            status = None
            cat_col = None
            for col in run.findall("column"):
                t = col.get("title")
                if t == "status":
                    status = col.get("value")
                elif t == "category":
                    cat_col = col

            if cat_col is not None and status in ("true", "false"):
                if new_expected is None:
                    new_cat = "unknown"
                elif status == new_expected:
                    new_cat = "correct"
                else:
                    new_cat = "wrong"
                cat_col.set("value", new_cat)

            file_changed += 1
            runs_changed += 1

        if file_changed == 0:
            continue

        files_updated += 1
        if dry_run:
            print(f"  Would update {fname} ({file_changed} runs)")
        else:
            # Preserve the original preamble (XML declaration + DOCTYPE)
            preamble_end = original_bytes.find(b"<result")
            preamble = original_bytes[:preamble_end] if preamble_end > 0 else b""

            buf = io.BytesIO()
            tree.write(buf, encoding="utf-8", xml_declaration=(not preamble))
            body = buf.getvalue()
            # Strip ET's own XML declaration when we have the original preamble
            if preamble and body.startswith(b"<?xml"):
                nl = body.find(b"\n")
                body = body[nl + 1:] if nl >= 0 else body[body.find(b"?>") + 2:]

            with open(filepath, "wb") as f:
                f.write(preamble + body)
            print(f"  Updated {fname} ({file_changed} runs changed)")

    summary = f"{files_updated} XML files, {runs_changed} run entries"
    if dry_run:
        print(f"  [dry-run] Would update {summary}")
    else:
        print(f"  Updated {summary}")
    return files_updated, runs_changed


def majority_vote(solver_verdicts):
    """Given {solver: verdict}, compute majority vote.
    Returns (verdict, supporters, opposers) or (None, [], []) if no data.
    verdict is "true", "false", or "inconsistent".
    """
    if not solver_verdicts:
        return None, [], []

    true_solvers = [s for s, v in solver_verdicts.items() if v == "true"]
    false_solvers = [s for s, v in solver_verdicts.items() if v == "false"]

    n_true = len(true_solvers)
    n_false = len(false_solvers)

    if n_true > 0 and n_false > 0:
        # Disagreement: majority wins, but mark as inconsistent if tied
        if n_true > n_false:
            return "true", true_solvers, false_solvers
        elif n_false > n_true:
            return "false", false_solvers, true_solvers
        else:
            return "inconsistent", true_solvers, false_solvers
    elif n_true > 0:
        return "true", true_solvers, []
    elif n_false > 0:
        return "false", false_solvers, []
    else:
        return None, [], []


def write_yml(yml_path, data, verdict, sat_solvers, unsat_solvers):
    """Write the YAML file with majority-vote verdict and solver lists as YAML entries."""
    mv_verdict = "sat" if verdict == "true" else ("unsat" if verdict == "false" else verdict)
    for prop in data.get("properties", []):
        if prop.get("property_file", "").endswith("properties/check-sat.prp"):
            prop["majority_vote_verdict"] = mv_verdict
            if sat_solvers:
                prop["sat"] = sorted(sat_solvers)
            else:
                prop.pop("sat", None)
            if unsat_solvers:
                prop["unsat"] = sorted(unsat_solvers)
            else:
                prop.pop("unsat", None)
            break
    with open(yml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def load_benchmark_categories(benchmarks_dir):
    """Build benchmark -> category mapping from .set files."""
    categories = [
        "ADT-LIA-Arrays", "ADT-LIA", "BV", "LIA-Arrays",
        "LIA-Lin-Arrays", "LIA-Lin", "LIA", "LRA-Lin",
    ]
    bench_to_cat = {}
    cat_sizes = {}
    for cat in categories:
        set_file = os.path.join(benchmarks_dir, cat + ".set")
        if not os.path.exists(set_file):
            continue
        with open(set_file) as f:
            benches = [line.strip() for line in f if line.strip()]
        cat_sizes[cat] = len(benches)
        for bench in benches:
            bench_to_cat[bench] = cat
    return categories, bench_to_cat, cat_sizes


def compute_verdict_counts(all_verdicts, bench_to_cat, categories):
    """Compute verdict distribution per category from raw solver votes."""
    counts = {c: {"true": 0, "false": 0, "inconsistent": 0, "unknown": 0} for c in categories}
    for bench, cat in bench_to_cat.items():
        verdict, _, _ = majority_vote(all_verdicts.get(bench, {}))
        if verdict == "true":
            counts[cat]["true"] += 1
        elif verdict == "false":
            counts[cat]["false"] += 1
        elif verdict == "inconsistent":
            counts[cat]["inconsistent"] += 1
        else:
            counts[cat]["unknown"] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description="Majority-vote relabeling of CHC-COMP benchmarks")
    parser.add_argument("benchmarks_dir", help="Path to chc-comp25-benchmarks directory")
    parser.add_argument("data_dir", help="Directory containing solver result XML files")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files")
    args = parser.parse_args()

    benchmarks_dir = args.benchmarks_dir
    results_dir = args.data_dir
    categories, bench_to_cat, cat_sizes = load_benchmark_categories(benchmarks_dir)

    print("Collecting verdicts from all solver result files...")
    all_verdicts = collect_all_verdicts(results_dir)
    print(f"Found verdicts for {len(all_verdicts)} benchmarks from {len(discover_solver_files(results_dir))} solvers.")

    # Pre-compute all majority verdicts (used for both .yml and XML updates)
    computed_verdicts = {}
    for bench, solver_verdicts in all_verdicts.items():
        verdict, _, _ = majority_vote(solver_verdicts)
        if verdict is not None:
            computed_verdicts[bench] = verdict

    stats = {"updated": 0, "added": 0, "unchanged": 0, "inconsistent": 0,
             "no_data": 0, "missing_yml": 0}

    for bench, solver_verdicts in sorted(all_verdicts.items()):
        yml_path = os.path.join(benchmarks_dir, bench)
        if not os.path.exists(yml_path):
            stats["missing_yml"] += 1
            continue

        verdict = computed_verdicts.get(bench)
        if verdict is None:
            stats["no_data"] += 1
            continue

        _, supporters, opposers = majority_vote(solver_verdicts)
        if verdict in ("true", "inconsistent"):
            sat_solvers, unsat_solvers = supporters, opposers
        else:
            sat_solvers, unsat_solvers = opposers, supporters

        with open(yml_path, "r") as f:
            data = yaml.safe_load(f)

        prop = None
        for p in data.get("properties", []):
            if p.get("property_file", "").endswith("properties/check-sat.prp"):
                prop = p
                break

        if prop is None:
            continue

        old_verdict = prop.get("expected_verdict")

        if verdict == "inconsistent":
            stats["inconsistent"] += 1
            # Keep inconsistent tasks unlabeled for BenchExec compatibility.
            prop.pop("expected_verdict", None)
            if not args.dry_run:
                write_yml(yml_path, data, verdict, sat_solvers, unsat_solvers)
            else:
                print(f"  INCONSISTENT: {bench} "
                      f"(sat: {', '.join(sorted(sat_solvers))}, "
                      f"unsat: {', '.join(sorted(unsat_solvers))})")
            continue

        # verdict is "true" or "false"
        new_bool = True if verdict == "true" else False

        if old_verdict == new_bool:
            stats["unchanged"] += 1
            # Still rewrite to add YAML entries
            if not args.dry_run:
                write_yml(yml_path, data, verdict, sat_solvers, unsat_solvers)
            continue

        if old_verdict is None:
            stats["added"] += 1
        else:
            stats["updated"] += 1
            if not args.dry_run:
                print(f"  CHANGED: {bench}: {old_verdict} -> {new_bool} "
                      f"(sat: {', '.join(sorted(sat_solvers))})")
            else:
                print(f"  WOULD CHANGE: {bench}: {old_verdict} -> {new_bool}")

        prop["expected_verdict"] = new_bool
        if not args.dry_run:
            write_yml(yml_path, data, verdict, sat_solvers, unsat_solvers)

    # Also handle benchmarks that no solver attempted (no entry in all_verdicts)
    # These keep their existing labels but we won't touch them.

    print("\nUpdating XML result files...")
    update_xml_files(results_dir, computed_verdicts, dry_run=args.dry_run)

    print(f"\n=== Summary ===")
    print(f"  Benchmarks with solver data: {len(all_verdicts)}")
    print(f"  Verdicts unchanged:          {stats['unchanged']}")
    print(f"  Verdicts added (new):        {stats['added']}")
    print(f"  Verdicts updated (changed):  {stats['updated']}")
    print(f"  Marked inconsistent:         {stats['inconsistent']}")
    print(f"  No solver produced verdict:  {stats['no_data']}")
    print(f"  Missing .yml files:          {stats['missing_yml']}")


if __name__ == "__main__":
    main()
