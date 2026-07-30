import json
from pathlib import Path
from src.checker import process_sample_checker, VALID_VERDICTS


def test_checker_evaluation_on_samples(tmp_path: Path):
    req_file = Path("data/requirements.json")
    samples_dir = Path("data/samples")

    assert req_file.exists()
    assert samples_dir.exists()

    sample_files = [
        "sample_compliant.md",
        "sample_partial.md",
        "sample_noncompliant.md",
    ]

    for sample_name in sample_files:
        sample_path = samples_dir / sample_name
        output_file = tmp_path / "results" / f"{sample_path.stem}.json"

        results = process_sample_checker(req_file, sample_path, output_file)

        assert output_file.exists()
        assert len(results) == 63

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 63
        for item in data:
            assert "requirement_id" in item
            assert "citation" in item
            assert "requirement" in item
            assert "verdict" in item
            assert item["verdict"] in VALID_VERDICTS
            assert "evidence_quote" in item
            assert "confidence" in item
            assert 0.0 <= item["confidence"] <= 1.0
            assert "reasoning" in item

            # STRICT AUDIT RULE: Met or Partial MUST have a non-null evidence quote
            if item["verdict"] in ("Met", "Partial"):
                assert item["evidence_quote"] is not None
                assert isinstance(item["evidence_quote"], str)
                assert len(item["evidence_quote"]) > 0
            else: # No Evidence or Not Met without quote
                if item["evidence_quote"] is None:
                    assert item["verdict"] in ("No Evidence", "Not Met")
