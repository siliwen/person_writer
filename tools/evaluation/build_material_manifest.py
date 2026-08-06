import argparse
import csv
import hashlib
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


WRITER_IDS = {
    "莫言": "writer_moyan",
    "于坚": "writer_yujian",
    "王家新": "writer_wangjiaxin",
    "薄暮": "writer_bomu",
    "韩东": "writer_handong",
    "龚学明": "writer_gongxueming",
    "许子东": "writer_xuzidong",
    "蔡辉": "writer_caihui",
    "群山": "writer_qunshan",
    "唐山": "writer_tangshan",
    "桂从路": "writer_guiconglu",
}


FIELDNAMES = [
    "material_id",
    "writer_id",
    "writer_display_name",
    "title",
    "genre",
    "source_type",
    "source_path",
    "source_url",
    "source_site",
    "publication_date",
    "license_name",
    "license_url",
    "rights_status",
    "authorization_document_id",
    "collected_at",
    "collector",
    "content_hash",
    "doc_char_count",
    "paragraph_count",
    "needs_split",
    "allowed_for_eval",
    "allowed_for_rag",
    "allowed_for_training",
    "ingest_status",
    "notes",
]


def extract_docx_text(path: Path) -> tuple[str, int]:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tree = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in tree.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs), len(paragraphs)


def infer_writer_and_title(path: Path, corpus_root: Path) -> tuple[str, str]:
    stem = path.stem
    folder = path.parent.name if path.parent != corpus_root else ""
    match = re.match(r"^(?:\d+_)?([^_+－-]+)[_+－-](.+)$", stem)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    if "_" in stem:
        writer, title = stem.split("_", 1)
        return writer.strip(), title.strip()
    if "－" in folder:
        return folder.split("－", 1)[0].strip(), stem
    if "-" in folder:
        return folder.split("-", 1)[0].strip(), stem
    return "UNKNOWN", stem


def infer_genre(path: Path, title: str) -> str:
    text = f"{path.parent.name} {title}"
    if "杂文散文" in text:
        return "杂文/散文合集"
    if any(name in text for name in ["某山", "未完成的自画像", "你无法想象我多爱这棵树", "暮色的味道"]):
        return "诗歌"
    if any(name in text for name in ["漫游集", "莫言"]):
        return "散文/随笔"
    return "待确认"


def needs_split(title: str, source_path: str) -> str:
    text = f"{title} {source_path}"
    return "true" if "篇" in text or "合集" in text or "杂文散文" in text else "false"


def writer_id(writer: str) -> str:
    if writer in WRITER_IDS:
        return WRITER_IDS[writer]
    digest = hashlib.sha1(writer.encode("utf-8")).hexdigest()[:8]
    return f"writer_{digest}"


def build_rows(project_root: Path, corpus_root: Path) -> list[dict[str, str]]:
    rows = []
    index = 1
    for path in sorted(corpus_root.rglob("*.docx"), key=lambda item: str(item)):
        if path.name.startswith("~$"):
            continue
        rel_path = path.relative_to(project_root).as_posix()
        writer, title = infer_writer_and_title(path, corpus_root)
        try:
            text, paragraph_count = extract_docx_text(path)
            char_count = len(re.sub(r"\s+", "", text))
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            notes = ""
        except Exception as exc:
            paragraph_count = 0
            char_count = 0
            content_hash = ""
            notes = f"read_error: {exc}"
        rows.append(
            {
                "material_id": f"mat_web_{index:04d}",
                "writer_id": writer_id(writer),
                "writer_display_name": writer,
                "title": title,
                "genre": infer_genre(path, title),
                "source_type": "internal_eval_material",
                "source_path": rel_path,
                "source_url": "",
                "source_site": "",
                "publication_date": "",
                "license_name": "",
                "license_url": "",
                "rights_status": "internal_use_assumed",
                "authorization_document_id": "",
                "collected_at": "",
                "collector": "",
                "content_hash": content_hash,
                "doc_char_count": str(char_count),
                "paragraph_count": str(paragraph_count),
                "needs_split": needs_split(title, rel_path),
                "allowed_for_eval": "true",
                "allowed_for_rag": "true",
                "allowed_for_training": "false",
                "ingest_status": "approved_for_internal_eval",
                "notes": notes,
            }
        )
        index += 1
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--corpus-root", default="测评集/网页作品")
    parser.add_argument("--out", default="eval_sets/mvp_style_eval_v1/material_manifest.csv")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    corpus_root = (project_root / args.corpus_root).resolve()
    out_path = (project_root / args.out).resolve()
    rows = build_rows(project_root, corpus_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
