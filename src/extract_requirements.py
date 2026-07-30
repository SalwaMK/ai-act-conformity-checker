"""LLM-assisted requirement extraction script using the Groq API (or offline fallback).

Decomposes bundled legal provisions from data/provisions.json into atomic,
individually-checkable single-claim requirements, outputting to data/requirements_draft.json.

Leaf-only rule:
Only leaf provisions (nodes with no child provisions) have active requirements populated
for compliance checking. Parent nodes retain their id, citation, and full_text for
report headers, context, and grouping, but have an empty requirements list ([]) and
is_leaf: False.
"""

import json
import os
import time
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from euaiact import AIAct

# Automatically load GROQ_API_KEY from .env file
load_dotenv()

try:
    from groq import Groq, RateLimitError
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    RateLimitError = Exception

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

# LLM Prompt Template for extracting atomic requirements
EXTRACTION_PROMPT_TEMPLATE = """
You are a legal and compliance engineering expert specializing in the EU AI Act.
Given the following legal provision, extract a list of atomic, single-claim, individually-checkable requirements.

Rules:
1. Split any compound/bundled obligations into separate statements.
2. Each requirement must state a single clear, verifiable condition or duty.
3. Use precise legal modal language ("shall", "must").

Provision Citation: {citation}
Provision Text:
{full_text}

Output JSON format:
{{
  "requirements": [
    "Atomic requirement 1...",
    "Atomic requirement 2..."
  ]
}}
"""

# Pre-computed verified LLM requirement map for offline fallback
LLM_LEAF_REQUIREMENTS_MAP = {
    # Article 9 Leaves
    "art_9.par_1": [
        "A risk management system shall be established for high-risk AI systems.",
        "A risk management system shall be implemented for high-risk AI systems.",
        "A risk management system shall be documented for high-risk AI systems.",
        "A risk management system shall be maintained for high-risk AI systems.",
    ],
    "art_9.par_2.pt_a": [
        "Known risks that the high-risk AI system can pose to health, safety, or fundamental rights during intended use shall be identified and analyzed.",
        "Reasonably foreseeable risks that the high-risk AI system can pose to health, safety, or fundamental rights during intended use shall be identified and analyzed.",
    ],
    "art_9.par_2.pt_b": [
        "Risks that may emerge when the high-risk AI system is used in accordance with its intended purpose shall be estimated and evaluated.",
        "Risks that may emerge under conditions of reasonably foreseeable misuse shall be estimated and evaluated.",
    ],
    "art_9.par_2.pt_c": [
        "Other risks arising based on analysis of data gathered from the post-market monitoring system (Article 72) shall be evaluated.",
    ],
    "art_9.par_2.pt_d": [
        "Appropriate and targeted risk management measures shall be adopted to address identified risks to health, safety, or fundamental rights.",
    ],
    "art_9.par_3": [
        "Risk management measures shall address risks that can be reasonably mitigated or eliminated through system development or design.",
        "Risk management measures shall address risks that can be reasonably mitigated or eliminated through provision of adequate technical information.",
    ],
    "art_9.par_4": [
        "Risk management measures shall give due consideration to the effects and interactions resulting from combined application of Section requirements.",
        "Risk management measures shall achieve an appropriate balance in fulfilling Section requirements while effectively minimizing risks.",
    ],
    "art_9.par_5.pt_a": [
        "Identified and evaluated risks shall be eliminated or reduced as far as technically feasible through adequate design and development of the high-risk AI system.",
    ],
    "art_9.par_5.pt_b": [
        "Implementation of adequate mitigation and control measures shall address risks that cannot be eliminated, where appropriate.",
    ],
    "art_9.par_5.pt_c": [
        "Information required pursuant to Article 13 shall be provided to deployers.",
        "Training shall be provided to deployers where appropriate.",
    ],
    "art_9.par_6": [
        "High-risk AI systems shall be tested for the purpose of identifying the most appropriate and targeted risk management measures.",
        "Testing shall ensure high-risk AI systems perform consistently for their intended purpose.",
        "Testing shall ensure compliance with requirements set out in Section 2.",
    ],
    "art_9.par_7": [
        "Testing procedures may include testing in real-world conditions in accordance with Article 60.",
    ],
    "art_9.par_8": [
        "Testing of high-risk AI systems shall be performed prior to placing on the market or putting into service.",
        "Testing shall be carried out against prior defined metrics and probabilistic thresholds appropriate to the intended purpose.",
    ],
    "art_9.par_9": [
        "Providers shall consider whether the high-risk AI system is likely to have an adverse impact on persons under the age of 18.",
        "Providers shall consider whether the high-risk AI system is likely to have an adverse impact on other vulnerable groups.",
    ],
    "art_9.par_10": [
        "For providers subject to internal risk management requirements under other Union law, AI Act risk management aspects may be combined with procedures under that law.",
    ],
    # Article 13 Leaves
    "art_13.par_1": [
        "High-risk AI systems shall be designed and developed to ensure their operation is sufficiently transparent to enable deployers to interpret system output.",
        "High-risk AI systems shall be designed and developed to ensure deployers can use the system appropriately.",
    ],
    "art_13.par_2": [
        "High-risk AI systems shall be accompanied by instructions for use in an appropriate digital or non-digital format.",
        "Instructions for use shall include concise, complete, correct, and clear information that is relevant, accessible, and understandable to deployers.",
    ],
    "art_13.par_3.pt_a": [
        "Instructions for use shall state the identity and contact details of the provider.",
        "Instructions for use shall state the identity and contact details of the authorised representative, where applicable.",
    ],
    "art_13.par_3.pt_b.pt_i": [
        "Instructions for use shall state the intended purpose of the high-risk AI system.",
    ],
    "art_13.par_3.pt_b.pt_ii": [
        "Instructions for use shall state expected levels of accuracy, robustness, and cybersecurity, including metrics tested against.",
        "Instructions for use shall state known and foreseeable circumstances that may impact expected accuracy, robustness, or cybersecurity.",
    ],
    "art_13.par_3.pt_b.pt_iii": [
        "Instructions for use shall state known or foreseeable circumstances during intended use or misuse that may lead to health, safety, or fundamental rights risks.",
    ],
    "art_13.par_3.pt_b.pt_iv": [
        "Instructions for use shall specify technical capabilities and characteristics to provide information relevant to explain system outputs, where applicable.",
    ],
    "art_13.par_3.pt_b.pt_v": [
        "Instructions for use shall specify system performance regarding specific target persons or groups of persons, when appropriate.",
    ],
    "art_13.par_3.pt_b.pt_vi": [
        "Instructions for use shall provide specifications for input data or relevant training, validation, and testing dataset information, when appropriate.",
    ],
    "art_13.par_3.pt_b.pt_vii": [
        "Instructions for use shall provide information enabling deployers to interpret system output and use it appropriately, where applicable.",
    ],
    "art_13.par_3.pt_c": [
        "Instructions for use shall specify pre-determined changes to the system and its performance agreed during initial conformity assessment.",
    ],
    "art_13.par_3.pt_d": [
        "Instructions for use shall specify human oversight measures referred to in Article 14.",
        "Instructions for use shall specify technical measures put in place to facilitate output interpretation by deployers.",
    ],
    "art_13.par_3.pt_e": [
        "Instructions for use shall state computational and hardware resource requirements needed for proper functioning.",
        "Instructions for use shall state the expected lifetime of the high-risk AI system.",
        "Instructions for use shall state necessary maintenance and care measures, including frequency and software update details.",
    ],
    "art_13.par_3.pt_f": [
        "Instructions for use shall describe mechanisms allowing deployers to properly collect, store, and interpret logs in accordance with Article 12, where relevant.",
    ],
    # Article 14 Leaves
    "art_14.par_1": [
        "High-risk AI systems shall be designed and developed with appropriate human-machine interface tools.",
        "High-risk AI systems shall enable effective oversight by natural persons during the period of use.",
    ],
    "art_14.par_2": [
        "Human oversight shall aim to prevent or minimize risks to health, safety, or fundamental rights during intended use or reasonably foreseeable misuse.",
        "Human oversight shall address persistent risks that remain despite application of other Section 2 requirements.",
    ],
    "art_14.par_3.pt_a": [
        "Human oversight measures identified and built into the system by the provider before market placement shall be implemented when technically feasible.",
    ],
    "art_14.par_3.pt_b": [
        "Human oversight measures appropriate to be implemented by the deployer shall be identified by the provider prior to market placement or putting into service.",
    ],
    "art_14.par_4.pt_a": [
        "Oversight personnel shall be enabled to properly understand relevant capacities and limitations of the high-risk AI system.",
        "Oversight personnel shall be enabled to duly monitor system operation to detect and address anomalies, dysfunctions, and unexpected performance.",
    ],
    "art_14.par_4.pt_b": [
        "Oversight personnel shall be enabled to remain aware of possible tendencies toward automation bias (over-relying on system outputs).",
    ],
    "art_14.par_4.pt_c": [
        "Oversight personnel shall be enabled to correctly interpret system outputs using available interpretation tools and methods.",
    ],
    "art_14.par_4.pt_d": [
        "Oversight personnel shall be enabled to decide in any particular situation not to use the high-risk AI system.",
        "Oversight personnel shall be enabled to disregard, override, or reverse high-risk AI system outputs.",
    ],
    "art_14.par_4.pt_e": [
        "Oversight personnel shall be enabled to intervene in system operation or interrupt the system through a stop button or similar safe-state procedure.",
    ],
    "art_14.par_5": [
        "For biometric identification systems (Annex III point 1(a)), deployers shall take no action or decision based on outputs unless separately verified and confirmed by at least two natural persons.",
        "Natural persons verifying biometric identification outputs shall possess necessary competence, training, and authority.",
    ],
}


def extract_atomic_requirements_via_groq(
    client: Any,
    citation: str,
    full_text: str,
    model: str = DEFAULT_GROQ_MODEL,
    max_retries: int = 3,
) -> List[str]:
    """Call Groq API to extract atomic requirements for a provision with retry backoff."""
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(citation=citation, full_text=full_text)
    
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an EU AI Act legal compliance expert. Output strictly JSON matching the required schema.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            res_text = completion.choices[0].message.content
            data = json.loads(res_text)

            if isinstance(data, dict) and "requirements" in data and isinstance(data["requirements"], list):
                return data["requirements"]
            elif isinstance(data, list):
                return data
            return [full_text]
        except RateLimitError as e:
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise e


def process_provisions_file(
    input_path: Path,
    output_path: Path,
    use_groq: bool = False,
    model: str = DEFAULT_GROQ_MODEL,
) -> tuple[list[dict], int, int]:
    """Read input provisions JSON and extract atomic requirements for leaf nodes only."""
    with open(input_path, "r", encoding="utf-8") as f:
        provisions = json.load(f)

    # Load euaiact to determine provision tree hierarchy and leaf nodes
    act = AIAct.load()

    groq_client = None
    if use_groq:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or .env file.")
        if not GROQ_AVAILABLE:
            raise ImportError("groq package is not installed.")
        groq_client = Groq(api_key=api_key)

    extracted_drafts = []
    total_atomic_count = 0
    leaf_count = 0

    for item in provisions:
        pid = item["id"]
        prov = act.get(pid)
        is_leaf = prov is not None and len(prov.children) == 0

        if is_leaf:
            leaf_count += 1
            if groq_client:
                atomic_reqs = extract_atomic_requirements_via_groq(
                    groq_client, item["citation"], item["full_text"], model=model
                )
            else:
                atomic_reqs = LLM_LEAF_REQUIREMENTS_MAP.get(
                    pid,
                    [f"{item['citation']} obligation: {item['full_text'].strip()}"],
                )
        else:
            atomic_reqs = []

        entry = {
            "id": item["id"],
            "citation": item["citation"],
            "is_leaf": is_leaf,
            "full_text": item["full_text"],
            "requirements": atomic_reqs,
        }
        extracted_drafts.append(entry)
        total_atomic_count += len(atomic_reqs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extracted_drafts, f, ensure_ascii=False, indent=2)

    return extracted_drafts, total_atomic_count, leaf_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract atomic requirements from EU AI Act provisions.")
    parser.add_argument("--use-groq", action="store_true", help="Force use of Groq API (reads GROQ_API_KEY from .env)")
    parser.add_argument("--model", type=str, default=DEFAULT_GROQ_MODEL, help="Groq model name")
    args = parser.parse_args()

    input_file = Path("data/provisions.json")
    output_file = Path("data/requirements_draft.json")

    extracted_drafts, total_count, leaf_count = process_provisions_file(
        input_file, output_file, use_groq=args.use_groq, model=args.model
    )

    parent_count = len(extracted_drafts) - leaf_count
    print("=" * 70)
    print(f"LLM Requirement Extraction Summary ({'Groq API' if args.use_groq else 'Verified Offline Draft'})")
    print("=" * 70)
    print(f"Total Provisions: {len(extracted_drafts)} (Leafs: {leaf_count}, Parents: {parent_count})")
    print(f"Total Atomic Requirements Extracted: {total_count}")
    print(f"Draft File Saved: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
