# AI Act Conformity Checker

A Python tool for evaluating AI-system documentation against atomic requirements derived from the EU AI Act. It focuses on high-risk AI systems and currently covers Articles 9 (risk management), 13 (transparency and instructions for use), and 14 (human oversight). EU AI Act provisions are loaded through the [`euaiact`](https://github.com/azizamari/euaiact) project.

The project can run entirely offline using verified, deterministic sample evaluations, or use the Groq API for LLM-assisted requirement extraction and document auditing.

> This project is an engineering aid for compliance review, not legal advice or a substitute for a formal conformity assessment.

## Features

- Extracts Articles 9, 13, and 14 from the `euaiact` dataset into reusable provision data.
- Converts leaf legal provisions into atomic, individually checkable requirements.
- Audits documentation against each requirement using either Groq or the offline evaluator.
- Enforces an evidence rule: `Met` and `Partial` verdicts must include a verbatim evidence quote.
- Produces structured JSON with the requirement, citation, verdict, evidence, confidence, and reasoning.
- Generates self-contained HTML compliance reports grouped by article, including verdict summaries and confidence indicators.
- Includes compliant, partially compliant, and non-compliant HR-screening examples plus automated tests.

## Project structure

```text
.
├── src/
│   ├── fetch_provisions.py          # Extract selected EU AI Act provisions
│   ├── extract_requirements.py      # Create atomic leaf-level requirements
│   ├── checker.py                   # Evaluate documentation against requirements
│   ├── report.py                    # Render JSON results as an HTML report
│   └── ai_act_conformity_checker/   # Installable package entry point
├── data/
│   ├── provisions.json              # Extracted Articles 9, 13, and 14
│   ├── requirements.json            # Atomic requirements used by the checker
│   ├── samples/                     # Example AI-system documentation
│   └── results/                     # Generated evaluation results
├── reports/                         # Generated HTML and Markdown report examples
├── tests/                           # Pytest suite
└── pyproject.toml                   # Package metadata and dependencies
```

## Quick start

Requires Python 3.9 or later.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Run the bundled offline audit against all three sample documents:

```bash
python src/checker.py
```

This writes JSON evaluations to `data/results/` for each sample. The result schema includes:

```json
{
  "requirement_id": "art_9.par_1#req1",
  "citation": "Article 9(1)",
  "requirement": "A risk management system shall be established...",
  "verdict": "Met",
  "evidence_quote": "A verbatim quote from the audited document.",
  "confidence": 0.95,
  "reasoning": "A concise explanation of the verdict."
}
```

Valid verdicts are `Met`, `Partial`, `Not Met`, and `No Evidence`.

## Generate a report

Create a standalone HTML report from an evaluation result file:

```bash
python src/report.py \
  --results data/results/sample_compliant.json \
  --provisions data/provisions.json \
  --output reports/sample_compliant_report.html
```

The report provides an overall status, verdict counts, article-level grouping, evidence quotes, reasoning, and confidence scores.

## Rebuild the audit data

To refresh the extracted provision data:

```bash
python src/fetch_provisions.py
```

To create a fresh atomic-requirements draft using the built-in offline mapping:

```bash
python src/extract_requirements.py
```

This creates `data/requirements_draft.json`. Review it before replacing the checked-in requirements used in production audits.

## Use Groq for LLM-assisted evaluation

Create a `.env` file in the project root with your API key:

```env
GROQ_API_KEY=your_api_key_here
```

Then enable Groq when extracting requirements or auditing documents:

```bash
python src/extract_requirements.py --use-groq
python src/checker.py --use-groq
```

Both commands accept `--model` to select a Groq-compatible model. The default is `llama-3.3-70b-versatile`.

## Test

```bash
pytest
```

The tests validate provision extraction, requirement generation, the result schema, verdict handling, and report rendering.

## Sample workflow

```text
EU AI Act provisions
        ↓
Atomic legal requirements
        ↓
AI-system documentation
        ↓
Evidence-backed verdicts (JSON)
        ↓
Human-readable HTML conformity report
```

## License

No license has been specified for this repository.

## Acknowledgements

This project uses [`azizamari/euaiact`](https://github.com/azizamari/euaiact) to load and navigate the EU AI Act provisions used during extraction.
