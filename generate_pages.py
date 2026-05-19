#!/usr/bin/env python3
"""Generate enhanced index.html for CHC-COMP results.

Creates a grid-based index page with:
- Solver track (plain verifiers) and Model track (model verifiers) sections
- Tools × categories grid with score + correct/wrong/total summary links
- Overall per-tool columns linking to overall cross-verifier tables
- Cross-verifier table links in column headers
- Dynamic scoring with gold/silver/bronze medal rankings
"""

import argparse
import glob
import os
import xml.etree.ElementTree as ET

from configs import read_hors_concours


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


# ---------------------------------------------------------------------------
# JavaScript helpers embedded in the page
# ---------------------------------------------------------------------------

SCORING_JS = r"""
window.addEventListener('load', function() {
  var select = document.getElementById('scoring-mode');

  function calcScore(correct, wrong, mode) {
    if (mode === 'punish') return correct - 64 * wrong;
    if (mode === 'assume') return correct + wrong;
    return correct; // 'ignore'
  }

  function updateAll() {
    var mode = select.value;

    // Update score values in every cell
    document.querySelectorAll('.score-cell').forEach(function(cell) {
      var correct = parseInt(cell.getAttribute('data-correct'), 10);
      var wrong   = parseInt(cell.getAttribute('data-wrong'),   10);
      cell.querySelector('.score-value').textContent = calcScore(correct, wrong, mode);
    });

    // Build column → [cells] map
    var colMap = {};
    document.querySelectorAll('.score-cell').forEach(function(c) {
      var col = c.getAttribute('data-col-id');
      if (!colMap[col]) colMap[col] = [];
      colMap[col].push(c);
    });

    // Rank per column; hors-concours cells are excluded from ranking
    var MEDALS = ['\uD83E\uDD47', '\uD83E\uDD48', '\uD83E\uDD49'];
    Object.keys(colMap).forEach(function(colId) {
      var cells = colMap[colId];
      var eligibleScores = cells
        .filter(function(c) { return c.getAttribute('data-hc') !== 'true'; })
        .map(function(c) {
          return calcScore(
            parseInt(c.getAttribute('data-correct'), 10),
            parseInt(c.getAttribute('data-wrong'),   10), mode);
        })
        .sort(function(a, b) { return b - a; });

      cells.forEach(function(cell) {
        var medalSpan = cell.querySelector('.medal');
        if (cell.getAttribute('data-hc') === 'true') {
          medalSpan.textContent = '';
          return;
        }
        var score = calcScore(
          parseInt(cell.getAttribute('data-correct'), 10),
          parseInt(cell.getAttribute('data-wrong'),   10), mode);
        var rank = eligibleScores.indexOf(score);
        medalSpan.textContent = (score > 0 && rank >= 0 && rank < 3) ? MEDALS[rank] : '';
      });
    });
  }

  select.addEventListener('change', updateAll);
  updateAll();
});
"""

SCORING_INFO = (
    "Scoring options:\n"
    "• Ignore wrong (default): score = correct\n"
    "• Punish wrong: score = correct \u2212 64\u00d7wrong\n"
    "• Assume all correct: score = correct + wrong\n\n"
    "Rankings per column are awarded dynamically based on the selected score. "
    "Only solvers with score > 0 receive medals. "
    "Hors concours solvers are excluded from medals."
)

HC_INFO = (
    "This solver did not officially enter the competition. "
    "It was included by the organizers to provide meaningful "
    "context for other participants. "
    "It is excluded from medal rankings."
)


def cell_data_attrs(counts):
    """Return data-correct / data-wrong attributes string for a score cell."""
    if counts is None:
        return None
    correct, wrong, _ = counts
    return f'data-correct="{correct}" data-wrong="{wrong}"'


def generate_grid(html, tools, categories, results_dir, tables_dir,
                  is_model, cross_prefix, track_id, hc_tools=()):
    """Generate an HTML table grid for a track.

    track_id is a short unique string used to namespace column IDs so that
    medals are ranked independently between the solver and model tracks.
    hc_tools is the set of hors concours tool basenames.
    """
    sorted_tools = sorted(tools)
    html.append('<table>')

    # Header row
    html.append('<tr><th>Tool</th>')
    for cat in categories:
        col_id = f'{track_id}-{cat}'
        cross_file = find_table_html(tables_dir, f'results-{cat}-{cross_prefix}',
                                     prefer_multi=True)
        if cross_file:
            html.append(
                f'<th data-col-id="{col_id}">'
                f'<a href="{cross_file}">{cat}</a></th>')
        else:
            html.append(f'<th data-col-id="{col_id}">{cat}</th>')
    # Overall column header — link to cross-verifier overall table
    overall_col_id = f'{track_id}-overall'
    overall_cross_file = find_table_html(
        tables_dir, f'results-overall-{cross_prefix}', prefer_multi=True)
    if overall_cross_file:
        html.append(
            f'<th data-col-id="{overall_col_id}">'
            f'<a href="{overall_cross_file}">Overall</a></th>')
    else:
        html.append(f'<th data-col-id="{overall_col_id}">Overall</th>')
    html.append('</tr>')

    # Sub-header row explaining columns
    html.append('<tr><td></td>')
    for _ in categories:
        html.append('<td style="font-size:0.8em;color:#666">score&nbsp;/&nbsp;correct&nbsp;/&nbsp;wrong&nbsp;/&nbsp;total</td>')
    html.append('<td style="font-size:0.8em;color:#666">score&nbsp;/&nbsp;correct&nbsp;/&nbsp;wrong&nbsp;/&nbsp;total</td>')
    html.append('</tr>')

    # Determine table name suffix for per-verifier links
    table_suffix = '-model' if is_model else ''

    hc_info_escaped = HC_INFO.replace('"', '&quot;')

    # Tool rows
    for tool in sorted_tools:
        tool_cats = get_tool_categories(results_dir, tool, is_model=is_model)
        is_hc = tool in hc_tools

        if is_hc:
            name_cell = (
                f'<td>{tool}'
                f'<br><small class="hc-label">hors concours'
                f'&nbsp;<i class="info-icon" title="{hc_info_escaped}">i</i>'
                f'</small></td>'
            )
            html.append(f'<tr class="hors-concours">{name_cell}')
        else:
            html.append(f'<tr><td>{tool}</td>')

        for cat in categories:
            col_id = f'{track_id}-{cat}'
            if cat not in tool_cats:
                html.append('<td class="no-data">-</td>')
                continue

            xml_path = get_result_xml(results_dir, tool, cat, is_model=is_model)
            counts = extract_counts(xml_path)
            table_file = find_table_html(
                tables_dir, f'results-{tool}{table_suffix}-{cat}',
                prefer_multi=is_model)

            html.append(_render_cell(counts, table_file, col_id, is_hc=is_hc))

        # Overall column
        overall_col_id = f'{track_id}-overall'
        overall_xml = get_overall_xml(results_dir, tool, is_model=is_model)
        overall_counts = extract_counts(overall_xml)
        overall_file = find_table_html(
            tables_dir, f'results-{tool}{table_suffix}-overall',
            prefer_multi=is_model)
        html.append(_render_cell(overall_counts, overall_file, overall_col_id, is_hc=is_hc))

        html.append('</tr>')

    html.append('</table>')


def _render_cell(counts, table_file, col_id, is_hc=False):
    """Render a single result cell with score line + correct/wrong/total."""
    if counts is None:
        return '<td class="no-data">-</td>'
    correct, wrong, total = counts
    counts_str = f'{correct}&nbsp;/&nbsp;{wrong}&nbsp;/&nbsp;{total}'
    hc_attr = ' data-hc="true"' if is_hc else ''
    inner = (
        f'<span class="score-cell" data-col-id="{col_id}" '
        f'data-correct="{correct}" data-wrong="{wrong}"{hc_attr}>'
        f'<span class="medal"></span>'
        f'<span class="score-value"></span><br>'
        f'<span class="counts">{counts_str}</span>'
        f'</span>'
    )
    if table_file:
        return f'<td><a href="{table_file}">{inner}</a></td>'
    return f'<td>{inner}</td>'


def generate_html(args):
    results_dir = args.results_dir
    tables_dir = args.tables_dir
    model_verifiers = args.model_verifiers
    plain_verifiers = args.plain_verifiers

    categories = discover_categories(results_dir)
    hc_tools = read_hors_concours()

    html = []
    html.append('<!DOCTYPE html>')
    html.append('<html lang="en"><head><meta charset="utf-8">')
    html.append('<title>CHC-COMP 2026 Results</title>')
    html.append('<style>')
    html.append("""
body { font-family: sans-serif; max-width: 1600px; margin: 2em auto; padding: 0 1em; }
h1 { border-bottom: 2px solid #333; padding-bottom: .3em; }
h2 { margin-top: 1.5em; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: center; white-space: nowrap; }
th { background: #f5f5f5; }
td:first-child, th:first-child { text-align: left; font-weight: bold; }
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
.no-data { color: #999; }
.score-cell { display: inline-block; }
.score-value { font-weight: bold; font-size: 1.05em; }
.medal { font-size: 1.1em; margin-right: 2px; }
.counts { font-size: 0.85em; color: #555; }
.scoring-bar { display: flex; align-items: center; gap: 0.7em; margin: 1em 0 0.5em 0;
               background: #f8f8f8; border: 1px solid #ddd; border-radius: 6px;
               padding: 0.5em 1em; width: fit-content; }
.scoring-bar label { font-weight: bold; }
.scoring-bar select { font-size: 0.95em; padding: 2px 6px; }
.info-icon { display: inline-flex; align-items: center; justify-content: center;
             width: 1.3em; height: 1.3em; border-radius: 50%;
             background: #0366d6; color: white; font-size: 0.78em;
             cursor: help; font-style: normal; font-weight: bold;
             border: none; padding: 0; flex-shrink: 0; }
tr.hors-concours { font-style: italic; color: #555; }
tr.hors-concours td:first-child { font-weight: normal; }
.hc-label { font-size: 0.78em; color: #888; font-style: normal; }
.banner-uncertified {
  background: #fff3cd; border: 2px solid #f0ad4e; border-radius: 6px;
  padding: 0.7em 1.2em; margin-bottom: 1.2em;
  font-size: 1em; color: #856404;
  display: flex; align-items: center; gap: 0.6em;
}
.banner-uncertified .banner-icon { font-size: 1.4em; }
""".strip())
    html.append('</style>')
    html.append('</head><body>')
    html.append('<h1>CHC-COMP 2026 Results</h1>')
    html.append(
        '<div class="banner-uncertified">'
        '<span class="banner-icon">&#x26A0;&#xFE0F;</span>'
        '<strong>These results are preliminary and have not yet been certified.</strong>'
        '</div>')

    html.append(
        '<p>Each cell shows the <em>score</em> (bold) and '
        '<em>correct&nbsp;/&nbsp;wrong&nbsp;/&nbsp;total</em> task counts. '
        'Click a cell to view the detailed table. '
        'Category headers link to cross-verifier comparison tables.</p>')

    # Scoring dropdown (shared across all tracks)
    scoring_info_escaped = SCORING_INFO.replace('\n', '&#10;').replace('"', '&quot;')
    html.append('<div class="scoring-bar">')
    html.append('<label for="scoring-mode">Scoring:</label>')
    html.append(
        '<select id="scoring-mode">'
        '<option value="ignore">Ignore wrong results</option>'
        '<option value="punish">Punish wrong results</option>'
        '<option value="assume">Assume all correct</option>'
        '</select>')
    html.append(
        f'<i class="info-icon" title="{scoring_info_escaped}">i</i>')
    html.append('</div>')

    # --- Solver Track ---
    if plain_verifiers:
        html.append('<h2>Solver Track (check-sat)</h2>')
        generate_grid(html, plain_verifiers, categories, results_dir,
                      tables_dir, is_model=False, cross_prefix='solver',
                      track_id='solver', hc_tools=hc_tools)

    # --- Model Track ---
    if model_verifiers:
        html.append('<h2>Model Track (check-sat with model generation)</h2>')
        generate_grid(html, model_verifiers, categories, results_dir,
                      tables_dir, is_model=True, cross_prefix='model',
                      track_id='model', hc_tools=hc_tools)

    html.append(f'<script>{SCORING_JS}</script>')
    html.append('</body></html>')

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        f.write('\n'.join(html))

    print(f"Index page written to {args.output}")

    # Write root redirect page
    pages_dir = os.path.dirname(os.path.dirname(args.output))
    redirect_path = os.path.join(pages_dir, 'index.html')
    with open(redirect_path, 'w') as f:
        f.write(
            '<!DOCTYPE html>\n'
            '<html lang="en"><head><meta charset="utf-8">\n'
            '<meta http-equiv="refresh" content="0; url=tables/index.html">\n'
            '<title>CHC-COMP 2026 Results</title>\n'
            '</head><body>\n'
            '<p>Redirecting to <a href="tables/index.html">results</a>...</p>\n'
            '</body></html>\n'
        )
    print(f"Redirect page written to {redirect_path}")


def main():
    args = parse_args()
    generate_html(args)


if __name__ == '__main__':
    main()
