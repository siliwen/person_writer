from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path


def split_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    blocks = [item.strip() for item in re.split(r"\n\s*\n+", normalized) if item.strip()]
    if len(blocks) == 1:
        blocks = [item.strip() for item in normalized.split("\n") if item.strip()]
    return blocks


def extract_text_from_docx(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml_bytes = archive.read("word/document.xml")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_upload_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        return extract_text_from_docx(data)
    return data.decode("utf-8-sig")

