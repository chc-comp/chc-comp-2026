#!/usr/bin/env python3
"""Generate enhanced index.html for CHC-COMP results.

Creates a grid-based index page with:
- Solver track (plain verifiers) and Model track (model verifiers) sections
- Tools × categories grid with correct/wrong/total summary links
- Overall per-tool columns
- Cross-verifier table links in column headers
"""

import argparse
import glob
import os
import xml.etree.ElementTree as ET


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate index page for CHC-COMP results"
    )
    parser.add_argument('--results-dir', default='results')
    parser.add_argument('--tables-dir', default='results/tables')
    parser.add_argument('--output', default='results/pages/tables/index.html')
    parser.add_argument('--model-verifiers', nargs='*', default=[])
    parser.add_argument('--plain-verifiers', nargs='*', default=[])
    return parser.parse_args()


def find_latest_xml(results_dir, pattern, tool_prefix=None):
    """Find the latest XML file matching a glob pattern.

    If tool_prefix is given, only include files whose basename starts with
    that exact prefix (e.g., 'spacer.' won't match 'spacer-model.').
    """
    files = sorted(glob.glob(os.path.join(results_dir, pattern)))
    if tool_prefix:
        files = [f for f in files
                 if os.path.basename(f).startswith(tool_prefix)]
    return files[-1] if files else None


def extract_counts(xml_path):
    """Extract correct/wrong/total counts from an XML result file."""
    if not xml_path or not os.path.exists(xml_path):
        return None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        correct = 0
        wrong = 0
        total = 0
        for run in root.findall('run'):
            total += 1
            for col in run.findall('column'):
                if col.get('title') == 'category':
                    val = col.get('value', '')
                    if val == 'correct':
                        correct += 1
                    elif val == 'wrong':
                        wrong += 1
        return correct, wrong, total
    except Exception as e:
        print(f"WARNING: Failed to parse {xml_path}: {e}")
        return None


def find_table_html(tables_dir, name, prefer_multi=False):
    """Find the actual HTML file for a table name.

    BenchExec table-generator produces .table.html for multi-input tables
    and .html for single-input tables.  When prefer_multi is True (model
    track with validators), check .table.html first; otherwise prefer
    the single-input .html to avoid picking up a stale model+validator
    table for a plain verifier.
    """
    order = ['.table.html', '.html'] if prefer_multi else ['.html', '.table.html']
    for suffix in order:
        path = os.path.join(tables_dir, name + suffix)
        if os.path.exists(path):
            return name + suffix
    return None


def discover_categories(results_dir):
    """Discover all benchmark categories from XML result files."""
    categories = set()
    for f in glob.glob(os.path.join(results_dir, '*results.CHC-COMP2026_check-sat.*.xml')):
        basename = os.path.basename(f)
        parts = basename.split('.CHC-COMP2026_check-sat.')
        if len(parts) == 2:
            cat = parts[1].replace('.xml', '')
            if cat:
                categories.add(cat)
    return sorted(categories)


def get_tool_categories(results_dir, tool_basename, is_model=False):
    """Get the set of categories a tool has results for."""
    if is_model:
        prefix = f'{tool_basename}-model.'
    else:
        prefix = f'{tool_basename}.'
    pattern = f'{prefix}*results.CHC-COMP2026_check-sat.*.xml'
    categories = set()
    for f in glob.glob(os.path.join(results_dir, pattern)):
        basename = os.path.basename(f)
        if not basename.startswith(prefix):
            continue
        parts = basename.split('.CHC-COMP2026_check-sat.')
        if len(parts) == 2:
            cat = parts[1].replace('.xml', '')
            if cat:
                categories.add(cat)
    return categories


def get_result_xml(results_dir, tool_basename, category, is_model=False):
    """Find the result XML for a tool + category."""
    if is_model:
        # Use fixed (validated) results if available
        fixed = os.path.join(
            results_dir,
            f'{tool_basename}-fixed.results.CHC-COMP2026_check-sat.{category}.xml'
        )
        if os.path.exists(fixed):
            return fixed
        # Fall back to raw model results
        return find_latest_xml(
            results_dir,
            f'{tool_basename}-model.*results.CHC-COMP2026_check-sat.{category}.xml',
            tool_prefix=f'{tool_basename}-model.'
        )
    else:
        return find_latest_xml(
            results_dir,
            f'{tool_basename}.*results.CHC-COMP2026_check-sat.{category}.xml',
            tool_prefix=f'{tool_basename}.'
        )


def get_overall_xml(results_dir, tool_basename, is_model=False):
    """Find the overall (all categories) result XML for a tool."""
    if is_model:
        fixed = os.path.join(
            results_dir,
            f'{tool_basename}-fixed.results.CHC-COMP2026_check-sat.xml'
        )
        if os.path.exists(fixed):
            return fixed
        return find_latest_xml(
            results_dir,
            f'{tool_basename}-model.*results.CHC-COMP2026_check-sat.xml',
            tool_prefix=f'{tool_basename}-model.'
        )
    else:
        return find_latest_xml(
            results_dir,
            f'{tool_basename}.*results.CHC-COMP2026_check-sat.xml',
            tool_prefix=f'{tool_basename}.'
        )


def format_counts(counts):
    """Format (correct, wrong, total) as a display string."""
    if counts is None:
        return '-'
    correct, wrong, total = counts
    return f'{correct} / {wrong} / {total}'


def generate_grid(html, tools, categories, results_dir, tables_dir,
                  is_model, cross_prefix):
    """Generate an HTML table grid for a track."""
    html.append('<table>')

    # Header row
    html.append('<tr><th>Tool</th>')
    for cat in categories:
        cross_file = find_table_html(tables_dir, f'results-{cat}-{cross_prefix}',
                                     prefer_multi=True)
        if cross_file:
            html.append(f'<th><a href="{cross_file}">{cat}</a></th>')
        else:
            html.append(f'<th>{cat}</th>')
    html.append('<th>Overall</th>')
    html.append('</tr>')

    # Sub-header row explaining columns
    html.append('<tr><td></td>')
    for _ in categories:
        html.append('<td style="font-size:0.8em;color:#666">correct / wrong / total</td>')
    html.append('<td style="font-size:0.8em;color:#666">correct / wrong / total</td>')
    html.append('</tr>')

    # Determine table name prefix for per-verifier links
    table_suffix = '-model' if is_model else ''

    # Tool rows
    for tool in sorted(tools):
        tool_cats = get_tool_categories(results_dir, tool, is_model=is_model)
        html.append(f'<tr><td>{tool}</td>')

        for cat in categories:
            if cat not in tool_cats:
                html.append('<td class="no-data">-</td>')
                continue

            xml_path = get_result_xml(results_dir, tool, cat, is_model=is_model)
            counts = extract_counts(xml_path)
            table_file = find_table_html(
                tables_dir, f'results-{tool}{table_suffix}-{cat}',
                prefer_multi=is_model)
            cell_text = format_counts(counts)

            if table_file:
                html.append(f'<td><a href="{table_file}">{cell_text}</a></td>')
            else:
                html.append(f'<td>{cell_text}</td>')

        # Overall column
        overall_xml = get_overall_xml(results_dir, tool, is_model=is_model)
        overall_counts = extract_counts(overall_xml)
        overall_file = find_table_html(
            tables_dir, f'results-{tool}{table_suffix}-overall',
            prefer_multi=is_model)
        overall_text = format_counts(overall_counts)

        if overall_file:
            html.append(f'<td><a href="{overall_file}">{overall_text}</a></td>')
        else:
            html.append(f'<td>{overall_text}</td>')

        html.append('</tr>')

    html.append('</table>')


def generate_html(args):
    results_dir = args.results_dir
    tables_dir = args.tables_dir
    model_verifiers = args.model_verifiers
    plain_verifiers = args.plain_verifiers

    categories = discover_categories(results_dir)

    html = []
    html.append('<!DOCTYPE html>')
    html.append('<html lang="en"><head><meta charset="utf-8">')
    html.append('<title>CHC-COMP 2025 Results</title>')
    html.append('<style>')
    html.append("""
body { font-family: sans-serif; max-width: 1400px; margin: 2em auto; padding: 0 1em; }
h1 { border-bottom: 2px solid #333; padding-bottom: .3em; }
h2 { margin-top: 1.5em; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: center; white-space: nowrap; }
th { background: #f5f5f5; }
td:first-child, th:first-child { text-align: left; font-weight: bold; }
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
.no-data { color: #999; }
""".strip())
    html.append('</style>')
    html.append('</head><body>')
    html.append('<h1>CHC-COMP 2025 Results</h1>')
    html.append('<p>Each cell shows <em>correct / wrong / total</em> task counts. '
                'Click to view the detailed table. '
                'Category headers link to cross-verifier comparison tables.</p>')

    # --- Solver Track ---
    if plain_verifiers:
        html.append('<h2>Solver Track (check-sat)</h2>')
        generate_grid(html, plain_verifiers, categories, results_dir,
                      tables_dir, is_model=False, cross_prefix='solver')

    # --- Model Track ---
    if model_verifiers:
        html.append('<h2>Model Track (check-sat with model generation)</h2>')
        generate_grid(html, model_verifiers, categories, results_dir,
                      tables_dir, is_model=True, cross_prefix='model')

    html.append('</body></html>')

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        f.write('\n'.join(html))

    print(f"Index page written to {args.output}")


def main():
    args = parse_args()
    generate_html(args)


if __name__ == '__main__':
    main()
