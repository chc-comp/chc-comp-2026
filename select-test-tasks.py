#!/usr/bin/env python3
"""Select a random, verdict-balanced subset of tasks from a BenchExec .set file.

Usage: select-test-tasks.py <set-file> <benchmark-base-dir> [max-tasks]

Reads a .set file (lines containing paths to .yml task files), randomly selects
up to max-tasks (default 5) entries, ensuring at least one task with
expected_verdict: true and at least one with expected_verdict: false are included,
provided the set file contains both kinds.  Rewrites the .set file in-place.
"""

import os
import random
import re
import sys


def get_verdict(yml_path: str) -> str | None:
    """Return 'true', 'false', or None if undetermined / file unreadable."""
    try:
        with open(yml_path) as f:
            content = f.read()
        m = re.search(r"expected_verdict:\s*(true|false)", content)
        return m.group(1) if m else None
    except OSError:
        return None


def select_tasks(set_file: str, base_dir: str, n: int = 5) -> None:
    with open(set_file) as f:
        all_lines = [line.strip() for line in f if line.strip()]

    if len(all_lines) <= n:
        # Nothing to trim – keep the file as-is.
        return

    verdicts = [get_verdict(os.path.join(base_dir, line)) for line in all_lines]

    true_idx = [i for i, v in enumerate(verdicts) if v == "true"]
    false_idx = [i for i, v in enumerate(verdicts) if v == "false"]

    if true_idx and false_idx:
        # Guarantee at least one representative from each verdict class.
        ti = random.choice(true_idx)
        fi = random.choice(false_idx)
        seed = {ti, fi}
        remaining = [i for i in range(len(all_lines)) if i not in seed]
        random.shuffle(remaining)
        chosen = list(seed) + remaining[: n - 2]
    else:
        # Cannot satisfy the balance constraint; fall back to plain random sample.
        chosen = random.sample(range(len(all_lines)), n)

    selected = [all_lines[i] for i in chosen]

    with open(set_file, "w") as f:
        for line in selected:
            f.write(line + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    set_file_arg = sys.argv[1]
    base_dir_arg = sys.argv[2]
    max_tasks = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    select_tasks(set_file_arg, base_dir_arg, max_tasks)
