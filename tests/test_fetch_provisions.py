import json
from pathlib import Path
from src.fetch_provisions import fetch_and_save_provisions


def test_fetch_provisions(tmp_path: Path):
    output_file = tmp_path / "provisions.json"
    extracted_data, stats = fetch_and_save_provisions(output_file)

    assert output_file.exists()
    assert len(extracted_data) == 48

    # Verify JSON structure
    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 48
    first_entry = data[0]
    assert "id" in first_entry
    assert "citation" in first_entry
    assert "full_text" in first_entry

    assert first_entry["id"] == "art_9"
    assert first_entry["citation"] == "Article 9"

    # Verify all target articles exist in stats
    assert set(stats.keys()) == {9, 13, 14}
