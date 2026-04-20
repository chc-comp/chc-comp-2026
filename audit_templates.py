#!/usr/bin/env python3
"""Audit benchmark-defs XML templates.

Checks:
  1. All .xml.template files are well-formed XML matching the declared DTD.
  2. All -model.xml.template files have expectedverdict="true" on every
     <propertyfile> tag.
  3. Produces a Markdown participation table (tools × categories × options).

Exit code 0 if all checks pass, 1 otherwise.
"""

import glob
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


def validate_dtd(template_dir, dtd_path):
    """Validate every .xml.template against its declared DTD using xmllint."""
    errors = []
    templates = sorted(glob.glob(os.path.join(template_dir, '*.xml.template')))
    for path in templates:
        name = os.path.basename(path)
        result = subprocess.run(
            ['xmllint', '--noout', '--dtdvalid', dtd_path, path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            errors.append((name, result.stderr.strip()))
    return errors


EXPECTED_LIMITS = {
    'timelimit': '30 min',
    'hardtimelimit': '30 min',
    'cpuCores': '8',
    'memlimit': '30 GB',
}


def check_resource_limits(template_dir):
    """Check that all verifier templates have the expected resource limits."""
    errors = []
    for path in sorted(glob.glob(
            os.path.join(template_dir, '*.xml.template'))):
        name = os.path.basename(path)
        if name.endswith('-validation.xml.template'):
            continue
        tree = ET.parse(path)
        root = tree.getroot()
        for attr, expected in EXPECTED_LIMITS.items():
            actual = root.get(attr)
            if actual != expected:
                errors.append((
                    name,
                    f'{attr}="{actual}" (expected "{expected}")'
                ))
    return errors


def check_model_expected_verdicts(template_dir):
    """Check that -model.xml.template files have expectedverdict="true"."""
    errors = []
    for path in sorted(glob.glob(
            os.path.join(template_dir, '*-model.xml.template'))):
        name = os.path.basename(path)
        tree = ET.parse(path)
        root = tree.getroot()
        for tasks in root.iter('tasks'):
            task_name = tasks.get('name', '?')
            for pf in tasks.findall('propertyfile'):
                verdict = pf.get('expectedverdict')
                if verdict != 'true':
                    errors.append((
                        name,
                        f'tasks "{task_name}": expectedverdict='
                        f'"{verdict}" (expected "true")'
                    ))
    return errors


def build_participation_table(template_dir):
    """Build a Markdown table of tool participation.

    Returns (markdown_string, all_categories_sorted).
    """
    templates = sorted(glob.glob(
        os.path.join(template_dir, '*.xml.template')))

    # Collect data: {(tool, track): {category: options_list}}
    entries = []
    all_categories = set()

    for path in templates:
        basename = os.path.basename(path)
        stem = basename.replace('.xml.template', '')

        # Determine track
        if stem.endswith('-validation'):
            track = 'validator'
        elif stem.endswith('-model'):
            track = 'model'
        else:
            track = 'solver'

        tree = ET.parse(path)
        root = tree.getroot()

        tool_attr = root.get('tool', stem)
        display = root.get('displayName', '')

        # Global options (direct children of <benchmark> or <rundefinition>)
        global_opts = []
        for opt in root.findall('option'):
            opt_text = opt.text.strip() if opt.text else ''
            opt_name = opt.get('name', '')
            if opt_text:
                global_opts.append(opt_text)
            elif opt_name:
                global_opts.append(opt_name)

        for rd in root.findall('rundefinition'):
            for opt in rd.findall('option'):
                opt_text = opt.text.strip() if opt.text else ''
                opt_name = opt.get('name', '')
                if opt_text:
                    global_opts.append(opt_text)
                elif opt_name:
                    global_opts.append(opt_name)

        categories = {}
        for tasks in root.iter('tasks'):
            cat = tasks.get('name', '?')
            all_categories.add(cat)
            # Per-task options
            task_opts = list(global_opts)
            for opt in tasks.findall('option'):
                opt_text = opt.text.strip() if opt.text else ''
                opt_name = opt.get('name', '')
                if opt_text:
                    task_opts.append(opt_text)
                elif opt_name:
                    task_opts.append(opt_name)
            categories[cat] = task_opts

        tool_label = display if display else tool_attr
        entries.append((stem, tool_label, track, categories))

    cats = sorted(all_categories)

    # Build markdown table
    lines = []
    header = '| Template | Tool | Track | ' + ' | '.join(cats) + ' |'
    sep = '|' + '|'.join(['---'] * (3 + len(cats))) + '|'
    lines.append(header)
    lines.append(sep)

    for stem, tool_label, track, categories in entries:
        row = [f'`{stem}`', tool_label, track]
        for cat in cats:
            if cat in categories:
                opts = categories[cat]
                if opts:
                    # Filter out model-dir placeholders for readability
                    display_opts = [o for o in opts
                                    if '||MODELS-DIR||' not in o]
                    cell = ' '.join(f'`{o}`' for o in display_opts) if display_opts else '✓'
                else:
                    cell = '✓'
            else:
                cell = ''
            row.append(cell)
        lines.append('| ' + ' | '.join(row) + ' |')

    return '\n'.join(lines)


DEFAULT_DTD = os.path.join('benchexec', 'doc', 'benchmark.dtd')


def main():
    template_dir = sys.argv[1] if len(sys.argv) > 1 else 'benchmark-defs'
    dtd_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DTD
    has_errors = False

    # 1. DTD validation
    print('## DTD Validation\n')
    if not os.path.isfile(dtd_path):
        print(f'**SKIP** DTD file not found: `{dtd_path}`\n')
    else:
        dtd_errors = validate_dtd(template_dir, dtd_path)
        if dtd_errors:
            has_errors = True
            for name, err in dtd_errors:
                print(f'**FAIL** `{name}`:\n```\n{err}\n```\n')
        else:
            print('All templates pass DTD validation.\n')

    # 2. Resource limits check
    print('## Resource Limits Check\n')
    limit_errors = check_resource_limits(template_dir)
    if limit_errors:
        has_errors = True
        for name, msg in limit_errors:
            print(f'- **FAIL** `{name}`: {msg}')
        print()
    else:
        print('All verifier templates have correct resource limits.\n')

    # 3. Model expectedverdict check
    print('## Model Template expectedverdict Check\n')
    verdict_errors = check_model_expected_verdicts(template_dir)
    if verdict_errors:
        has_errors = True
        for name, msg in verdict_errors:
            print(f'- **FAIL** `{name}`: {msg}')
        print()
    else:
        print('All model templates have `expectedverdict="true"` on every '
              '`<propertyfile>`.\n')

    # 4. Participation table
    print('## Tool Participation\n')
    print(build_participation_table(template_dir))
    print()

    sys.exit(1 if has_errors else 0)


if __name__ == '__main__':
    main()
