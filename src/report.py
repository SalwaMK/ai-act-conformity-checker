#!/usr/bin/env python3
"""
report.py — EU AI Act Conformity Report Generator

Usage:
    python src/report.py --results data/results_sample_compliant.json \
                         --provisions data/provisions.json

    python src/report.py --results data/results/sample_partial.json \
                         --provisions data/provisions.json \
                         --output reports/my_report.html

Produces an HTML report saved to reports/<sample_name>_report.html
(or a custom path if --output is specified).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Verdict styling
# ---------------------------------------------------------------------------

VERDICT_META: dict[str, dict[str, str]] = {
    "Met": {
        "color": "#16a34a",          # green-700
        "bg": "#dcfce7",             # green-100
        "border": "#86efac",         # green-300
        "icon": "✅",
        "label": "Met",
    },
    "Partial": {
        "color": "#d97706",          # amber-600
        "bg": "#fef9c3",             # yellow-100
        "border": "#fde047",         # yellow-300
        "icon": "⚠️",
        "label": "Partial",
    },
    "Not Met": {
        "color": "#dc2626",          # red-600
        "bg": "#fee2e2",             # red-100
        "border": "#fca5a5",         # red-300
        "icon": "❌",
        "label": "Not Met",
    },
    "No Evidence": {
        "color": "#6b7280",          # gray-500
        "bg": "#f3f4f6",             # gray-100
        "border": "#d1d5db",         # gray-300
        "icon": "🔍",
        "label": "No Evidence",
    },
}

# Canonical verdict order for summary tables
VERDICT_ORDER = ["Met", "Partial", "Not Met", "No Evidence"]

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> Any:
    """Load and return JSON from *path*, with a friendly error on failure."""
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        sys.exit(f"[report] ERROR: File not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"[report] ERROR: Invalid JSON in {path}: {exc}")


def build_provision_map(provisions: list[dict]) -> dict[str, dict]:
    """Return a mapping of provision_id → provision dict for fast lookup."""
    return {p["id"]: p for p in provisions}


# ---------------------------------------------------------------------------
# Grouping logic
# ---------------------------------------------------------------------------


def article_key(citation: str) -> str:
    """
    Extract a sortable article key from a citation string.

    Examples
    --------
    "Article 9(1)"            → "Article 9"
    "Article 13(3), point (a)"→ "Article 13"
    """
    match = re.match(r"(Article\s+\d+)", citation, re.IGNORECASE)
    return match.group(1) if match else citation


def article_sort_key(article: str) -> int:
    """Return the numeric part of 'Article N' for numeric sorting."""
    match = re.search(r"\d+", article)
    return int(match.group()) if match else 0


def group_results_by_article(
    results: list[dict],
) -> dict[str, list[dict]]:
    """Group result entries by their top-level article."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for entry in results:
        key = article_key(entry.get("citation", "Unknown"))
        groups[key].append(entry)
    # Sort groups numerically by article number
    return dict(
        sorted(groups.items(), key=lambda kv: article_sort_key(kv[0]))
    )


# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------


def compute_summary(results: list[dict]) -> dict[str, int]:
    """Return {verdict: count} across all results."""
    counts: dict[str, int] = {v: 0 for v in VERDICT_ORDER}
    for entry in results:
        v = entry.get("verdict", "No Evidence")
        counts[v] = counts.get(v, 0) + 1
    return counts


def overall_status(counts: dict[str, int]) -> tuple[str, str, str]:
    """
    Derive a single overall compliance status label, colour, and description.

    Returns (label, hex_color, description).
    """
    total = sum(counts.values())
    if total == 0:
        return "Unknown", "#6b7280", "No requirements evaluated."
    met = counts.get("Met", 0)
    partial = counts.get("Partial", 0)
    not_met = counts.get("Not Met", 0)
    no_ev = counts.get("No Evidence", 0)

    if not_met == 0 and no_ev == 0 and partial == 0:
        return "Fully Compliant", "#16a34a", "All requirements are met."
    if met == 0 and partial == 0:
        return "Non-Compliant", "#dc2626", "No requirements are satisfied."
    if not_met > 0 or no_ev > 0:
        return (
            "Partially Compliant",
            "#d97706",
            f"{met} met, {partial} partial, {not_met} not met, {no_ev} with no evidence.",
        )
    return "Largely Compliant", "#16a34a", f"{met} met, {partial} partial."


# ---------------------------------------------------------------------------
# HTML generation helpers
# ---------------------------------------------------------------------------

_HTML_ESCAPE_TABLE = str.maketrans(
    {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}
)


def esc(text: str | None) -> str:
    """HTML-escape a string, returning an empty string for None."""
    if text is None:
        return ""
    return str(text).translate(_HTML_ESCAPE_TABLE)


def verdict_badge(verdict: str) -> str:
    """Return an inline HTML badge for *verdict*."""
    meta = VERDICT_META.get(verdict, VERDICT_META["No Evidence"])
    return (
        f'<span class="badge" style="'
        f'color:{meta["color"]};'
        f'background:{meta["bg"]};'
        f'border:1px solid {meta["border"]};'
        f'">'
        f'{meta["icon"]} {esc(meta["label"])}'
        f"</span>"
    )


def confidence_bar(confidence: float | None) -> str:
    """Return an HTML progress bar representing *confidence* (0–1)."""
    if confidence is None:
        return "<em>N/A</em>"
    pct = max(0.0, min(1.0, float(confidence))) * 100
    color = "#16a34a" if pct >= 80 else "#d97706" if pct >= 50 else "#dc2626"
    return (
        f'<span class="conf-wrap" title="{pct:.0f}% confidence">'
        f'<span class="conf-bar" style="width:{pct:.0f}%;background:{color};"></span>'
        f'<span class="conf-label">{pct:.0f}%</span>'
        f"</span>"
    )


# ---------------------------------------------------------------------------
# Full HTML report assembly
# ---------------------------------------------------------------------------


def render_html(
    sample_name: str,
    results: list[dict],
    provisions: list[dict],
    generated_at: str,
) -> str:
    """Return a complete, self-contained HTML report as a string."""

    provision_map = build_provision_map(provisions)
    groups = group_results_by_article(results)
    counts = compute_summary(results)
    total = sum(counts.values())
    status_label, status_color, status_desc = overall_status(counts)

    # ------------------------------------------------------------------
    # verdict badge (updated for new CSS classes)
    # ------------------------------------------------------------------
    def _badge(verdict: str) -> str:
        cls_map = {"Met": "badge-met", "Partial": "badge-par",
                   "Not Met": "badge-not", "No Evidence": "badge-noev"}
        meta = VERDICT_META.get(verdict, VERDICT_META["No Evidence"])
        cls  = cls_map.get(verdict, "badge-noev")
        return f'<span class="badge {cls}">{meta["icon"]} {esc(meta["label"])}</span>'

    # confidence bar (updated)
    def _conf(confidence: float | None) -> str:
        if confidence is None:
            return '<span class="meta-item"><span class="meta-key">Conf</span> N/A</span>'
        pct   = max(0.0, min(1.0, float(confidence))) * 100
        color = "var(--met)" if pct >= 80 else "var(--partial)" if pct >= 50 else "var(--notmet)"
        return (
            f'<span class="meta-item">'
            f'<span class="meta-key">Conf</span>'
            f'<span class="conf-wrap">'
            f'<span class="conf-track"><span class="conf-fill" style="width:{pct:.0f}%;background:{color};"></span></span>'
            f'<span class="conf-val">{pct:.0f}%</span>'
            f'</span></span>'
        )

    # ------------------------------------------------------------------
    # Build article sections HTML
    # ------------------------------------------------------------------
    sections_html: list[str] = []
    for article, entries in groups.items():
        art_counts = compute_summary(entries)
        rows: list[str] = []

        for entry in entries:
            req_id      = esc(entry.get("requirement_id", ""))
            citation    = esc(entry.get("citation", ""))
            requirement = esc(entry.get("requirement", ""))
            verdict     = entry.get("verdict", "No Evidence")
            evidence    = entry.get("evidence_quote")
            confidence  = entry.get("confidence")
            reasoning   = esc(entry.get("reasoning", ""))

            evidence_cell = (
                f'<blockquote class="evidence">&ldquo;{esc(evidence)}&rdquo;</blockquote>'
                if evidence
                else '<span class="no-evidence">— no evidence quoted —</span>'
            )

            prov_id   = req_id.split("#")[0] if req_id else None
            provision = provision_map.get(prov_id, {}) if prov_id else {}
            prov_text = provision.get("full_text", "")
            prov_snippet = (
                f'<details class="prov-details"><summary>Provision text</summary>'
                f'<pre class="prov-text">{esc(prov_text)}</pre></details>'
                if prov_text else ""
            )

            rows.append(
                f"""
        <div class="req-card verdict-{verdict.lower().replace(" ", "-")}">
          <div class="req-top">
            <span class="req-citation">{citation}</span>
            {_badge(verdict)}
            <span class="req-id">{req_id}</span>
          </div>
          <p class="req-text">{requirement}</p>
          <div class="req-evidence">
            <div class="ev-label">Evidence</div>
            {evidence_cell}
          </div>
          <div class="req-footer">
            {_conf(confidence)}
            {"<span class='meta-item'><span class='meta-key'>Note</span> " + reasoning + "</span>" if reasoning else ""}
            {prov_snippet}
          </div>
        </div>"""
            )

        # Article-level chips
        chip_cls = {"Met": "c-met", "Partial": "c-par", "Not Met": "c-not", "No Evidence": "c-noev"}
        chips_html = "".join(
            f'<span class="art-chip {chip_cls[v]}">{VERDICT_META[v]["icon"]} {art_counts[v]}</span>'
            for v in VERDICT_ORDER if art_counts[v] > 0
        )

        sections_html.append(
            f"""
    <section class="article-section" id="{esc(article.lower().replace(' ', '-'))}">
      <div class="article-header">
        <h2 class="article-title">{esc(article)}</h2>
        <div class="article-chips">{chips_html}</div>
      </div>
      <div class="req-grid">
        {"".join(rows)}
      </div>
    </section>"""
        )

    # ------------------------------------------------------------------
    # Sidebar nav items
    # ------------------------------------------------------------------
    toc_items = "\n".join(
        f'<li><a href="#{esc(art.lower().replace(" ", "-"))}">{esc(art)}</a></li>'
        for art in groups
    )

    # ------------------------------------------------------------------
    # Final HTML
    # ------------------------------------------------------------------
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EU AI Act Conformity Report — {esc(sample_name)}</title>
  <meta name="description"
        content="EU AI Act conformity assessment report for {esc(sample_name)}.
                 Generated {esc(generated_at)}."/>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg:          #0f1117;
      --surface:     #181c27;
      --surface2:    #1e2333;
      --border:      #2a2f42;
      --border-soft: #232840;
      --text:        #e2e8f0;
      --text-muted:  #8892a4;
      --text-dim:    #55627a;
      --accent:      #3b82f6;
      --accent-glow: rgba(59,130,246,.18);
      --met:         #22c55e;  --met-bg:     rgba(34,197,94,.10);
      --partial:     #f59e0b;  --partial-bg: rgba(245,158,11,.10);
      --notmet:      #ef4444;  --notmet-bg:  rgba(239,68,68,.10);
      --noev:        #64748b;  --noev-bg:    rgba(100,116,139,.10);
      --radius-sm:   6px; --radius-md: 10px;
      --font:  'Inter', system-ui, sans-serif;
      --mono:  'JetBrains Mono', monospace;
      --shadow-md: 0 4px 16px rgba(0,0,0,.45);
      --transition: .18s cubic-bezier(.4,0,.2,1);
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; color-scheme: dark; }}
    body {{
      font-family: var(--font); font-size: 14px; line-height: 1.55;
      color: var(--text); background: var(--bg); -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* Layout */
    .shell {{
      display: grid;
      grid-template-columns: 210px 1fr;
      grid-template-rows: auto 1fr;
      min-height: 100vh;
    }}

    /* Banner */
    .banner {{
      grid-column: 1 / -1;
      background: linear-gradient(105deg, #0d1b3e 0%, #112048 45%, #1a1060 100%);
      border-bottom: 1px solid var(--border);
      padding: 1rem 1.75rem;
      display: flex; align-items: center; gap: 1rem;
    }}
    .banner-flag {{ font-size: 1.85rem; line-height: 1; flex-shrink: 0; }}
    .banner-body {{ flex: 1; min-width: 0; }}
    .banner h1 {{ font-size: .98rem; font-weight: 700; letter-spacing: -.01em; color: #fff; }}
    .banner-sub {{ font-size: .72rem; color: #7c8db5; margin-top: .08rem; }}
    .banner-sub strong {{ color: #a5b4fc; }}
    .status-chip {{
      display: inline-flex; align-items: center; gap: .32rem;
      padding: .26rem .72rem; border-radius: 999px;
      font-size: .68rem; font-weight: 700; letter-spacing: .04em;
      text-transform: uppercase; flex-shrink: 0;
    }}
    .status-chip::before {{
      content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor;
    }}

    /* Sidebar */
    .sidebar {{
      background: var(--surface); border-right: 1px solid var(--border);
      padding: 1rem 0 2rem; position: sticky; top: 0;
      height: 100vh; overflow-y: auto;
      scrollbar-width: thin; scrollbar-color: var(--border) transparent;
    }}
    .sidebar-section {{ margin-bottom: 1.35rem; }}
    .sidebar-label {{
      font-size: .59rem; font-weight: 700; letter-spacing: .13em;
      text-transform: uppercase; color: var(--text-dim); padding: 0 1rem; margin-bottom: .42rem;
    }}
    .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: .26rem; padding: 0 .72rem; }}
    .stat-pill {{
      display: flex; flex-direction: column; align-items: center; padding: .42rem .28rem;
      border-radius: var(--radius-sm); border: 1px solid var(--border-soft);
      background: var(--surface2); transition: border-color var(--transition);
    }}
    .stat-pill:hover {{ border-color: var(--c, var(--accent)); }}
    .stat-pill .stat-num {{ font-size: 1.05rem; font-weight: 700; line-height: 1; color: var(--c); }}
    .stat-pill .stat-lbl {{
      font-size: .56rem; font-weight: 600; letter-spacing: .05em;
      text-transform: uppercase; color: var(--text-dim); margin-top: .16rem;
    }}
    .stat-pill.s-met  {{ --c: var(--met);    }}
    .stat-pill.s-par  {{ --c: var(--partial); }}
    .stat-pill.s-not  {{ --c: var(--notmet);  }}
    .stat-pill.s-noev {{ --c: var(--noev);   }}
    .meter-track {{
      margin: .45rem .72rem 0; height: 4px; border-radius: 2px;
      background: var(--surface2); overflow: hidden; display: flex;
    }}
    .meter-seg {{ height: 100%; }}
    .nav-list {{ list-style: none; padding: 0 .42rem; }}
    .nav-list li {{ margin-bottom: 1px; }}
    .nav-list a {{
      display: block; padding: .24rem .58rem; border-radius: var(--radius-sm);
      font-size: .74rem; color: var(--text-muted);
      transition: background var(--transition), color var(--transition);
    }}
    .nav-list a:hover {{ background: var(--surface2); color: var(--text); text-decoration: none; }}

    /* Main */
    .main {{ padding: 1.35rem 1.55rem 4rem; min-width: 0; }}

    /* Article sections */
    .article-section {{ margin-bottom: 1.65rem; }}
    .article-header {{
      display: flex; align-items: center; gap: .55rem;
      margin-bottom: .45rem; padding-bottom: .42rem;
      border-bottom: 1px solid var(--border);
    }}
    .article-title {{ font-size: .87rem; font-weight: 700; color: var(--text); letter-spacing: -.01em; }}
    .article-chips {{ display: flex; gap: .2rem; flex-wrap: wrap; margin-left: auto; }}
    .art-chip {{ font-size: .61rem; font-weight: 700; padding: .09rem .36rem; border-radius: 999px; }}
    .art-chip.c-met  {{ color: var(--met);    background: var(--met-bg);    }}
    .art-chip.c-par  {{ color: var(--partial); background: var(--partial-bg); }}
    .art-chip.c-not  {{ color: var(--notmet);  background: var(--notmet-bg);  }}
    .art-chip.c-noev {{ color: var(--noev);   background: var(--noev-bg);    }}

    /* Requirement cards */
    .req-grid {{ display: grid; gap: .32rem; }}
    .req-card {{
      background: var(--surface); border: 1px solid var(--border-soft);
      border-left: 3px solid var(--noev); border-radius: var(--radius-md);
      padding: .52rem .72rem;
      transition: border-color var(--transition), box-shadow var(--transition), transform var(--transition);
    }}
    .req-card:hover {{
      border-color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent-glow), var(--shadow-md);
      transform: translateY(-1px);
    }}
    .req-card.verdict-met         {{ border-left-color: var(--met);    }}
    .req-card.verdict-partial     {{ border-left-color: var(--partial); }}
    .req-card.verdict-not-met     {{ border-left-color: var(--notmet);  }}
    .req-card.verdict-no-evidence {{ border-left-color: var(--noev);   }}
    .req-top {{ display: flex; align-items: center; gap: .38rem; flex-wrap: wrap; margin-bottom: .24rem; }}
    .req-citation {{ font-size: .66rem; font-weight: 600; color: var(--text-muted); font-family: var(--mono); }}
    .req-id {{ font-size: .59rem; color: var(--text-dim); font-family: var(--mono); margin-left: auto; }}
    .badge {{
      display: inline-flex; align-items: center; gap: .16rem;
      padding: .08rem .4rem; border-radius: 999px;
      font-size: .62rem; font-weight: 700; letter-spacing: .02em; flex-shrink: 0;
    }}
    .badge-met  {{ color: var(--met);    background: var(--met-bg);    }}
    .badge-par  {{ color: var(--partial); background: var(--partial-bg); }}
    .badge-not  {{ color: var(--notmet);  background: var(--notmet-bg);  }}
    .badge-noev {{ color: var(--noev);   background: var(--noev-bg);    }}
    .req-text {{ font-size: .79rem; color: var(--text); margin-bottom: .24rem; line-height: 1.42; }}
    .req-evidence {{ margin-bottom: .22rem; }}
    .ev-label {{
      font-size: .58rem; font-weight: 700; letter-spacing: .09em;
      text-transform: uppercase; color: var(--text-dim); margin-bottom: .12rem;
    }}
    blockquote.evidence {{
      border-left: 2px solid var(--border); padding: .22rem .48rem;
      background: var(--surface2); color: var(--text-muted);
      font-style: italic; font-size: .76rem;
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0; line-height: 1.4;
    }}
    .no-evidence {{ color: var(--text-dim); font-size: .72rem; font-style: italic; }}
    .req-footer {{ display: flex; align-items: center; flex-wrap: wrap; gap: .48rem; margin-top: .26rem; }}
    .meta-item {{ font-size: .69rem; color: var(--text-muted); display: flex; align-items: center; gap: .26rem; }}
    .meta-key {{ font-weight: 700; text-transform: uppercase; letter-spacing: .07em; font-size: .57rem; color: var(--text-dim); }}
    .conf-wrap {{ display: inline-flex; align-items: center; gap: .26rem; }}
    .conf-track {{ width: 46px; height: 3px; border-radius: 2px; background: var(--surface2); overflow: hidden; }}
    .conf-fill {{ height: 100%; border-radius: 2px; }}
    .conf-val {{ font-size: .64rem; color: var(--text-muted); }}
    .prov-details {{ margin-left: auto; }}
    .prov-details summary {{
      cursor: pointer; font-size: .65rem; color: var(--accent);
      user-select: none; list-style: none;
      display: inline-flex; align-items: center; gap: .18rem;
    }}
    .prov-details summary::marker,
    .prov-details summary::-webkit-details-marker {{ display: none; }}
    .prov-details summary::before {{
      content: '\203a'; font-size: .84rem;
      transition: transform var(--transition); display: inline-block;
    }}
    .prov-details[open] summary::before {{ transform: rotate(90deg); }}
    pre.prov-text {{
      margin-top: .35rem; background: var(--surface2); border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: .42rem .58rem;
      font-size: .67rem; font-family: var(--mono);
      white-space: pre-wrap; word-break: break-word; color: var(--text-muted);
      max-height: 120px; overflow-y: auto; scrollbar-width: thin;
    }}
    .page-footer {{
      text-align: center; font-size: .67rem; color: var(--text-dim);
      margin-top: 2.25rem; padding-top: .9rem; border-top: 1px solid var(--border);
    }}
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
    @media (max-width: 720px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .sidebar {{ display: none; }}
      .main {{ padding: .9rem .85rem 3rem; }}
      .req-id {{ display: none; }}
    }}
  </style>
</head>
<body>
<div class="shell">

  <header class="banner">
    <div class="banner-flag">🇪🇺</div>
    <div class="banner-body">
      <h1>EU AI Act — Conformity Assessment Report</h1>
      <p class="banner-sub">
        Sample: <strong>{esc(sample_name)}</strong>
        &nbsp;·&nbsp; {esc(generated_at)}
      </p>
    </div>
    <div class="status-chip" style="color:{status_color};background:color-mix(in srgb,{status_color} 12%,transparent);border:1px solid color-mix(in srgb,{status_color} 28%,transparent);">
      {status_label}
    </div>
  </header>

  <aside class="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-label">Overview</div>
      <div class="stat-grid">
        <div class="stat-pill s-met">
          <span class="stat-num">{counts["Met"]}</span>
          <span class="stat-lbl">Met</span>
        </div>
        <div class="stat-pill s-par">
          <span class="stat-num">{counts["Partial"]}</span>
          <span class="stat-lbl">Partial</span>
        </div>
        <div class="stat-pill s-not">
          <span class="stat-num">{counts["Not Met"]}</span>
          <span class="stat-lbl">Not Met</span>
        </div>
        <div class="stat-pill s-noev">
          <span class="stat-num">{counts["No Evidence"]}</span>
          <span class="stat-lbl">No Evid.</span>
        </div>
      </div>
      <div class="meter-track" title="{total} requirements">
        {"".join(
          f'<div class="meter-seg" style="width:{counts[v]/total*100:.2f}%;background:{VERDICT_META[v]["color"]};" title="{v}: {counts[v]}"></div>'
          for v in VERDICT_ORDER
          if total and counts[v]
        )}
      </div>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-label">Articles</div>
      <ul class="nav-list">
        {toc_items}
      </ul>
    </div>
  </aside>

  <main class="main">
    {"".join(sections_html)}
    <footer class="page-footer">
      <p>EU AI Act Conformity Checker — {esc(generated_at)}</p>
      <p>Informational purposes only. Does not constitute legal advice.</p>
    </footer>
  </main>

</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Markdown report (plain-text alternative)
# ---------------------------------------------------------------------------


def render_markdown(
    sample_name: str,
    results: list[dict],
    provisions: list[dict],
    generated_at: str,
) -> str:
    """Return a GitHub-flavoured Markdown report as a string."""
    provision_map = build_provision_map(provisions)
    groups = group_results_by_article(results)
    counts = compute_summary(results)
    total = sum(counts.values())
    status_label, _, status_desc = overall_status(counts)

    lines: list[str] = []

    # Header
    lines.append(f"# 🇪🇺 EU AI Act Conformity Report")
    lines.append(f"")
    lines.append(f"**Sample:** `{sample_name}`  ")
    lines.append(f"**Generated:** {generated_at}  ")
    lines.append(f"**Overall Status:** {status_label} — {status_desc}")
    lines.append("")

    # Summary section
    lines.append("---")
    lines.append("")
    lines.append("## 📊 Summary")
    lines.append("")
    lines.append("| Verdict | Count | Share |")
    lines.append("|---------|------:|------:|")
    for v in VERDICT_ORDER:
        cnt = counts[v]
        pct = (cnt / total * 100) if total else 0
        icon = VERDICT_META[v]["icon"]
        lines.append(f"| {icon} {v} | {cnt} | {pct:.1f}% |")
    lines.append(f"| **Total** | **{total}** | **100%** |")
    lines.append("")

    # TOC
    lines.append("---")
    lines.append("")
    lines.append("## 📑 Articles Covered")
    lines.append("")
    for article in groups:
        slug = article.lower().replace(" ", "-")
        lines.append(f"- [{article}](#{slug})")
    lines.append("")

    # Per-article sections
    for article, entries in groups.items():
        art_counts = compute_summary(entries)
        lines.append("---")
        lines.append("")
        lines.append(f"## {article}")
        lines.append("")
        mini = " | ".join(
            f'{VERDICT_META[v]["icon"]} **{art_counts[v]}** {v}'
            for v in VERDICT_ORDER
            if art_counts[v] > 0
        )
        lines.append(f"_{mini}_")
        lines.append("")

        for entry in entries:
            req_id = entry.get("requirement_id", "")
            citation = entry.get("citation", "")
            requirement = entry.get("requirement", "")
            verdict = entry.get("verdict", "No Evidence")
            evidence = entry.get("evidence_quote")
            confidence = entry.get("confidence")
            reasoning = entry.get("reasoning", "")

            icon = VERDICT_META.get(verdict, VERDICT_META["No Evidence"])["icon"]

            lines.append(f"### {icon} `{req_id}`")
            lines.append("")
            lines.append(f"**Citation:** {citation}  ")
            lines.append(f"**Verdict:** {icon} {verdict}  ")
            lines.append(f"**Requirement:** {requirement}  ")

            if evidence:
                lines.append("")
                lines.append(f"**Evidence:**")
                lines.append("")
                lines.append(f"> {evidence}")
            else:
                lines.append(f"**Evidence:** _(no evidence quoted)_  ")

            conf_str = f"{confidence * 100:.0f}%" if confidence is not None else "N/A"
            lines.append(f"**Confidence:** {conf_str}  ")

            if reasoning:
                lines.append(f"**Reasoning:** {reasoning}  ")

            # Provision text
            prov_id = req_id.split("#")[0] if req_id else None
            provision = provision_map.get(prov_id, {}) if prov_id else {}
            prov_text = provision.get("full_text", "")
            if prov_text:
                lines.append("")
                lines.append(
                    "<details><summary>View provision text</summary>"
                )
                lines.append("")
                lines.append(f"```")
                lines.append(prov_text)
                lines.append(f"```")
                lines.append("")
                lines.append("</details>")

            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        f"*EU AI Act Conformity Checker — Auto-generated report — {generated_at}*  "
    )
    lines.append(
        "*This report is for informational purposes only and does not constitute legal advice.*"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an EU AI Act conformity report from results and provisions JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--results",
        required=True,
        type=Path,
        metavar="PATH",
        help="Path to results_<sample>.json (or data/results/<sample>.json)",
    )
    parser.add_argument(
        "--provisions",
        default=Path("data/provisions.json"),
        type=Path,
        metavar="PATH",
        help="Path to provisions.json  [default: data/provisions.json]",
    )
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        metavar="PATH",
        help="Output file path. Overrides automatic naming.",
    )
    parser.add_argument(
        "--format",
        choices=["html", "md", "both"],
        default="html",
        help="Output format: html, md (Markdown), or both  [default: html]",
    )
    return parser.parse_args()


def derive_sample_name(results_path: Path) -> str:
    """
    Infer a human-readable sample name from the results file path.

    Examples
    --------
    data/results_sample_compliant.json  → sample_compliant
    data/results/sample_partial.json    → sample_partial
    results/my_results.json             → my_results
    """
    stem = results_path.stem  # e.g. "results_sample_compliant" or "sample_partial"
    # Strip a leading "results_" prefix if present
    if stem.startswith("results_"):
        stem = stem[len("results_"):]
    return stem


def main() -> None:
    args = parse_args()

    results_path: Path = args.results
    provisions_path: Path = args.provisions

    print(f"[report] Loading results   : {results_path}")
    print(f"[report] Loading provisions: {provisions_path}")

    results = load_json(results_path)
    provisions = load_json(provisions_path)

    if not isinstance(results, list):
        sys.exit("[report] ERROR: results JSON must be a top-level array.")
    if not isinstance(provisions, list):
        sys.exit("[report] ERROR: provisions JSON must be a top-level array.")

    sample_name = derive_sample_name(results_path)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine output directory — default to reports/ next to the project root
    reports_dir = Path("reports")

    fmt = args.format
    outputs_written: list[Path] = []

    if fmt in ("html", "both"):
        out_path = args.output if (args.output and fmt == "html") else reports_dir / f"{sample_name}_report.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        html_content = render_html(sample_name, results, provisions, generated_at)
        out_path.write_text(html_content, encoding="utf-8")
        outputs_written.append(out_path)

    if fmt in ("md", "both"):
        md_out = (
            args.output if (args.output and fmt == "md")
            else reports_dir / f"{sample_name}_report.md"
        )
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_content = render_markdown(sample_name, results, provisions, generated_at)
        md_out.write_text(md_content, encoding="utf-8")
        outputs_written.append(md_out)

    for p in outputs_written:
        print(f"[report] ✅ Report written  : {p}")


if __name__ == "__main__":
    main()
