import json
from pathlib import Path
from src.extract_requirements import process_provisions_file


def test_extract_requirements_leaf_only_rule(tmp_path: Path):
    input_file = Path("data/provisions.json")
    output_file = tmp_path / "requirements_draft.json"

    assert input_file.exists(), "data/provisions.json must exist"

    extracted_drafts, total_count, leaf_count = process_provisions_file(
        input_file, output_file
    )

    assert output_file.exists()
    assert len(extracted_drafts) == 48
    assert leaf_count == 39
    assert total_count == 63  # Active atomic requirements at leaf level

    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Verify parent nodes have empty requirements list and is_leaf=False
    parent_entry = next(item for item in data if item["id"] == "art_9.par_2")
    assert parent_entry["is_leaf"] is False
    assert parent_entry["requirements"] == []
    assert "citation" in parent_entry
    assert "full_text" in parent_entry

    # Verify leaf nodes have populated requirements list and is_leaf=True
    leaf_entry = next(item for item in data if item["id"] == "art_9.par_2.pt_a")
    assert leaf_entry["is_leaf"] is True
    assert len(leaf_entry["requirements"]) == 2
