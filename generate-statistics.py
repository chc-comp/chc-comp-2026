#!/usr/bin/env python3
"""Generate competition statistics, LaTeX tables, and cactus plots for CHC-COMP 2026.

Reads solver results from BenchExec .xml files and produces:
  - Per-category, per-solver statistics (sat, unsat, timeout, unknown, etc.)
  - LaTeX table fragments for direct inclusion in the competition report
  - Cactus plots (PDF) per category and overall
  - A plain-text summary
  - A CSV file for external processing
  - LaTeX \\newcommand macros for key numbers
  - Model generation and validation tables (previously parse-model-validation.py)
  - A single unified sample LaTeX document (sample.tex)

Usage:
    python3 generate-statistics.py <data_dir> <output_dir>

Example:
    python3 generate-statistics.py results output
"""

import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET
import yaml
from collections import defaultdict

from configs import (
    COMPETITION_NAME,
    BENCH_PREFIX_MARKER,
    normalize_bench_path,
    tex_escape,
    SOLVER_DISPLAY,
    SOLVER_COLORS,
    SOLVER_LATEX_MACROS,
    PLAIN_RESULT_RE,
    MODEL_GEN_RE,
    FIXED_RE,
    VALIDATOR_RE,
    CATEGORIES,
    MODEL_VALIDATION_CAT_GROUPS,
    read_hors_concours,
    solver_label_tex,
    italicise_if_hc,
    solver_linestyle,
    solver_label_plot,
)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("WARNING: matplotlib not found, skipping plots", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# File discovery
# ─────────────────────────────────────────────────────────────────────────────

def discover_solver_files(data_dir):
    """Auto-discover plain solver result XML files from *data_dir*.

    Returns {solver_name: [filepath, ...]}.
    Only per-category files (those with a category suffix) are included, so
    that each benchmark is counted exactly once.
    """
    per_cat = {}
    for fname in sorted(os.listdir(data_dir)):
        m = PLAIN_RESULT_RE.match(fname)
        if not m:
            continue
        solver = m.group(1)
        cat = m.group(2)
        fpath = os.path.join(data_dir, fname)
        if cat is not None:
            print(f"Discovered result file for solver '{solver}', "
                  f"category '{cat}': {fpath}")
            per_cat.setdefault(solver, []).append(fpath)
    return per_cat


# ─────────────────────────────────────────────────────────────────────────────
# XML parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_result_xml(filepath):
    """Parse a BenchExec XML result file.

    Returns (category, list of (benchmark_path, status, cputime) tuples).
    The category is extracted from the root element's *block* attribute,
    e.g. "CHC-COMP2026_check-sat.BV-Lin" → "BV-Lin".
    """
    results = []
    tree = ET.parse(filepath)
    root = tree.getroot()
    block = root.get("block", "")
    category = block.split(".")[-1] if "." in block else block
    for run in root.iter("run"):
        bench = normalize_bench_path(run.get("name", ""))
        cols = {c.get("title"): c.get("value") for c in run.findall("column")}
        status = cols.get("status", "unknown")
        cputime_str = cols.get("cputime", "0s")
        try:
            cputime = float(cputime_str.rstrip("s"))
        except ValueError:
            cputime = 0.0
        results.append((bench, status, cputime))
    return category, results


def classify_result(status):
    """Map a BenchExec status string to a coarse outcome class.

    Returns one of: 'sat', 'unsat', 'timeout', 'oom', 'error', 'unknown'.
    """
    if status == "TIMEOUT":
        return "timeout"
    if "OUT OF MEMORY" in status:
        return "oom"
    if "ERROR" in status:
        return "error"
    if status == "true":
        return "sat"
    if status == "false":
        return "unsat"
    return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Statistics computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_statistics(data_dir):
    """Compute per-solver, per-category statistics from result XML files.

    Returns (stats, cactus_data, categories, cat_sizes, solved_benches_by_solver)
    where:
      stats[solver][category] = {sat, unsat, timeout, unknown, error, oom, total}
      cactus_data[solver][category] = sorted list of cputimes for solved tasks
      categories = sorted list of discovered category names
      cat_sizes[category] = max total tasks seen for that category
      solved_benches_by_solver[solver][category] = set of solved benchmark paths
    """
    solver_files = discover_solver_files(data_dir)

    stats = {}
    cactus_data = {}
    all_categories = set()
    solved_benches_by_solver = {}

    for solver, filepaths in solver_files.items():
        solver_stats = defaultdict(lambda: {
            "sat": 0, "unsat": 0,
            "timeout": 0, "unknown": 0, "error": 0, "oom": 0,
            "total": 0,
        })
        solver_cactus = defaultdict(list)
        solver_solved = defaultdict(set)

        for filepath in filepaths:
            category, solver_results = parse_result_xml(filepath)
            all_categories.add(category)
            for bench, status, cputime in solver_results:
                cls = classify_result(status)
                solver_stats[category]["total"] += 1
                solver_stats[category][cls] += 1
                if cls in ("sat", "unsat"):
                    solver_cactus[category].append(cputime)
                    solver_solved[category].add(bench)

        for cat in solver_cactus:
            solver_cactus[cat].sort()

        stats[solver] = dict(solver_stats)
        cactus_data[solver] = dict(solver_cactus)
        solved_benches_by_solver[solver] = dict(solver_solved)

    cat_sizes = {}
    for solver in stats:
        for cat, s in stats[solver].items():
            cat_sizes[cat] = max(cat_sizes.get(cat, 0), s["total"])

    return (
        stats,
        cactus_data,
        sorted(all_categories),
        cat_sizes,
        solved_benches_by_solver,
    )


# ─────────────────────────────────────────────────────────────────────────────
# LaTeX helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cat_macro(cat):
    """Convert a category name to a safe LaTeX macro suffix.

    E.g. "LIA-Lin-Arrays" → "LIALinArrays".
    """
    return cat.replace("-", "").replace("_", "")


def generate_latex_macros(stats, categories, cat_sizes, overall_rows,
                          solved_benches_by_solver, output_dir, hc_set=frozenset()):
    """Emit LaTeX \\newcommand macros for all key experimental numbers."""
    macros = []

    def newcmd(name, val):
        # Sanitise: LaTeX command names cannot contain digits.
        safe = (name
                .replace("0", "Zero").replace("1", "One").replace("2", "Two")
                .replace("3", "Three").replace("4", "Four").replace("5", "Five")
                .replace("6", "Six").replace("7", "Seven").replace("8", "Eight")
                .replace("9", "Nine"))
        macros.append(f"\\newcommand{{\\{safe}}}{{{val}}}")

    # Competition-wide totals
    total_benchmarks = sum(cat_sizes.values())
    newcmd("numBenchmarks", f"\\numprint{{{total_benchmarks}}}")
    newcmd("numCategories", str(len(categories)))
    newcmd("numSolverConfigs", str(len(stats)))

    # Category sizes
    for cat in categories:
        newcmd(f"catSize{_cat_macro(cat)}", f"\\numprint{{{cat_sizes[cat]}}}")

    # Virtual best per category (union of all solved tasks)
    virtual_best_per_cat = {}
    for cat in categories:
        union = set()
        for solver in solved_benches_by_solver:
            union |= solved_benches_by_solver[solver].get(cat, set())
        virtual_best_per_cat[cat] = len(union)
    virtual_best_total = sum(virtual_best_per_cat.values())
    newcmd("virtualBestTotal", f"\\numprint{{{virtual_best_total}}}")
    for cat in categories:
        newcmd(f"virtualBest{_cat_macro(cat)}",
               f"\\numprint{{{virtual_best_per_cat[cat]}}}")

    # Algorithm selection (best single config per category, summed)
    algo_select_total = 0
    for cat in categories:
        best = max(
            (stats[s].get(cat, {}).get("sat", 0) +
             stats[s].get(cat, {}).get("unsat", 0))
            for s in stats
        ) if stats else 0
        algo_select_total += best
    newcmd("algorithmSelectionTotal", f"\\numprint{{{algo_select_total}}}")

    # Best solver overall
    if overall_rows:
        best_solver, entered, total_answers, sat, unsat, timeout, unknown, error = overall_rows[0]
        best_display = solver_label_tex(best_solver, hc_set)
        pct = 100 * total_answers / entered if entered > 0 else 0
        newcmd("bestSolverOverall", best_display)
        newcmd("bestSolverOverallCount", f"\\numprint{{{total_answers}}}")
        newcmd("bestSolverOverallPct", f"{pct:.1f}")
        algo_gain = algo_select_total - total_answers
        algo_gain_pct = 100 * algo_gain / total_answers if total_answers > 0 else 0
        newcmd("algorithmSelectionGain", f"\\numprint{{{algo_gain}}}")
        newcmd("algorithmSelectionGainPct", f"{algo_gain_pct:.1f}")

    # Virtual best vs algorithm selection gap
    portfolio_gap = virtual_best_total - algo_select_total
    newcmd("virtualBestGap", f"\\numprint{{{portfolio_gap}}}")

    # Per-category best solver
    for cat in categories:
        best_solver = None
        best_count = 0
        for solver in stats:
            s = stats[solver].get(cat, {})
            c = s.get("sat", 0) + s.get("unsat", 0)
            if c > best_count:
                best_count = c
                best_solver = solver
        if best_solver:
            display = solver_label_tex(best_solver, hc_set)
            cat_total = cat_sizes.get(cat, 0)
            pct = 100 * best_count / cat_total if cat_total > 0 else 0
            cn = _cat_macro(cat)
            newcmd(f"bestSolver{cn}", display)
            newcmd(f"bestCount{cn}", f"\\numprint{{{best_count}}}")
            newcmd(f"bestPct{cn}", f"{pct:.1f}")

    # Per-solver key macros (iterates over all solvers defined in configs)
    for solver_key, macro_base in SOLVER_LATEX_MACROS.items():
        if solver_key not in stats:
            continue
        total_sat   = sum(stats[solver_key].get(c, {}).get("sat",   0) for c in categories)
        total_unsat = sum(stats[solver_key].get(c, {}).get("unsat", 0) for c in categories)
        total_answers = total_sat + total_unsat
        total_entered = sum(stats[solver_key].get(c, {}).get("total", 0) for c in categories)
        pct = 100 * total_answers / total_entered if total_entered > 0 else 0
        newcmd(f"count{macro_base}", f"\\numprint{{{total_answers}}}")
        newcmd(f"pct{macro_base}", f"{pct:.1f}")

    path = os.path.join(output_dir, "macros-stats.tex")
    with open(path, "w") as f:
        f.write("% Auto-generated by generate-statistics.py — do not edit manually.\n")
        f.write("\n".join(macros) + "\n")
    print(f"Wrote {path}")
    return virtual_best_per_cat


# ─────────────────────────────────────────────────────────────────────────────
# LaTeX table: overall
# ─────────────────────────────────────────────────────────────────────────────

def generate_latex_overall(stats, categories, output_dir, hc_set=frozenset()):
    """Generate a LaTeX table with overall results per solver."""
    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(
        r"\caption{Overall results per solver: "
        r"number of SAT/UNSAT answers and unanswered tasks.}")
    lines.append(r"\label{tab:results-overall}")
    lines.append(r"\begin{tabular}{lrrrrr}")
    lines.append(r"\toprule")
    lines.append(
        r"\textbf{Solver} & \textbf{Correct} & \textbf{SAT} & \textbf{UNSAT} "
        r"& \textbf{Timeout} & \textbf{Unknown} \\")
    lines.append(r"\midrule")

    rows = []
    for solver in stats:
        total_tests   = sum(stats[solver].get(c, {}).get("total",   0) for c in categories)
        total_sat     = sum(stats[solver].get(c, {}).get("sat",     0) for c in categories)
        total_unsat   = sum(stats[solver].get(c, {}).get("unsat",   0) for c in categories)
        total_timeout = sum(stats[solver].get(c, {}).get("timeout", 0) for c in categories)
        total_unknown = sum(stats[solver].get(c, {}).get("unknown", 0) for c in categories)
        total_error   = sum(stats[solver].get(c, {}).get("error",   0) for c in categories)
        total_answers = total_sat + total_unsat
        rows.append((solver, total_tests, total_answers, total_sat,
                     total_unsat, total_timeout, total_unknown, total_error))

    rows.sort(key=lambda r: -r[2])
    for solver, total_tests, total_answers, sat, unsat, timeout, unknown, error in rows:
        solver_tex = solver_label_tex(solver, hc_set)
        fmt = lambda n: italicise_if_hc(f"{n:,}", solver, hc_set)
        lines.append(
            f"{solver_tex} & {fmt(total_answers)} & {fmt(sat)} & {fmt(unsat)} & {fmt(timeout)} & {fmt(unknown)} \\\\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, "table-overall.tex")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {path}")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# LaTeX table: per-category
# ─────────────────────────────────────────────────────────────────────────────

def generate_latex_per_category(stats, cat_sizes, categories, output_dir, hc_set=frozenset()):
    """Generate a LaTeX table with per-category results per solver."""
    short_names = {cat: cat.replace("-Arrays", "-Arr") for cat in categories}

    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(
        r"\caption{Per-category results: correctly solved benchmarks per solver. "
        r"Best per category in bold. ``---'' = not entered.}")
    lines.append(r"\label{tab:results-category}")
    lines.append(r"\small")
    lines.append(r"\setlength{\tabcolsep}{3pt}")
    ncols = len(categories)
    lines.append(r"\begin{tabular}{l" + "*{" + str(ncols) + r"}{S[table-format=4.0]}}")
    lines.append(r"\toprule")

    header = ""
    for cat in categories:
        header += (f" & \\multicolumn{{1}}{{c}}"
                   f"{{\\rotatebox{{90}}{{{short_names[cat]}}}}}")
    lines.append(header + r" \\")

    size_row = ""
    for cat in categories:
        size_row += (f" & \\multicolumn{{1}}{{c}}"
                     f"{{\\footnotesize({cat_sizes.get(cat, 0)})}}")
    lines.append(size_row + r" \\")
    lines.append(r"\midrule")

    best = {}
    for cat in categories:
        competing = [s for s in stats if s not in hc_set]
        best[cat] = max(
            (stats[s].get(cat, {}).get("sat", 0) +
             stats[s].get(cat, {}).get("unsat", 0))
            for s in competing
        ) if competing else 0

    for solver in sorted(stats.keys()):
        row = f"{solver_label_tex(solver, hc_set):16s}"
        for cat in categories:
            s = stats[solver].get(cat)
            if s is None or s.get("total", 0) == 0:
                row += r" & \multicolumn{1}{c}{---}"
            else:
                answers = s.get("sat", 0) + s.get("unsat", 0)
                if solver in hc_set:
                    row += r" & \multicolumn{1}{r}{\textit{" + str(answers) + r"}}"
                elif answers == best[cat] and answers > 0:
                    row += r" & \multicolumn{1}{r}{\textbf{" + str(answers) + r"}}"
                else:
                    row += f" & {answers}"
        row += r" \\"
        lines.append(row)

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, "table-per-category.tex")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Cactus plots
# ─────────────────────────────────────────────────────────────────────────────

def generate_cactus_plots(cactus_data, categories, cat_sizes, output_dir, hc_set=frozenset()):
    """Generate per-category and overall cactus plots (PDF)."""
    if not HAS_MATPLOTLIB:
        return

    for cat in categories:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        any_data = False
        for solver in sorted(cactus_data.keys()):
            times = cactus_data[solver].get(cat, [])
            if not times:
                continue
            any_data = True
            ax.plot(
                list(range(1, len(times) + 1)), times,
                label=solver_label_plot(solver, hc_set),
                color=SOLVER_COLORS.get(solver, "black"),
                linestyle=solver_linestyle(solver, hc_set),
                linewidth=1.5,
            )
        if not any_data:
            plt.close()
            continue
        ax.set_xlabel("Correctly solved benchmarks (cumulative)")
        ax.set_ylabel("CPU time (s)")
        ax.set_title(
            f"{COMPETITION_NAME} — {cat} ({cat_sizes.get(cat, '?')} benchmarks)")
        ax.set_yscale("log")
        ax.set_yticks([0.1, 1, 10, 100, 1000])
        ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="lower right")
        plt.tight_layout()
        path = os.path.join(output_dir, f"cactus-{cat}.pdf")
        plt.savefig(path)
        plt.close()
        print(f"Wrote {path}")

    fig, ax = plt.subplots(figsize=(8, 5))
    for solver in sorted(cactus_data.keys()):
        all_times = []
        for cat in categories:
            all_times.extend(cactus_data[solver].get(cat, []))
        if not all_times:
            continue
        all_times.sort()
        ax.plot(
            list(range(1, len(all_times) + 1)), all_times,
            label=solver_label_plot(solver, hc_set),
            color=SOLVER_COLORS.get(solver, "black"),
            linestyle=solver_linestyle(solver, hc_set),
            linewidth=1.5,
        )
    ax.set_xlabel("Correctly solved benchmarks (cumulative)")
    ax.set_ylabel("CPU time (s)")
    ax.set_title(
        f"{COMPETITION_NAME} — Overall ({sum(cat_sizes.values())} benchmarks)")
    ax.set_yscale("log")
    ax.set_yticks([0.1, 1, 10, 100, 1000])
    ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    plt.tight_layout()
    path = os.path.join(output_dir, "cactus-overall.pdf")
    plt.savefig(path)
    plt.close()
    print(f"Wrote {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Plain-text summary
# ─────────────────────────────────────────────────────────────────────────────

def generate_text_summary(stats, categories, cat_sizes, overall_rows, output_dir, hc_set=frozenset()):
    """Generate a plain-text summary with key numbers."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"{COMPETITION_NAME} Solver Results Summary")
    lines.append("=" * 70)
    lines.append(f"\nTotal benchmarks: {sum(cat_sizes.values())}")

    lines.append("\n--- Category Sizes ---")
    for cat in sorted(categories):
        lines.append(f"  {cat:20s}: {cat_sizes.get(cat, 0):5d}")

    lines.append("\n--- Overall Solver Rankings (by SAT+UNSAT answers) ---")
    for solver, entered, total_answers, sat, unsat, timeout, unknown, error in overall_rows:
        if entered > 0:
            pct = 100 * total_answers / entered
            hc_note = " (hors concours)" if solver in hc_set else ""
            lines.append(
                f"  {SOLVER_DISPLAY.get(solver, solver.title()):20s}: "
                f"{total_answers:5d} / {entered:5d} ({pct:5.1f}%){hc_note}")

    lines.append("\n--- Category Winners (by SAT+UNSAT answers) ---")
    for cat in sorted(categories):
        best_solver = None
        best_count = 0
        for solver in stats:
            s = stats[solver].get(cat, {})
            c = s.get("sat", 0) + s.get("unsat", 0)
            if c > best_count:
                best_count = c
                best_solver = solver
        if best_solver:
            cat_total = cat_sizes.get(cat, 0)
            pct = 100 * best_count / cat_total if cat_total > 0 else 0
            lines.append(
                f"  {cat:20s}: "
                f"{SOLVER_DISPLAY.get(best_solver, best_solver):20s} "
                f"({best_count}/{cat_total}, {pct:.1f}%)")

    lines.append("\n--- Timeouts per Solver ---")
    for solver in sorted(stats.keys()):
        total_timeout = sum(stats[solver].get(c, {}).get("timeout", 0) for c in categories)
        if total_timeout > 0:
            lines.append(
                f"  {SOLVER_DISPLAY.get(solver, solver.title()):20s}: "
                f"{total_timeout} timeouts")

    text = "\n".join(lines) + "\n"
    path = os.path.join(output_dir, "summary.txt")
    with open(path, "w") as f:
        f.write(text)
    print(f"Wrote {path}")
    print(text)


# ─────────────────────────────────────────────────────────────────────────────
# CSV export
# ─────────────────────────────────────────────────────────────────────────────

def generate_csv(stats, categories, cat_sizes, output_dir):
    """Generate a CSV file with per-solver, per-category statistics."""
    path = os.path.join(output_dir, "results.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Solver", "Category", "Total", "SAT", "UNSAT",
                         "Timeout", "Unknown", "Error", "OOM"])
        for solver in sorted(stats.keys()):
            for cat in categories:
                s = stats[solver].get(cat)
                if s is None:
                    continue
                writer.writerow([solver, cat, s["total"], s["sat"], s["unsat"],
                                  s["timeout"], s["unknown"], s["error"], s["oom"]])
    print(f"Wrote {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Dissent / consistency table
# ─────────────────────────────────────────────────────────────────────────────

# Verdict meanings (from majority_vote_verdict in .yml files):
#   sat            – majority voted SAT (not model-validated)
#   unsat          – majority voted UNSAT
#   sat_validated  – SAT, confirmed by model validation
#   unsat_validated– UNSAT, confirmed by validation (rare)
#   inconsistent   – equal SAT/UNSAT votes, no proof either way

_VALIDATED = {"sat_validated", "unsat_validated"}
_SAT_VERDICTS = {"sat", "sat_validated"}


def load_majority_verdicts(benchmarks_dir):
    """Load majority_vote_verdict for every benchmark from its .yml file.

    Returns {bench_path: majority_vote_verdict_str}.  *bench_path* is the
    relative path within *benchmarks_dir*, which matches the output of
    normalize_bench_path() applied to BenchExec XML run names.
    """
    verdicts = {}
    for cat in CATEGORIES:
        set_file = os.path.join(benchmarks_dir, cat + ".set")
        if not os.path.exists(set_file):
            continue
        with open(set_file) as fh:
            benches = [ln.strip().removeprefix("./") for ln in fh if ln.strip()]
        for bench in benches:
            yml_path = os.path.join(benchmarks_dir, bench)
            if not os.path.exists(yml_path):
                continue
            with open(yml_path) as fh:
                data = yaml.safe_load(fh)
            for prop in data.get("properties", []):
                if prop.get("property_file", "").endswith("properties/check-sat.prp"):
                    mv = prop.get("majority_vote_verdict")
                    if mv:
                        verdicts[bench] = str(mv)
                    break
    return verdicts


def compute_dissent_stats(data_dir, benchmarks_dir):
    """Compute per-solver, per-category dissent/inconsistency counts.

    For each (solver, benchmark) pair where the solver gave a definitive
    answer (true/false) and the benchmark has a majority_vote_verdict,
    classify the result as one of:

    * inconsistent – majority_vote_verdict == "inconsistent" (equal votes,
                     no proof; any solver answer counts)
    * dissenting   – solver contradicts a *non-validated* majority verdict
                     ("sat" → solver said false; "unsat" → solver said true)
    * wrong        – solver contradicts a *validated* verdict
                     ("sat_validated" → solver said false;
                      "unsat_validated" → solver said true)

    Returns {solver: {category: {"inconsistent": N, "dissenting": N, "wrong": N}}}.
    """
    print("Loading majority_vote_verdict from benchmark YAML files...")
    mv_map = load_majority_verdicts(benchmarks_dir)
    print(f"Loaded verdicts for {len(mv_map)} benchmarks.")

    # Find per-category solver result files (same set as compute_statistics)
    solver_files = {}
    for fname in sorted(os.listdir(data_dir)):
        m = PLAIN_RESULT_RE.match(fname)
        if not m:
            continue
        solver, cat = m.group(1), m.group(2)
        if cat is not None:
            solver_files.setdefault(solver, []).append(
                os.path.join(data_dir, fname))

    dissent = {}
    for solver, filepaths in solver_files.items():
        solver_d = defaultdict(lambda: {"inconsistent": 0, "dissenting": 0, "wrong": 0})
        for filepath in filepaths:
            cat, results = parse_result_xml(filepath)
            for bench, status, _cpu in results:
                if status not in ("true", "false"):
                    continue
                mv = mv_map.get(bench)
                if mv is None:
                    continue
                if mv == "inconsistent":
                    solver_d[cat]["inconsistent"] += 1
                elif mv in _SAT_VERDICTS and status == "false":
                    if mv in _VALIDATED:
                        solver_d[cat]["wrong"] += 1
                    else:
                        solver_d[cat]["dissenting"] += 1
                elif mv not in _SAT_VERDICTS and mv != "inconsistent" and status == "true":
                    # mv in {"unsat", "unsat_validated"}
                    if mv in _VALIDATED:
                        solver_d[cat]["wrong"] += 1
                    else:
                        solver_d[cat]["dissenting"] += 1
        dissent[solver] = dict(solver_d)
    return dissent


def generate_latex_dissent_table(dissent_stats, categories, output_dir,
                                  hc_set=frozenset()):
    """Generate a long-form LaTeX table of per-solver inconsistent/dissenting/wrong counts.

    Only rows with at least one non-zero count are included.
    Solvers are separated by \\midrule; categories follow canonical order.
    """
    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(
        r"\caption{Inconsistent, dissenting, and wrong answers per solver and "
        r"category. Only non-zero rows are shown. "
        r"\emph{Inconsistent}: benchmark has equal SAT/UNSAT votes with no proof; "
        r"\emph{Dissenting}: solver contradicts a non-validated majority verdict; "
        r"\emph{Wrong}: solver contradicts a validated verdict.}")
    lines.append(r"\label{tab:dissent}")
    lines.append(r"\begin{tabular}{llrrr}")
    lines.append(r"\toprule")
    lines.append(
        r"\textbf{Solver} & \textbf{Category} & "
        r"\textbf{Inconsistent} & \textbf{Dissenting} & \textbf{Wrong} \\")
    lines.append(r"\midrule")

    any_row = False
    first_solver = True
    for solver in sorted(dissent_stats):
        # Collect non-zero rows for this solver in canonical category order
        solver_rows = []
        for cat in categories:
            d = dissent_stats[solver].get(cat, {})
            inc = d.get("inconsistent", 0)
            dis = d.get("dissenting",   0)
            wrg = d.get("wrong",        0)
            if inc or dis or wrg:
                solver_rows.append((cat, inc, dis, wrg))
        # Also catch any categories not in the canonical list
        extra = sorted(set(dissent_stats[solver]) - set(categories))
        for cat in extra:
            d = dissent_stats[solver][cat]
            inc = d.get("inconsistent", 0)
            dis = d.get("dissenting",   0)
            wrg = d.get("wrong",        0)
            if inc or dis or wrg:
                solver_rows.append((cat, inc, dis, wrg))

        if not solver_rows:
            continue

        if not first_solver:
            lines.append(r"\midrule")
        first_solver = False
        any_row = True

        solver_tex = solver_label_tex(solver, hc_set)
        fmt = lambda n, s=solver: italicise_if_hc(str(n), s, hc_set)
        n = len(solver_rows)
        for i, (cat, inc, dis, wrg) in enumerate(solver_rows):
            solver_col = (
                f"\\multirow{{{n}}}{{*}}{{{solver_tex}}}"
                if i == 0 else "")
            lines.append(
                f"{solver_col} & {cat} & {fmt(inc)} & {fmt(dis)} & {fmt(wrg)} \\\\")

    if not any_row:
        lines.append(r"\multicolumn{5}{c}{\emph{No inconsistencies or disagreements found.}} \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, "table-dissent.tex")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Model validation: file discovery
# ─────────────────────────────────────────────────────────────────────────────

def _discover_model_gen_files(data_dir):
    """Discover solver model-generation per-category XML files.

    Returns {solver: {category: filepath}}.  Per-category files are preferred;
    an aggregate file (no category suffix) is listed under key *None* as a
    fallback so callers can decide how to handle it.
    """
    per_cat = {}
    aggregate = {}
    for fname in sorted(os.listdir(data_dir)):
        m = MODEL_GEN_RE.match(fname)
        if not m:
            continue
        solver = m.group(1)
        cat = m.group(2)
        fpath = os.path.join(data_dir, fname)
        if cat is None:
            aggregate[solver] = fpath
        else:
            per_cat.setdefault(solver, {})[cat] = fpath
    result = dict(per_cat)
    for solver, agg_path in aggregate.items():
        if solver not in result:
            result[solver] = {None: agg_path}
    return result


def _discover_fixed_files(data_dir):
    """Discover solver fixed-result per-category XML files.

    Returns {solver: {category: filepath}}.
    """
    result = {}
    for fname in sorted(os.listdir(data_dir)):
        m = FIXED_RE.match(fname)
        if not m:
            continue
        solver = m.group(1)
        cat = m.group(2)
        if cat is None:
            continue  # skip aggregate
        result.setdefault(solver, {})[cat] = os.path.join(data_dir, fname)
    return result


def _discover_validator_files(data_dir):
    """Discover validator per-category XML files.

    Returns {validator: {solver: {category: filepath}}}.
    """
    result = {}
    for fname in sorted(os.listdir(data_dir)):
        m = VALIDATOR_RE.match(fname)
        if not m:
            continue
        validator = m.group(1)
        solver = m.group(2)
        cat = m.group(3)
        if cat is None:
            continue  # skip aggregate
        (result
         .setdefault(validator, {})
         .setdefault(solver, {}))[cat] = os.path.join(data_dir, fname)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Model validation: XML parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_xml_results(filepath):
    """Parse a BenchExec XML result file for model-validation purposes.

    Returns list of (name, status, category_value) tuples.
    """
    results = []
    tree = ET.parse(filepath)
    for run in tree.getroot().iter("run"):
        name = run.get("name", "")
        status = None
        category = None
        for col in run.findall("column"):
            title = col.get("title")
            if title == "status":
                status = col.get("value")
            elif title == "category":
                category = col.get("value")
        results.append((name, status, category))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Model validation: result parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_model_gen_results(data_dir):
    """Parse model-generation solver results per category.

    Returns {solver: {category: {status: count}}}.
    """
    model_gen_files = _discover_model_gen_files(data_dir)
    solver_results = {}
    for solver, cat_files in model_gen_files.items():
        solver_results[solver] = {}
        for cat, filepath in cat_files.items():
            if cat is None:
                continue  # aggregate without per-category split; skip
            counts = defaultdict(int)
            for _name, status, _cat_val in _parse_xml_results(filepath):
                counts[status] += 1
            solver_results[solver][cat] = dict(counts)
    return solver_results


def parse_model_validated_results(data_dir):
    """Parse post-validation (fixed) results per solver per category.

    Returns {solver: {category: {validated, unvalidated, wrong, other}}}.
    Only rows with status=true (SAT answers) are counted because model
    validation applies only to SAT witnesses.
    """
    fixed_files = _discover_fixed_files(data_dir)
    validated = {}
    for solver, cat_files in fixed_files.items():
        validated[solver] = {}
        for cat, filepath in cat_files.items():
            counts = {"validated": 0, "unvalidated": 0, "wrong": 0, "other": 0}
            for _name, status, category in _parse_xml_results(filepath):
                if status != "true":
                    continue
                if category == "correct":
                    counts["validated"] += 1
                elif category in ("unknown", "unkown"):  # tolerate typo
                    counts["unvalidated"] += 1
                elif category == "wrong":
                    counts["wrong"] += 1
                else:
                    counts["other"] += 1
            validated[solver][cat] = counts
    return validated


def parse_validator_results(data_dir):
    """Parse individual validator results.

    Returns {validator: {solver: {category: {correct, wrong, unknown}}}}.
    """
    validator_files = _discover_validator_files(data_dir)
    val_results = {}
    for validator, solver_cats in validator_files.items():
        val_results[validator] = {}
        for solver, cat_files in solver_cats.items():
            val_results[validator][solver] = {}
            for cat, filepath in cat_files.items():
                counts = {"correct": 0, "wrong": 0, "unknown": 0}
                for _name, _status, category in _parse_xml_results(filepath):
                    if category == "correct":
                        counts["correct"] += 1
                    elif category in ("wrong", "false"):
                        counts["wrong"] += 1
                    else:
                        counts["unknown"] += 1
                val_results[validator][solver][cat] = counts
    return val_results


# ─────────────────────────────────────────────────────────────────────────────
# Model validation: LaTeX helpers
# ─────────────────────────────────────────────────────────────────────────────

def _write_per_cat_table(f, cat_group, categories, all_solvers,
                         validated, solver_results, caption, label,
                         hc_set=frozenset()):
    """Write a single per-category LaTeX table to an open file handle."""
    f.write("\\begin{table}[H]\n")
    f.write("\\centering\n")
    f.write(f"\\caption{{{caption}}}\n")
    f.write(f"\\label{{{label}}}\n")
    f.write("\\footnotesize\n")
    f.write("\\begin{tabular}{llrrrr}\n")
    f.write("\\toprule\n")
    f.write(
        "\\textbf{Category} & \\textbf{Solver} & \\textbf{SAT} & "
        "\\textbf{Validated} & \\textbf{Unvalidated} & \\textbf{Rate} \\\\\n")
    f.write("\\midrule\n")

    first_cat = True
    for cat in cat_group:
        if cat not in categories:
            continue
        cat_rows = []
        for solver in all_solvers:
            if cat not in validated.get(solver, {}):
                continue
            vr = validated[solver][cat]
            sr = solver_results.get(solver, {}).get(cat, {})
            sat = sr.get("true", 0)
            if sat == 0 and vr["validated"] == 0 and vr["unvalidated"] == 0:
                continue
            val = vr["validated"]
            unv = vr["unvalidated"]
            rate = f"{val / sat * 100:.1f}\\%" if sat > 0 else "---"
            cat_rows.append((solver, sat, val, unv, rate))

        if not cat_rows:
            continue
        if not first_cat:
            f.write("\\midrule\n")
        first_cat = False

        for i, (solver, sat, val, unv, rate) in enumerate(cat_rows):
            display = solver_label_tex(solver, hc_set)
            cat_col = (
                f"\\multirow{{{len(cat_rows)}}}{{*}}{{{cat}}}"
                if i == 0 else "")
            sat_str = italicise_if_hc(f"{sat:,}".replace(",", "{,}"), solver, hc_set)
            val_str = italicise_if_hc(f"{val:,}".replace(",", "{,}"), solver, hc_set)
            unv_str = italicise_if_hc(f"{unv:,}".replace(",", "{,}"), solver, hc_set)
            rate    = italicise_if_hc(rate, solver, hc_set)
            f.write(f"{cat_col} & {display:12s} & {sat_str} & "
                    f"{val_str} & {unv_str} & {rate} \\\\\n")

    f.write("\\bottomrule\n")
    f.write("\\end{tabular}\n")
    f.write("\\end{table}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Model validation: LaTeX macros
# ─────────────────────────────────────────────────────────────────────────────

def generate_latex_macros_validation(summary, validated, solver_results,
                                     categories, output_dir):
    """Emit LaTeX \\newcommand macros for key model-validation numbers."""
    macros = []

    def newcmd(name, val):
        safe = (name
                .replace("0", "Zero").replace("1", "One").replace("2", "Two")
                .replace("3", "Three").replace("4", "Four").replace("5", "Five")
                .replace("6", "Six").replace("7", "Seven").replace("8", "Eight")
                .replace("9", "Nine"))
        macros.append(f"\\newcommand{{\\{safe}}}{{{val}}}")

    for solver_key, macro_base in SOLVER_LATEX_MACROS.items():
        if solver_key not in summary:
            continue
        s = summary[solver_key]
        sat = s["sat"]
        validated_count = s["validated"]
        rate = validated_count / sat * 100 if sat > 0 else 0
        newcmd(f"validSAT{macro_base}",      f"\\numprint{{{sat}}}")
        newcmd(f"validValidated{macro_base}", f"\\numprint{{{validated_count}}}")
        newcmd(f"validRate{macro_base}",      f"{rate:.1f}")

    path = os.path.join(output_dir, "macros-validation.tex")
    with open(path, "w") as f:
        f.write(
            "% Auto-generated by generate-statistics.py — do not edit manually.\n")
        f.write("\n".join(macros) + "\n")
    print(f"Wrote {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Model validation: main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_model_validation(data_dir, output_dir, hc_set=frozenset()):
    """Run the full model-validation pipeline; return n_val_groups (0 if skipped)."""
    mv_solver_results = parse_model_gen_results(data_dir)
    mv_validated      = parse_model_validated_results(data_dir)
    _val_results      = parse_validator_results(data_dir)  # available for future use

    if not mv_solver_results and not mv_validated:
        return 0

    all_solvers = sorted(set(mv_solver_results.keys()) | set(mv_validated.keys()))
    categories = sorted({
        cat
        for per_solver in (list(mv_solver_results.values()) + list(mv_validated.values()))
        for cat in per_solver.keys()
    })

    # Overall summary per solver
    summary = {}
    for solver in all_solvers:
        total_sat         = 0
        total_validated   = 0
        total_unvalidated = 0
        total_wrong       = 0
        for cat in categories:
            sr = mv_solver_results.get(solver, {}).get(cat, {})
            total_sat += sr.get("true", 0)
            vr = mv_validated.get(solver, {}).get(cat, {})
            total_validated   += vr.get("validated",   0)
            total_unvalidated += vr.get("unvalidated", 0)
            total_wrong       += vr.get("wrong",       0)
        summary[solver] = {
            "sat":         total_sat,
            "validated":   total_validated,
            "unvalidated": total_unvalidated,
            "wrong":       total_wrong,
        }

    # Print summary
    print("=" * 70)
    print(f"MODEL VALIDATION TRACK — {COMPETITION_NAME}")
    print("=" * 70)
    for solver, s in summary.items():
        display = SOLVER_DISPLAY.get(solver, solver.title())
        rate = f"{s['validated'] / s['sat'] * 100:.1f}%" if s["sat"] > 0 else "N/A"
        print(f"  {display:12s}: SAT={s['sat']:5d}  Validated={s['validated']:5d}  "
              f"Unvalidated={s['unvalidated']:5d}  Dissenting={s['wrong']:3d}  Rate={rate}")

    print("\n--- Per-category details ---")
    for solver in all_solvers:
        display = SOLVER_DISPLAY.get(solver, solver.title())
        print(f"\n  {display}:")
        for cat in categories:
            vr = mv_validated.get(solver, {}).get(cat, {})
            sr = mv_solver_results.get(solver, {}).get(cat, {})
            sat = sr.get("true", 0)
            if sat == 0 and not any(vr.values()):
                continue
            print(f"    {cat:20s}: SAT={sat:5d}  Validated={vr.get('validated', 0):5d}  "
                  f"Unvalidated={vr.get('unvalidated', 0):5d}  "
                  f"Dissenting={vr.get('wrong', 0):3d}")

    # Overall LaTeX table
    tex_path = os.path.join(output_dir, "table-model-validation.tex")
    with open(tex_path, "w") as f:
        f.write("\\begin{table}[H]\n")
        f.write("\\centering\n")
        f.write("\\caption{Model generation and validation results.}\n")
        f.write("\\label{tab:model-validation}\n")
        f.write("\\begin{tabular}{lrrrr}\n")
        f.write("\\toprule\n")
        f.write(
            "\\textbf{Solver} & \\textbf{SAT} & \\textbf{Validated} "
            "& \\textbf{Unvalidated} & \\textbf{Rate} \\\\\n")
        f.write("\\midrule\n")
        for solver in all_solvers:
            s = summary.get(solver)
            if s is None:
                continue
            display = solver_label_tex(solver, hc_set)
            rate    = f"{s['validated'] / s['sat'] * 100:.1f}\\%" if s["sat"] > 0 else "---"
            sat_str = italicise_if_hc(f"{s['sat']:,}".replace(",", "{,}"), solver, hc_set)
            val_str = italicise_if_hc(f"{s['validated']:,}".replace(",", "{,}"), solver, hc_set)
            unv_str = italicise_if_hc(f"{s['unvalidated']:,}".replace(",", "{,}"), solver, hc_set)
            rate    = italicise_if_hc(rate, solver, hc_set)
            f.write(f"{display:12s} & {sat_str} & {val_str} & {unv_str} & {rate} \\\\\n")
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")
    print(f"\nWrote {tex_path}")

    # Split per-category LaTeX tables
    cat_group_defs = []
    for i, cat_group in enumerate(MODEL_VALIDATION_CAT_GROUPS, start=1):
        cat_group_defs.append((
            f"table-model-validation-per-cat-{i}.tex",
            f"tab:model-validation-per-cat-{i}",
            (f"Per-category model validation results "
             f"({', '.join(cat_group)}). "
             f"``---'' = solver did not participate in this category."),
            cat_group,
        ))

    for filename, label, caption, cat_group in cat_group_defs:
        tex_cat_path = os.path.join(output_dir, filename)
        with open(tex_cat_path, "w") as f:
            _write_per_cat_table(
                f, cat_group, categories, all_solvers,
                mv_validated, mv_solver_results, caption, label, hc_set)
        print(f"Wrote {tex_cat_path}")

    # Legacy single-file per-category table
    tex_cat_path = os.path.join(output_dir, "table-model-validation-per-category.tex")
    with open(tex_cat_path, "w") as f:
        _write_per_cat_table(
            f, categories, categories, all_solvers,
            mv_validated, mv_solver_results,
            caption=(
                "Per-category model validation results. "
                "``---'' = solver did not participate in this category."),
            label="tab:model-validation-per-category",
            hc_set=hc_set)
    print(f"Wrote {tex_cat_path}")

    # CSV
    csv_path = os.path.join(output_dir, "model-validation.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Solver", "Category", "SAT", "Validated",
                         "Unvalidated", "Dissenting"])
        for solver in all_solvers:
            for cat in categories:
                vr = mv_validated.get(solver, {}).get(cat, {})
                sr = mv_solver_results.get(solver, {}).get(cat, {})
                sat = sr.get("true", 0)
                writer.writerow([
                    SOLVER_DISPLAY.get(solver, solver.title()),
                    cat, sat,
                    vr.get("validated",   0),
                    vr.get("unvalidated", 0),
                    vr.get("wrong",       0),
                ])
    print(f"Wrote {csv_path}")

    # LaTeX macros
    print("\nGenerating model-validation LaTeX macros...")
    generate_latex_macros_validation(summary, mv_validated, mv_solver_results,
                                     categories, output_dir)

    return len(MODEL_VALIDATION_CAT_GROUPS)


# ─────────────────────────────────────────────────────────────────────────────
# Sample LaTeX document
# ─────────────────────────────────────────────────────────────────────────────

def generate_sample_latex(categories, output_dir, has_dissent=False,
                          n_val_groups=0):
    """Generate a unified standalone sample LaTeX document including every artifact."""
    L = []
    L.append(r"\documentclass[a4paper]{article}")
    L.append(r"\usepackage[margin=2.5cm]{geometry}")
    L.append(r"\usepackage{booktabs}")
    L.append(r"\usepackage{multirow}")
    L.append(r"\usepackage{rotating}")
    L.append(r"\usepackage{siunitx}")
    L.append(r"\usepackage{graphicx}")
    L.append(r"\usepackage{subcaption}")
    L.append(r"\usepackage{numprint}")
    L.append(r"\usepackage{float}")
    L.append(r"\npdecimalsign{.}")
    L.append(r"\npthousandsep{,}")
    L.append(r"")
    L.append(r"% Solver-statistics \newcommand macros")
    L.append(r"\input{macros-stats}")
    if n_val_groups > 0:
        L.append(r"% Model-validation \newcommand macros")
        L.append(r"\input{macros-validation}")
    L.append(r"")
    L.append(r"\begin{document}")
    L.append(r"")
    L.append(r"\section*{Overall results}")
    L.append(r"\input{table-overall}")
    L.append(r"")
    L.append(r"\section*{Per-category results}")
    L.append(r"\input{table-per-category}")
    L.append(r"")
    if has_dissent:
        L.append(r"\section*{Inconsistent, dissenting, and wrong answers}")
        L.append(r"\input{table-dissent}")
        L.append(r"")
    L.append(r"\section*{Cactus plots}")
    L.append(r"")
    L.append(r"\begin{figure}[H]")
    L.append(r"  \centering")
    L.append(r"  \includegraphics[width=\linewidth]{cactus-overall}")
    L.append(r"  \caption{Overall cactus plot.}")
    L.append(r"  \label{fig:cactus-overall}")
    L.append(r"\end{figure}")
    L.append(r"")
    for cat in categories:
        L.append(r"\begin{figure}[H]")
        L.append(r"  \centering")
        L.append(f"  \\includegraphics[width=\\linewidth]{{cactus-{cat}}}")
        L.append(f"  \\caption{{Cactus plot for the {cat} category.}}")
        L.append(f"  \\label{{fig:cactus-{cat}}}")
        L.append(r"\end{figure}")
        L.append(r"")
    if n_val_groups > 0:
        L.append(r"\section*{Model generation and validation --- overall}")
        L.append(r"\input{table-model-validation}")
        L.append(r"")
        L.append(r"\section*{Model generation and validation --- per category}")
        for i in range(1, n_val_groups + 1):
            L.append(f"\\input{{table-model-validation-per-cat-{i}}}")
            L.append(r"")
    L.append(r"\end{document}")

    path = os.path.join(output_dir, "sample.tex")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"Wrote {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=f"Generate {COMPETITION_NAME} solver result statistics, plots, and model-validation tables")
    parser.add_argument("data_dir",   help="Directory containing solver result XML files")
    parser.add_argument("output_dir", help="Output directory for tables, plots, and CSV")
    parser.add_argument(
        "--benchmarks-dir", default=None, metavar="DIR",
        help="Path to benchmark directory (chc-comp26-benchmarks). "
             "When provided, a dissent/inconsistency table is generated from "
             "the majority_vote_verdict fields in the benchmark .yml files.")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    hc_set = read_hors_concours()

    print("Computing statistics from XML result files...")
    stats, cactus_data, categories, cat_sizes, solved_benches = (
        compute_statistics(args.data_dir))
    print(f"Discovered categories: {', '.join(categories)}")
    print(f"Discovered solvers:    {', '.join(sorted(stats.keys()))}")

    print("\nGenerating LaTeX tables...")
    overall_rows = generate_latex_overall(stats, categories, args.output_dir, hc_set)
    generate_latex_per_category(stats, cat_sizes, categories, args.output_dir, hc_set)

    print("\nGenerating CSV...")
    generate_csv(stats, categories, cat_sizes, args.output_dir)

    print("\nGenerating cactus plots...")
    generate_cactus_plots(cactus_data, categories, cat_sizes, args.output_dir, hc_set)

    print("\nGenerating text summary...")
    generate_text_summary(stats, categories, cat_sizes, overall_rows, args.output_dir, hc_set)

    print("\nGenerating LaTeX macros...")
    generate_latex_macros(stats, categories, cat_sizes, overall_rows,
                          solved_benches, args.output_dir, hc_set)

    has_dissent = False
    if args.benchmarks_dir:
        print("\nGenerating dissent/inconsistency table...")
        dissent_stats = compute_dissent_stats(args.data_dir, args.benchmarks_dir)
        generate_latex_dissent_table(dissent_stats, categories, args.output_dir, hc_set)
        has_dissent = True

    print("\nParsing model validation results...")
    n_val_groups = run_model_validation(args.data_dir, args.output_dir, hc_set)
    if n_val_groups == 0:
        print("  No model-validation files found; skipping model-validation tables.")

    print("\nGenerating sample LaTeX document...")
    generate_sample_latex(categories, args.output_dir,
                          has_dissent=has_dissent, n_val_groups=n_val_groups)


if __name__ == "__main__":
    main()
