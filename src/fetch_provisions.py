import json
from pathlib import Path
from euaiact import AIAct, ProvisionType

# Target articles specified in requirement
TARGET_ARTICLES = [9, 13, 14]


def fetch_and_save_provisions(output_path: Path) -> tuple[list[dict], dict]:
    """Load EU AI Act, extract target articles (including paragraphs and points), and save to JSON."""
    act = AIAct.load()
    extracted_data = []
    stats = {
        art_num: {"heading": "", "paragraphs": 0, "points": 0, "total": 0}
        for art_num in TARGET_ARTICLES
    }

    for art_num in TARGET_ARTICLES:
        art = act.article(art_num)
        stats[art_num]["heading"] = f"{art.citation} — {art.heading}"

        for provision in art.walk():
            entry = {
                "id": provision.id,
                "citation": provision.citation,
                "full_text": provision.full_text(),
            }
            extracted_data.append(entry)

            stats[art_num]["total"] += 1
            if provision.type == ProvisionType.PARAGRAPH:
                stats[art_num]["paragraphs"] += 1
            elif provision.type == ProvisionType.POINT:
                stats[art_num]["points"] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=2)

    return extracted_data, stats


def print_summary(stats: dict, total_extracted: int, output_path: Path) -> None:
    """Print a readable summary of extracted provisions."""
    print("=" * 60)
    print("EU AI Act Provisions Extraction Summary")
    print("=" * 60)
    print(f"Output File: {output_path}")
    print(f"Total Provisions Extracted: {total_extracted}\n")

    for art_num, info in stats.items():
        print(f"• {info['heading']}")
        print(f"  - Total provisions: {info['total']}")
        print(f"  - Paragraphs: {info['paragraphs']}")
        print(f"  - Points & sub-points: {info['points']}")

    print("=" * 60)


def main() -> None:
    output_file = Path("data/provisions.json")
    extracted_data, stats = fetch_and_save_provisions(output_file)
    print_summary(stats, len(extracted_data), output_file)


if __name__ == "__main__":
    main()
