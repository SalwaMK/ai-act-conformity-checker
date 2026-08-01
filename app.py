"""Streamlit UI for live EU AI Act documentation checks.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from src.checker import DEFAULT_GROQ_MODEL, evaluate_requirement_via_groq
from src.report import render_html


ROOT = Path(__file__).resolve().parent
REQUIREMENTS_PATH = ROOT / "data" / "requirements.json"
PROVISIONS_PATH = ROOT / "data" / "provisions.json"
STOP_WORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "of",
    "on", "or", "that", "the", "their", "to", "under", "with", "shall",
}


@st.cache_data
def load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def words(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOP_WORDS and len(word) > 2
    }


def evaluate_offline(req_id: str, citation: str, requirement: str, document: str) -> dict[str, Any]:
    """Provide a transparent local baseline by matching requirement terms to sentences."""
    requirement_words = words(requirement)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", document) if s.strip()]
    best_sentence = ""
    best_score = 0.0
    for sentence in sentences:
        sentence_words = words(sentence)
        score = len(requirement_words & sentence_words) / max(len(requirement_words), 1)
        if score > best_score:
            best_score, best_sentence = score, sentence

    if best_score >= 0.55:
        verdict, confidence = "Met", min(0.99, 0.55 + best_score * 0.4)
        reasoning = "The document contains a sentence with substantial terminology overlap with this requirement."
        evidence = best_sentence
    elif best_score >= 0.25:
        verdict, confidence = "Partial", 0.55 + best_score * 0.3
        reasoning = "The document contains related terminology, but does not clearly address the complete requirement."
        evidence = best_sentence
    else:
        verdict, confidence = "No Evidence", max(0.5, 1.0 - best_score)
        reasoning = "No sufficiently specific evidence was found in the pasted documentation."
        evidence = None

    return {
        "requirement_id": req_id,
        "citation": citation,
        "requirement": requirement,
        "verdict": verdict,
        "evidence_quote": evidence,
        "confidence": round(confidence, 2),
        "reasoning": reasoning,
    }


def main() -> None:
    st.set_page_config(page_title="AI Act Conformity Checker", page_icon="⚖️", layout="wide")
    st.markdown(
        """
        <style>
        .block-container { max-width: 1450px; padding-top: 2rem; }
        .hero { padding: 1.35rem 1.55rem; border-radius: 18px; margin-bottom: 1.35rem;
                background: linear-gradient(135deg, #102a56 0%, #1e3a8a 55%, #312e81 100%);
                border: 1px solid rgba(147,197,253,.28); color: white; }
        .hero h1 { margin: 0; font-size: 2rem; letter-spacing: -.04em; }
        .hero p { margin: .45rem 0 0; color: #dbeafe; font-size: .98rem; }
        .eyebrow { color: #93c5fd; text-transform: uppercase; font-size: .7rem;
                   font-weight: 700; letter-spacing: .14em; }
        .result-card { padding: 1rem 1.1rem; border-radius: 14px; border: 1px solid #dbe3f0;
                       background: #f8fafc; min-height: 100px; }
        .result-card .label { color: #64748b; font-size: .76rem; text-transform: uppercase;
                              letter-spacing: .08em; font-weight: 700; }
        .result-card .value { font-size: 2rem; font-weight: 750; line-height: 1.2; margin-top: .35rem; }
        .muted { color: #64748b; font-size: .88rem; }
        </style>
        <div class="hero">
          <div class="eyebrow">Evidence-led compliance review</div>
          <h1>⚖️ AI Act Conformity Checker</h1>
          <p>Paste documentation, choose the requirements that matter, and inspect a live review of the evidence.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    requirements_data = load_json(REQUIREMENTS_PATH)
    provisions = load_json(PROVISIONS_PATH)
    leaf_requirements = [item for item in requirements_data if item.get("is_leaf") and item.get("requirements")]

    with st.sidebar:
        st.header("Review setup")
        st.caption("Select a scope, then choose the individual requirements to evaluate.")
        article_options = sorted({item["citation"].split("(")[0] for item in leaf_requirements})
        selected_articles = st.multiselect("Articles", article_options, default=article_options)
        candidates = [item for item in leaf_requirements if item["citation"].split("(")[0] in selected_articles]
        labels = {
            f"{item['citation']} — {req}": (item, index)
            for item in candidates
            for index, req in enumerate(item["requirements"])
        }
        selected_labels = st.multiselect(
            "Requirements",
            list(labels),
            default=list(labels)[: min(10, len(labels))],
            help="Choose the sample requirements to evaluate against the pasted document.",
        )
        use_groq = st.checkbox(
            "Use Groq (optional)",
            value=False,
            disabled=not bool(os.getenv("GROQ_API_KEY")),
            help="Requires GROQ_API_KEY in the environment or a .env file.",
        )
        st.divider()
        st.markdown("**Engine**")
        if use_groq:
            st.success("Groq LLM enabled")
        else:
            st.info("Local evidence matcher")
        st.caption("The local matcher is deterministic and runs without sending your document anywhere.")

    input_col, guide_col = st.columns([2.2, 1], gap="large")
    with input_col:
        st.subheader("1. Add documentation")
        document = st.text_area(
            "AI system documentation",
            height=300,
            label_visibility="collapsed",
            placeholder="Paste the system specification, risk assessment, instructions for use, or other evidence here…",
        )
    with guide_col:
        st.subheader("What gets checked")
        st.markdown(
            """
            <div class="muted">
            Each selected requirement receives a verdict, confidence score, reasoning, and (when found) an exact quote from your text.
            <br><br>
            <b>Met</b> · strong evidence<br>
            <b>Partial</b> · related but incomplete evidence<br>
            <b>No Evidence</b> · no sufficiently specific match
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not document.strip():
        st.info("Paste documentation above to begin the check.")
        return
    if not selected_labels:
        st.warning("Select at least one requirement in the sidebar.")
        return

    doc_words = len(words(document))
    doc_chars = len(document)
    st.caption(f"Documentation loaded · {doc_chars:,} characters · {doc_words:,} searchable terms · {len(selected_labels)} requirements selected")

    results: list[dict[str, Any]] = []
    groq_client = None
    if use_groq:
        from groq import Groq

        groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

    with st.spinner("Evaluating selected requirements…"):
        for label in selected_labels:
            item, index = labels[label]
            requirement = item["requirements"][index]
            req_id = f"{item['id']}#req{index + 1}"
            if groq_client:
                result = evaluate_requirement_via_groq(
                    groq_client, req_id, item["citation"], requirement, document, model=DEFAULT_GROQ_MODEL
                )
            else:
                result = evaluate_offline(req_id, item["citation"], requirement, document)
            results.append(result)

    counts = {verdict: sum(result["verdict"] == verdict for result in results)
              for verdict in ("Met", "Partial", "Not Met", "No Evidence")}
    st.subheader("2. Review findings")
    metrics = st.columns(4, gap="medium")
    colors = {"Met": "#15803d", "Partial": "#b45309", "Not Met": "#b91c1c", "No Evidence": "#475569"}
    for column, verdict in zip(metrics, counts):
        with column:
            st.markdown(
                f'<div class="result-card"><div class="label">{verdict}</div>'
                f'<div class="value" style="color:{colors[verdict]}">{counts[verdict]}</div></div>',
                unsafe_allow_html=True,
            )

    tab_table, tab_evidence, tab_report = st.tabs(["Results table", "Evidence details", "Full report"])
    table_rows = [
        {
            "Citation": result["citation"],
            "Verdict": result["verdict"],
            "Confidence": f"{result['confidence']:.0%}",
            "Evidence": result["evidence_quote"] or "—",
        }
        for result in results
    ]
    with tab_table:
        st.dataframe(table_rows, use_container_width=True, hide_index=True)
        st.download_button(
            "Download results JSON",
            data=json.dumps(results, ensure_ascii=False, indent=2),
            file_name="ai_act_review_results.json",
            mime="application/json",
        )
    with tab_evidence:
        for result in results:
            icon = {"Met": "✅", "Partial": "⚠️", "Not Met": "❌", "No Evidence": "🔍"}[result["verdict"]]
            with st.expander(f"{icon} {result['citation']} · {result['verdict']} · {result['confidence']:.0%}"):
                st.markdown(f"**Requirement**  \n{result['requirement']}")
                if result["evidence_quote"]:
                    st.info(f"Evidence quote: “{result['evidence_quote']}”")
                else:
                    st.caption("No evidence quote found in the documentation.")
                st.markdown(f"**Reasoning:** {result['reasoning']}")

    with tab_report:
        st.caption("The detailed report below is generated from the same live results.")
        report_html = render_html(
            "streamlit_review",
            results,
            provisions,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
        components.html(report_html, height=800, scrolling=True)
        st.download_button(
            "Download HTML report",
            data=report_html,
            file_name="ai_act_conformity_report.html",
            mime="text/html",
        )


if __name__ == "__main__":
    main()
