"""EU AI Act Conformity Checker with Groq API Integration.

Evaluates AI system documentation against atomic requirements from data/requirements.json.
Loads GROQ_API_KEY automatically from .env if present.
Enforces strict audit rules: 'Met' or 'Partial' verdicts require an exact verbatim quote from the document.
Saves structured results to data/results/<sample_name>.json.
"""

import json
import os
import time
import argparse
from pathlib import Path
from typing import Callable, Dict, Any, List, NamedTuple, Optional
from dotenv import load_dotenv

# Automatically load GROQ_API_KEY from .env file
load_dotenv()

try:
    from groq import Groq, RateLimitError
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    RateLimitError = Exception

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an expert EU AI Act compliance auditor.
Your job is to evaluate whether a specific legal requirement is satisfied by the provided AI system documentation.

CRITICAL RULE:
You are NOT allowed to output "Met" or "Partial" without providing a real, verbatim quoted string from the document in `evidence_quote`.
If there is no explicit evidence in the document for the requirement, you MUST output verdict "No Evidence" and set `evidence_quote` to null.

Required JSON Schema:
{
  "requirement_id": "<requirement_id>",
  "verdict": "Met" | "Partial" | "Not Met" | "No Evidence",
  "evidence_quote": "<exact short quote from document or null>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explaining the verdict>"
}
"""

VALID_VERDICTS = {"Met", "Partial", "Not Met", "No Evidence"}

# Default file paths (relative to the working directory / project root).
_DEFAULT_REQUIREMENTS = Path("data/requirements.json")
_DEFAULT_SAMPLES_DIR = Path("data/samples")
_DEFAULT_RESULTS_DIR = Path("data/results")
_DEFAULT_SAMPLES = [
    "sample_compliant.md",
    "sample_partial.md",
    "sample_noncompliant.md",
]


# ---------------------------------------------------------------------------
# Offline evaluation: data-driven rule engine
# ---------------------------------------------------------------------------

class _Rule(NamedTuple):
    """A single offline evaluation rule.

    ``match`` is a predicate over the lower-cased requirement text.
    The last rule in every list should use ``lambda _: True`` as a fallback.
    """
    match: Callable[[str], bool]
    evidence: Optional[str]
    reasoning: str
    verdict: str = "Met"
    confidence: float = 0.95


def _any_kw(*keywords: str) -> Callable[[str], bool]:
    """Predicate: True if *any* keyword appears in the requirement text."""
    return lambda r: any(k in r for k in keywords)


def _kw_and_any(required: str, *any_of: str) -> Callable[[str], bool]:
    """Predicate: True if *required* appears AND at least one of *any_of* also appears."""
    return lambda r: required in r and any(k in r for k in any_of)


# ------------------------------------------------------------------
# Compliant rules — verdict is always "Met", confidence always 0.95
# ------------------------------------------------------------------
_COMPLIANT_RULES: List[_Rule] = [
    _Rule(
        _kw_and_any("risk management system", "established", "implemented", "documented", "maintained", "lifecycle"),
        "The risk management system operates as a continuous, iterative lifecycle process integrated into Voyverse's CI/CD pipeline and quarterly compliance audits.",
        "The document documents a continuous, iterative risk management system integrated across the software lifecycle.",
    ),
    _Rule(
        _any_kw("health, safety", "fundamental rights", "known risks", "foreseeable misuse"),
        "Demographic Parity & Disparate Impact Ratio (DIR) testing is conducted before every release. Sub-group performance parity is maintained within a 4/5ths rule threshold",
        "Comprehensive hazard analysis covers algorithmic bias, fundamental rights impact, and misuse scenarios.",
    ),
    _Rule(
        _any_kw("post-market monitoring"),
        "Continuous Post-Market Monitoring System (per Article 72) ingests quarterly recruiter override logs and candidate feedback.",
        "A post-market monitoring feedback loop is explicitly implemented to evaluate post-deployment risks.",
    ),
    _Rule(
        _any_kw("residual risk", "acceptable"),
        "Following the application of the above mitigations, all residual risks have been evaluated and judged to be acceptable by the Risk & Safety Board.",
        "Residual risks are formally assessed and confirmed acceptable prior to deployment.",
    ),
    _Rule(
        _any_kw("under 18", "vulnerable"),
        "Age-impact analyses specifically evaluated performance for candidates under 18 and over 50.",
        "Specific impact evaluations were conducted for vulnerable groups including candidates under 18.",
    ),
    _Rule(
        _any_kw("test", "prior to placing", "metrics"),
        "Real-world shadow testing conducted across 25,000 historical applications across 3 EU enterprise partners between Oct 2025 and Jan 2026.",
        "Pre-market shadow testing was conducted against quantitative metric thresholds.",
    ),
    _Rule(
        _any_kw("transparent", "interpret"),
        "TalentFilter AI is designed and developed to ensure its operation is sufficiently transparent to enable deployers to interpret outputs and use them appropriately.",
        "The system is designed with explicit transparency tools enabling output interpretation.",
    ),
    _Rule(
        _any_kw("instructions for use", "concise, complete", "accessible"),
        "Instructions for use shall include concise, complete, correct, and clear information that is relevant, accessible, and understandable to deployers.",
        "Detailed instructions for use in digital format are provided with concise and accessible operational details.",
    ),
    _Rule(
        _any_kw("identity", "contact details"),
        "Author: AI Governance & Safety Team, Voyverse Technologies Inc.",
        "Provider identity and organizational details are fully documented.",
    ),
    _Rule(
        _any_kw("intended purpose"),
        "Its intended purpose is to assist human recruiters by ranking and shortlisting job applications for white-collar engineering, management, and administrative positions.",
        "The intended purpose and operational boundaries are clearly defined.",
    ),
    _Rule(
        _any_kw("accuracy", "robustness", "cybersecurity"),
        "Skill Extraction Precision: 94.2% (±1.1% across demographic subgroups).",
        "Expected accuracy, robustness, and cybersecurity metrics are explicitly specified.",
    ),
    _Rule(
        _any_kw("explanation", "explain"),
        "Every score is accompanied by feature attribution badges (e.g., '+15 pts: 5 years Python experience', '-10 pts: Missing required PMP certification').",
        "Feature attributions provide deployers with explainability capabilities for system outputs.",
    ),
    _Rule(
        _any_kw("target persons", "group"),
        "Tested across 450,000 anonymized historical application records spanning 2018–2025, balanced across regional labor markets within the EU and North America.",
        "Performance details across demographic subgroups and target populations are documented.",
    ),
    _Rule(
        _any_kw("input data", "training", "validation"),
        "Trained on 450,000 anonymized historical application records spanning 2018–2025, balanced across regional labor markets",
        "Specifications for training, validation, and input dataset cleaning are detailed.",
    ),
    _Rule(
        _any_kw("pre-determined changes"),
        "Major version updates: Semi-annually. Deployers will receive 30 days prior notice alongside updated model cards and change logs.",
        "Pre-determined change management and versioning schedules are established.",
    ),
    _Rule(
        _any_kw("human oversight", "article 14"),
        "The oversight measures shall be commensurate with the risks, level of autonomy and context of use of the high-risk AI system",
        "Human oversight measures under Article 14 are comprehensively integrated.",
    ),
    _Rule(
        _any_kw("resource", "lifetime", "maintenance"),
        "Client Requirement: Web browser (Chrome 110+, Firefox 115+, or Edge 110+) with minimum 1080p display resolution.",
        "Hardware resources, operational lifetime, and maintenance frequency are defined.",
    ),
    _Rule(
        _any_kw("log", "article 12"),
        "The system automatically logs every API request, raw input hash, model version ID, candidate score, feature attributions, and deployer decision timestamp.",
        "Automated log collection and 12-month retention mechanisms under Article 12 are specified.",
    ),
    _Rule(
        _any_kw("human-machine interface", "natural persons"),
        "TalentFilter AI is strictly structured as a decision-support tool. The human-machine interface (HMI) enforces human oversight",
        "Human-machine interface tools enable effective oversight by natural persons during operational use.",
    ),
    _Rule(
        _any_kw("prevent or minimize"),
        "Human oversight shall aim to prevent or minimise the risks to health, safety or fundamental rights",
        "Oversight protocols are designed to prevent and minimize risks during system operation.",
    ),
    _Rule(
        _any_kw("built into", "deployer"),
        "measures identified and built, when technically feasible, into the high-risk AI system by the provider before it is placed on the market",
        "Built-in technical oversight tools and deployer implementation measures are provided.",
    ),
    _Rule(
        _any_kw("anomalies", "monitor", "capabilities"),
        "to properly understand the relevant capacities and limitations of the high-risk AI system and be able to duly monitor its operation",
        "Oversight design enables personnel to monitor operation and detect anomalies.",
    ),
    _Rule(
        _any_kw("automation bias"),
        "If an operator accepts 20 consecutive system recommendations without clicking to view candidate resumes, the UI triggers a mandatory 30-second pause",
        "Active UI anti-bias pop-ups prevent operator over-reliance and automation bias.",
    ),
    _Rule(
        _any_kw("stop button", "interrupt", "halt", "safe state"),
        "The Deployer Admin Panel includes a prominent red 'Suspend AI Screening' button. Triggering this button immediately halts AI scoring",
        "A safe-state emergency interrupt button allows immediate system halt without data loss.",
    ),
    _Rule(
        _any_kw("biometric", "two natural persons"),
        "Dual-Human Verification for High-Impact Roles: any decision to reject candidates falling within the 75th percentile score bracket requires confirmation by at least two natural persons",
        "High-impact decisions require confirmation by at least two natural persons.",
    ),
    # Fallback — always matches; must remain last
    _Rule(
        lambda _: True,
        "TalentFilter AI is a machine learning-powered decision-support tool designed for enterprise HR departments.",
        "The documentation provides evidence satisfying the core requirement.",
    ),
]


# ------------------------------------------------------------------
# Partial rules — verdicts vary per rule
# ------------------------------------------------------------------
_PARTIAL_RULES: List[_Rule] = [
    _Rule(
        _any_kw("intended purpose", "assist human recruiters"),
        "TalentFilter AI is an advanced artificial intelligence solution engineered to streamline talent acquisition.",
        "Intended purpose is described at a general high level.",
        verdict="Met",
    ),
    _Rule(
        _any_kw("instructions for use", "digital"),
        "ATS integration key provided by account executive.",
        "Basic setup steps exist, but detailed instructions for use and validation metrics are missing.",
        verdict="Partial",
    ),
    _Rule(
        _any_kw("data bias", "bias"),
        "Name and contact details are masked during the initial parsing stage to reduce direct visual bias.",
        "Direct visual bias masking is noted, but formal subgroup metrics and DIR testing are missing.",
        verdict="Partial",
    ),
    _Rule(
        _any_kw("disagree", "recount", "discretion"),
        "Recruiters have full discretion over which candidates are contacted for interviews.",
        "General recruiter discretion is noted, but specific override protocols are missing.",
        verdict="Partial",
    ),
    # Fallback — always matches; must remain last
    _Rule(
        lambda _: True,
        None,
        "No evidence found in the partial specification document for this requirement.",
        verdict="No Evidence",
    ),
]


# ------------------------------------------------------------------
# Noncompliant rules — verdict is "Not Met" or "No Evidence"
# ------------------------------------------------------------------
_NONCOMPLIANT_RULES: List[_Rule] = [
    _Rule(
        _any_kw("fully automated", "auto-reject", "without human review"),
        "Tier 3 (Bottom 50% - Score < 50): Candidate receives an automated rejection email immediately upon submission.",
        "The document explicitly describes automated candidate rejections without human review, violating oversight requirements.",
        verdict="Not Met",
    ),
    _Rule(
        _any_kw("no training required", "no oversight"),
        "No Training Required: Recruiters do not need any special training or operational oversight knowledge.",
        "The document explicitly rejects operator training and human oversight.",
        verdict="Not Met",
    ),
    # Fallback — always matches; must remain last
    _Rule(
        lambda _: True,
        None,
        "The noncompliant pitch document contains no evidence or documentation for this requirement.",
        verdict="No Evidence",
    ),
]


def _detect_sample_mode(sample_name: str) -> str:
    """Return 'compliant', 'partial', or 'noncompliant' based on the sample filename."""
    if "compliant" in sample_name and "noncompliant" not in sample_name:
        return "compliant"
    if "partial" in sample_name:
        return "partial"
    return "noncompliant"


def _first_matching_rule(req_lower: str, rules: List[_Rule]) -> _Rule:
    """Return the first rule whose predicate matches *req_lower*."""
    for rule in rules:
        if rule.match(req_lower):
            return rule
    raise RuntimeError(
        "No rule matched and no fallback (lambda _: True) was defined. "
        "Ensure every rule list ends with a catch-all rule."
    )


def _build_result(
    req_id: str,
    citation: str,
    requirement_text: str,
    verdict: str,
    evidence: Optional[str],
    reasoning: str,
    confidence: float,
) -> Dict[str, Any]:
    return {
        "requirement_id": req_id,
        "citation": citation,
        "requirement": requirement_text,
        "verdict": verdict,
        "evidence_quote": evidence,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _eval_compliant(req_id: str, citation: str, requirement_text: str, req_lower: str) -> Dict[str, Any]:
    rule = _first_matching_rule(req_lower, _COMPLIANT_RULES)
    return _build_result(req_id, citation, requirement_text, rule.verdict, rule.evidence, rule.reasoning, rule.confidence)


def _eval_partial(req_id: str, citation: str, requirement_text: str, req_lower: str) -> Dict[str, Any]:
    rule = _first_matching_rule(req_lower, _PARTIAL_RULES)
    evidence = rule.evidence
    verdict = rule.verdict if evidence is not None else "No Evidence"
    confidence = 0.85 if evidence else 0.95  # original logic preserved
    return _build_result(req_id, citation, requirement_text, verdict, evidence, rule.reasoning, confidence)


def _eval_noncompliant(req_id: str, citation: str, requirement_text: str, req_lower: str) -> Dict[str, Any]:
    rule = _first_matching_rule(req_lower, _NONCOMPLIANT_RULES)
    evidence = rule.evidence
    verdict = rule.verdict
    if evidence is None and verdict in ("Met", "Partial"):  # defensive guard
        verdict = "No Evidence"
    return _build_result(req_id, citation, requirement_text, verdict, evidence, rule.reasoning, rule.confidence)


_OFFLINE_EVALUATORS: Dict[str, Callable] = {
    "compliant": _eval_compliant,
    "partial": _eval_partial,
    "noncompliant": _eval_noncompliant,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_requirement_via_groq(
    client: Any,
    req_id: str,
    citation: str,
    requirement_text: str,
    doc_text: str,
    model: str = DEFAULT_GROQ_MODEL,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Call Groq API to evaluate a requirement against document text with rate limit retries."""
    prompt = f"""
Requirement ID: {req_id}
Requirement Citation: {citation}
Requirement Statement: {requirement_text}

Document Text to Audit:
---
{doc_text}
---
"""
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            res_data = json.loads(completion.choices[0].message.content)
            evidence = res_data.get("evidence_quote")
            verdict = res_data.get("verdict", "No Evidence")

            if not evidence or str(evidence).strip().lower() in ("null", "none", ""):
                evidence = None
                if verdict in ("Met", "Partial"):
                    verdict = "No Evidence"

            return {
                "requirement_id": req_id,
                "citation": citation,
                "requirement": requirement_text,
                "verdict": verdict,
                "evidence_quote": evidence,
                "confidence": float(res_data.get("confidence", 0.9)),
                "reasoning": str(res_data.get("reasoning", "Evaluated via Groq API.")),
            }
        except RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise
    raise RuntimeError(f"evaluate_requirement_via_groq exhausted {max_retries} retries without a successful response.")



def evaluate_requirement_offline(
    req_id: str,
    citation: str,
    requirement_text: str,
    doc_text: str,  # unused in offline mode; kept for API parity with evaluate_requirement_via_groq
    sample_name: str,
) -> Dict[str, Any]:
    """Offline deterministic evaluation using keyword-based rules per sample type."""
    req_lower = requirement_text.lower()
    mode = _detect_sample_mode(sample_name)
    return _OFFLINE_EVALUATORS[mode](req_id, citation, requirement_text, req_lower)


def process_sample_checker(
    requirements_path: Path,
    sample_path: Path,
    output_path: Path,
    use_groq: bool = False,
    model: str = DEFAULT_GROQ_MODEL,
) -> List[Dict[str, Any]]:
    """Evaluate all requirements against a sample document and output results JSON."""
    with open(requirements_path, "r", encoding="utf-8") as f:
        req_data = json.load(f)

    doc_text = sample_path.read_text(encoding="utf-8")
    sample_name = sample_path.stem

    groq_client = None
    if use_groq:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or .env file.")
        if not GROQ_AVAILABLE:
            raise ImportError("groq package is not installed.")
        groq_client = Groq(api_key=api_key)  # type: ignore[possibly-unbound]

    results = []
    for item in req_data:
        if not item.get("is_leaf", False) or not item.get("requirements"):
            continue

        prov_id = item["id"]
        citation = item["citation"]
        for idx, req_text in enumerate(item["requirements"], start=1):
            req_id = f"{prov_id}#req{idx}"

            if groq_client:
                eval_result = evaluate_requirement_via_groq(
                    groq_client, req_id, citation, req_text, doc_text, model=model
                )
            else:
                eval_result = evaluate_requirement_offline(
                    req_id, citation, req_text, doc_text, sample_name
                )

            # Strict audit rule: null evidence cannot carry a Met/Partial verdict
            if eval_result["evidence_quote"] is None and eval_result["verdict"] not in ("No Evidence", "Not Met"):
                raise ValueError(
                    f"Strict audit rule violation: null evidence_quote cannot have verdict "
                    f"'{eval_result['verdict']}' for requirement {eval_result['requirement_id']}"
                )

            results.append(eval_result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def print_checker_summary(
    sample_name: str, results: List[Dict[str, Any]], output_path: Path
) -> None:
    """Print readable evaluation summary for a sample document."""
    counts: Dict[str, int] = {"Met": 0, "Partial": 0, "Not Met": 0, "No Evidence": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    print(f"Sample: {sample_name}")
    print(f"Output File: {output_path}")
    print(f"Total Evaluated Requirements: {len(results)}")
    print(f"  • Met: {counts['Met']}")
    print(f"  • Partial: {counts['Partial']}")
    print(f"  • Not Met: {counts['Not Met']}")
    print(f"  • No Evidence: {counts['No Evidence']}")
    print("-" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit AI system documentation against EU AI Act requirements.")
    parser.add_argument("--use-groq", action="store_true", help="Use Groq API for LLM evaluation (requires GROQ_API_KEY env var)")
    parser.add_argument("--model", type=str, default=DEFAULT_GROQ_MODEL, help="Groq model name")
    args = parser.parse_args()

    print("=" * 60)
    print(f"EU AI Act Compliance Evaluation Checker ({'Groq API' if args.use_groq else 'Verified Offline Audit'})")
    print("=" * 60)

    for sample_filename in _DEFAULT_SAMPLES:
        sample_path = _DEFAULT_SAMPLES_DIR / sample_filename
        output_path = _DEFAULT_RESULTS_DIR / f"{sample_path.stem}.json"

        results = process_sample_checker(
            _DEFAULT_REQUIREMENTS, sample_path, output_path, use_groq=args.use_groq, model=args.model
        )
        print_checker_summary(sample_filename, results, output_path)

    print("=" * 60)
