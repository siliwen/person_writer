import argparse
import csv
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = PROJECT_ROOT / "eval_sets" / "mvp_style_eval_v1"
MATERIAL_MANIFEST_PATH = EVAL_ROOT / "material_manifest.csv"
GENERATION_MANIFEST_PATH = EVAL_ROOT / "generation_manifest.csv"
COPYING_REPORT_PATH = EVAL_ROOT / "copying_report.csv"

FIELDS = [
    "check_id",
    "generation_id",
    "writer_id",
    "variant",
    "max_ngram_overlap",
    "longest_common_substring_chars",
    "matched_material_ids",
    "source_fragment_count",
    "risk_level",
    "reviewer",
    "reviewed_at",
    "action",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tree = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in tree.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def char_ngrams(text: str, n: int = 12) -> set[str]:
    if len(text) < n:
        return set()
    return {text[index : index + n] for index in range(len(text) - n + 1)}


def risk_level(max_overlap: float, longest_match: int) -> str:
    if longest_match >= 180 or max_overlap >= 0.35:
        return "high"
    if longest_match >= 100 or max_overlap >= 0.2:
        return "medium"
    if longest_match >= 60 or max_overlap >= 0.1:
        return "low"
    return "none"


def action_for(level: str) -> str:
    if level == "high":
        return "block_and_review"
    if level == "medium":
        return "manual_review"
    if level == "low":
        return "spot_check"
    return "pass"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="")
    parser.add_argument("--output", default=str(COPYING_REPORT_PATH))
    args = parser.parse_args()

    materials = read_csv(MATERIAL_MANIFEST_PATH)
    generations = read_csv(GENERATION_MANIFEST_PATH)
    if args.variant:
        generations = [row for row in generations if row["variant"] == args.variant]
    materials_by_writer = defaultdict(list)
    for row in materials:
        materials_by_writer[row["writer_id"]].append(row)

    text_cache = {}
    source_ngram_cache = {}
    rows = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for index, generation in enumerate(generations, start=1):
        output_path = PROJECT_ROOT / generation["output_path"]
        output_text = normalize(output_path.read_text(encoding="utf-8"))
        output_ngrams = char_ngrams(output_text)
        max_overlap = 0.0
        longest_match = 0
        matched_materials = []
        source_fragment_count = 0
        for material in materials_by_writer[generation["writer_id"]]:
            material_id = material["material_id"]
            if material_id not in text_cache:
                text_cache[material_id] = normalize(extract_docx_text(PROJECT_ROOT / material["source_path"]))
                source_ngram_cache[material_id] = char_ngrams(text_cache[material_id])
            source_text = text_cache[material_id]
            source_ngrams = source_ngram_cache[material_id]
            if output_ngrams:
                overlap = len(output_ngrams & source_ngrams) / len(output_ngrams)
            else:
                overlap = 0.0
            if overlap > max_overlap:
                max_overlap = overlap
            match = SequenceMatcher(None, output_text, source_text, autojunk=False).find_longest_match(
                0, len(output_text), 0, len(source_text)
            )
            if match.size > longest_match:
                longest_match = match.size
            if overlap >= 0.02 or match.size >= 40:
                matched_materials.append(material_id)
            if match.size >= 40:
                source_fragment_count += 1
        level = risk_level(max_overlap, longest_match)
        rows.append(
            {
                "check_id": f"copy_{index:04d}",
                "generation_id": generation["generation_id"],
                "writer_id": generation["writer_id"],
                "variant": generation["variant"],
                "max_ngram_overlap": f"{max_overlap:.4f}",
                "longest_common_substring_chars": str(longest_match),
                "matched_material_ids": "|".join(sorted(set(matched_materials))),
                "source_fragment_count": str(source_fragment_count),
                "risk_level": level,
                "reviewer": "run_copying_check.py",
                "reviewed_at": now,
                "action": action_for(level),
                "notes": "12-char ngram overlap plus longest common substring against same-writer materials.",
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"copying checks: {len(rows)}")


if __name__ == "__main__":
    main()
