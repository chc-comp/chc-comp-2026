#!/usr/bin/env python3
"""Shared configuration for CHC-COMP 2026 scripts.

Import this module from other scripts to get common configuration such as
category lists, solver display names, cactus-plot colours, tool-track
assignments, result-file discovery patterns, and helper functions.
"""

import glob
import os
import re


# ─────────────────────────────────────────────────────────────────────────────
# Competition metadata
# ─────────────────────────────────────────────────────────────────────────────

COMPETITION_NAME = "CHC-COMP 2026"
RESULTS_TAG = "CHC-COMP2026_check-sat"
BENCH_PREFIX_MARKER = "chc-comp26-benchmarks/"


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark categories
# ─────────────────────────────────────────────────────────────────────────────

# Official competition categories, in canonical order.
CATEGORIES = [
    "ADT-LIA-Arrays",
    "ADT-LIA",
    "BV",
    "BV-Lin",
    "LIA-Arrays",
    "LIA-Lin-Arrays",
    "LIA-Lin",
    "LIA",
    "LRA-Lin",
]

# How to split categories into groups for per-category LaTeX tables
# (keeps individual tables to a manageable length).
MODEL_VALIDATION_CAT_GROUPS = [
    ["ADT-LIA-Arrays", "ADT-LIA", "BV", "BV-Lin"],
    ["LIA-Arrays", "LIA-Lin-Arrays", "LIA-Lin", "LIA", "LRA-Lin"],
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool tracks
# ─────────────────────────────────────────────────────────────────────────────

# Path to the file listing hors concours tool basenames (one per line).
HORS_CONCOURS_FILE = "hors_concours.txt"

# Default directory for benchmark-defs templates (used by discover_tools).
BENCHMARK_DEFS_DIR = "benchmark-defs"


# ─────────────────────────────────────────────────────────────────────────────
# Display names (human-readable labels for tables and plots)
# ─────────────────────────────────────────────────────────────────────────────

SOLVER_DISPLAY = {
    "chococatalia": "ChocoCatalia",
    "eldarica":     "Eldarica",
    "golem":        "Golem",
    "loat":         "LoAT",
    "mucyc":        "muCYC",
    "pcsat":        "PCSat",
    "spacer":       "Spacer",
    "theta":        "Theta",
    "z4":           "Z4",
}

# LaTeX macro-name bases (no digits or underscores; used by generate-statistics.py
# and parse-model-validation.py when emitting \\newcommand macros).
SOLVER_LATEX_MACROS = {
    "chococatalia": "Chococatalia",
    "eldarica":     "Eldarica",
    "golem":        "Golem",
    "loat":         "Loat",
    "mucyc":        "Mucyc",
    "pcsat":        "Pcsat",
    "spacer":       "Spacer",
    "theta":        "Theta",
    "z4":           "ZFour",  # LaTeX command names may not contain digits
}


# ─────────────────────────────────────────────────────────────────────────────
# Cactus-plot colours (one distinct colour per plain verifier)
# ─────────────────────────────────────────────────────────────────────────────

SOLVER_COLORS = {
    "chococatalia": "#1f77b4",
    "eldarica":     "#ff7f0e",
    "golem":        "#2ca02c",
    "loat":         "#d62728",
    "mucyc":        "#9467bd",
    "pcsat":        "#8c564b",
    "spacer":       "#e377c2",
    "theta":        "#7f7f7f",
    "z4":           "#bcbd22",
}


# ─────────────────────────────────────────────────────────────────────────────
# Resource limits (must match benchmark-defs/*.xml.template)
# ─────────────────────────────────────────────────────────────────────────────

RESOURCE_LIMITS = {
    "timelimit":     "30 min",
    "hardtimelimit": "30 min",
    "cpuCores":      "8",
    "memlimit":      "30 GB",
}


# ─────────────────────────────────────────────────────────────────────────────
# Relabeling mode
# ─────────────────────────────────────────────────────────────────────────────

# When True (default), majority-vote-relabel.py computes the expected verdict
# by majority vote across solver result XMLs, writes the agreed verdict back
# into each benchmark's .yml file, and then updates expectedVerdict in the
# XML result files accordingly.
#
# When False, the benchmark .yml files are treated as the authoritative ground
# truth: the script reads expected_verdict directly from each .yml and only
# updates the XML result files to match.  No .yml files are written.
# Use this mode after the benchmark set has already been curated (e.g., after
# a previous voting run or a manual correction pass).
RELABEL_BY_MAJORITY_VOTE = False


# ─────────────────────────────────────────────────────────────────────────────
# Statistics toggle
# ─────────────────────────────────────────────────────────────────────────────

# When True, tables and statistics for the solver track also include the *raw*
# (non-validated) model-generation results of model-generating verifiers in
# addition to their validated/-fixed results.
# Set to False (default) to show only definitively validated results.
INCLUDE_RAW_MODEL_RESULTS = False


# ─────────────────────────────────────────────────────────────────────────────
# Result-file discovery patterns
# ─────────────────────────────────────────────────────────────────────────────
#
# BenchExec result files follow the naming convention:
#   {tool}.{timestamp}.results.{RESULTS_TAG}[.{category}].xml        – plain solver
#   {tool}-model.{timestamp}.results.{RESULTS_TAG}[.{category}].xml  – model generation
#   {tool}-fixed.results.{RESULTS_TAG}[.{category}].xml              – post-validation
#   {val}-validate-{tool}-models.{timestamp}.results.{RESULTS_TAG}.. – validator
#
# All toolnames are lowercase alphanumeric (first character a letter).

_TAG = re.escape(RESULTS_TAG)

# Plain solver result files  (e.g. "eldarica.2026-05-03_09-42-24.results...")
PLAIN_RESULT_RE = re.compile(
    r"^([a-z][a-z0-9]*)"
    r"\.\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}"
    r"\.results\." + _TAG + r"(?:\.([^.]+))?\.xml$"
)

# Model-generation result files  (e.g. "theta-model.2026-05-09_23-56-50.results...")
MODEL_GEN_RE = re.compile(
    r"^([a-z][a-z0-9]*)-model"
    r"\.\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}"
    r"\.results\." + _TAG + r"(?:\.([^.]+))?\.xml$"
)

# Post-validation fixed results  (e.g. "eldarica-fixed.results...")
FIXED_RE = re.compile(
    r"^([a-z][a-z0-9]*)-fixed"
    r"\.results\." + _TAG + r"(?:\.([^.]+))?\.xml$"
)

# Validator result files  (e.g. "cvc5-validate-eldarica-models.2026-05-13_20-30-04.results...")
VALIDATOR_RE = re.compile(
    r"^([a-z][a-z0-9]*)-validate-([a-z][a-z0-9]*)-models"
    r"\.\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}"
    r"\.results\." + _TAG + r"(?:\.([^.]+))?\.xml$"
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper functions
# ─────────────────────────────────────────────────────────────────────────────

def discover_tools(benchmark_defs_dir=None):
    """Discover tool tracks from *.xml.template files in *benchmark_defs_dir*.

    Template naming follows the same convention as the Makefile:
      TOOL.xml.template              → plain verifier
      TOOL-model.xml.template        → model verifier (produces SAT witnesses)
      TOOL-validation.xml.template   → validator (checks SAT witnesses)

    Returns (plain_verifiers, model_verifiers, validators) as sorted lists of
    tool basenames (the stem before the first hyphen-suffix or .xml.template).
    """
    if benchmark_defs_dir is None:
        benchmark_defs_dir = BENCHMARK_DEFS_DIR
    plain = []
    model = []
    validators = []
    for path in sorted(glob.glob(
            os.path.join(benchmark_defs_dir, "*.xml.template"))):
        stem = os.path.basename(path)[:-len(".xml.template")]
        if stem.endswith("-validation"):
            validators.append(stem[:-len("-validation")])
        elif stem.endswith("-model"):
            model.append(stem[:-len("-model")])
        else:
            plain.append(stem)
    return sorted(plain), sorted(model), sorted(validators)


def normalize_bench_path(name):
    """Extract the benchmark-relative path from an XML run name attribute.

    Example:
        '../../../chc-comp26-benchmarks/foo/bar.yml'  →  'foo/bar.yml'
    """
    idx = name.find(BENCH_PREFIX_MARKER)
    if idx >= 0:
        return name[idx + len(BENCH_PREFIX_MARKER):]
    return name


def tex_escape(text):
    """Escape LaTeX special characters (underscore) in a display string."""
    return text.replace("_", "\\_")


def read_hors_concours(path=None):
    """Return the set of hors concours tool basenames from *path*.

    Lines starting with '#' and blank lines are ignored.
    Returns an empty set when the file does not exist.
    """
    if path is None:
        path = HORS_CONCOURS_FILE
    if not os.path.exists(path):
        return set()
    with open(path) as fh:
        return {line.strip() for line in fh
                if line.strip() and not line.strip().startswith("#")}


def solver_label_tex(solver, hc_set):
    """Return a LaTeX-safe display name, wrapped in \\textit{} if hors concours."""
    display = tex_escape(SOLVER_DISPLAY.get(solver, solver.title()))
    if solver in hc_set:
        return r"\textit{" + display + r"}"
    return display


def italicise_if_hc(text, solver, hc_set):
    """Wrap *text* in \\textit{} when *solver* is hors concours."""
    if solver in hc_set:
        return r"\textit{" + text + r"}"
    return text


def solver_linestyle(solver, hc_set):
    """Return a matplotlib linestyle: dashed for hors concours, solid otherwise."""
    return "--" if solver in hc_set else "-"


def solver_label_plot(solver, hc_set):
    """Return a matplotlib legend label, in mathtext italic if hors concours."""
    display = SOLVER_DISPLAY.get(solver, solver.title())
    if solver in hc_set:
        return r"$\mathit{" + display + r"}$"
    return display
