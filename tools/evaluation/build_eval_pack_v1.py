import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET


EVAL_ROOT = Path("eval_sets/mvp_style_eval_v1")
MANIFEST_PATH = EVAL_ROOT / "material_manifest.csv"
HOLDOUT_PATH = EVAL_ROOT / "holdout_manifest.csv"
SELECTED_WRITERS_PATH = EVAL_ROOT / "selected_writers.csv"
TASKS_PATH = EVAL_ROOT / "tasks.csv"
TASK_INSTANCES_PATH = EVAL_ROOT / "task_instances.csv"
WRITERS_ROOT = EVAL_ROOT / "writers"


SELECTED_WRITER_IDS = [
    "writer_moyan",
    "writer_yujian",
    "writer_wangjiaxin",
    "writer_bomu",
    "writer_handong",
    "writer_gongxueming",
]


STYLE_NOTES = {
    "writer_moyan": {
        "one_sentence": "乡土记忆、民间叙事和生活经验驱动的散文/随笔风格。",
        "long_description": "当前档案基于内部评测材料自动生成，主要覆盖故乡、童年、民间人物、动物、文学经验和日常生活回忆等材料。初版用于评测，不代表人工最终风格结论。",
        "themes": ["故乡记忆", "童年经验", "民间生活", "动物与人物故事", "文学经验"],
        "opening_patterns": ["从具体生活场景或记忆入口进入", "用个人经历牵出叙述主题"],
        "ending_patterns": ["回到生活经验或情感判断", "以回忆、人物或物件形成收束"],
        "paragraph_structure": ["叙事段落较长", "常以事件推进带出观点或情绪"],
        "imagery": ["故乡", "集市", "动物", "家庭", "乡村物件"],
        "rhetorical_devices": ["民间叙述", "细节铺陈", "幽默与荒诞感"],
        "narrative_distance": "近距离第一人称回忆与观察",
        "emotional_intensity": "variable",
        "structure_patterns": ["记忆入口 -> 事件展开 -> 人物/物件细节 -> 经验性收束"],
    },
    "writer_yujian": {
        "one_sentence": "地理漫游、自然观察和地方经验驱动的散文/随笔风格。",
        "long_description": "当前档案基于内部评测材料自动生成，主要覆盖高原、村庄、云南、行旅、白云、群山、小卖部等空间经验。初版用于评测，不代表人工最终风格结论。",
        "themes": ["行旅", "地理空间", "云南高原", "村庄", "自然观察"],
        "opening_patterns": ["从地点、行走或观看动作进入", "以空间感建立叙述"],
        "ending_patterns": ["回到地方经验和身体感受", "保留开放式观察"],
        "paragraph_structure": ["段落以地点和观察对象推进", "叙述和议论交错"],
        "imagery": ["梯田", "白云", "高原", "群山", "村庄"],
        "rhetorical_devices": ["空间铺陈", "观察式比喻", "地理意识"],
        "narrative_distance": "观察者式第一人称或近距离游历视角",
        "emotional_intensity": "medium",
        "structure_patterns": ["地点进入 -> 观察展开 -> 历史/经验联想 -> 开放收束"],
    },
    "writer_wangjiaxin": {
        "one_sentence": "时间、旅行、艺术记忆和自我回望驱动的现代诗风格。",
        "long_description": "当前档案基于内部评测材料自动生成，主要覆盖夏夜、自画像、端午、艺术家、纽约、诗人记忆、沿线风景和时间节点。初版用于评测，不代表人工最终风格结论。",
        "themes": ["时间", "旅行", "艺术记忆", "自我回望", "异乡经验"],
        "opening_patterns": ["从时间节点或具体地点进入", "以一个画面或标题意象展开"],
        "ending_patterns": ["以留白或回望收束", "通过时间感形成余韵"],
        "paragraph_structure": ["短段/诗行组织", "意象与思考交替"],
        "imagery": ["夏夜", "自画像", "麦田", "酒馆", "沿线"],
        "rhetorical_devices": ["互文联想", "时间折返", "艺术意象"],
        "narrative_distance": "克制的自我回望视角",
        "emotional_intensity": "medium",
        "structure_patterns": ["意象呈现 -> 时间/地点转折 -> 思考深化 -> 留白"],
    },
    "writer_bomu": {
        "one_sentence": "自然意象、远方感和内在情绪驱动的现代诗风格。",
        "long_description": "当前档案基于内部评测材料自动生成，主要覆盖树、阳光、平原、枯枝、亲人、远方、客舍、信和美好等意象。初版用于评测，不代表人工最终风格结论。",
        "themes": ["自然", "远方", "亲情", "孤独", "内在感受"],
        "opening_patterns": ["从单一自然意象或身体感受进入", "以直接陈述建立情绪"],
        "ending_patterns": ["保留抒情余波", "以意象而非解释收束"],
        "paragraph_structure": ["短诗行组织", "意象密集但叙述克制"],
        "imagery": ["树", "阳光", "平原", "枯枝", "远方"],
        "rhetorical_devices": ["意象重复", "情绪投射", "轻度跳跃"],
        "narrative_distance": "近距离抒情主体",
        "emotional_intensity": "medium",
        "structure_patterns": ["核心意象 -> 情绪展开 -> 关系/远方联想 -> 余韵"],
    },
    "writer_handong": {
        "one_sentence": "日常片段、观念反讽和克制叙述驱动的现代诗风格。",
        "long_description": "当前档案基于内部评测材料自动生成，主要覆盖玩笑、物件、山、哲学人物、车库、鬼魂、劝酒、存在感等题材。初版用于评测，不代表人工最终风格结论。",
        "themes": ["日常片段", "物件观察", "哲学/观念", "荒诞感", "克制情绪"],
        "opening_patterns": ["从普通动作、物件或判断进入", "以平直语气制造张力"],
        "ending_patterns": ["以冷静转折或存在性判断收束", "保留反讽空间"],
        "paragraph_structure": ["短行、短段", "语义推进重于华丽修辞"],
        "imagery": ["珠子", "山", "车库", "狗", "酒"],
        "rhetorical_devices": ["反讽", "口语化判断", "观念跳转"],
        "narrative_distance": "冷静旁观和自我意识并存",
        "emotional_intensity": "low",
        "structure_patterns": ["日常事实 -> 语义偏移 -> 观念触发 -> 克制收束"],
    },
    "writer_gongxueming": {
        "one_sentence": "泥土、家、记忆和亲情情绪驱动的现代诗风格。",
        "long_description": "当前档案基于内部评测材料自动生成，主要覆盖泥土、家、母亲、记忆、秋夜、树、暮色、野鸭、绿皮火车等意象。初版用于评测，不代表人工最终风格结论。",
        "themes": ["家", "泥土", "母亲", "记忆", "悲伤"],
        "opening_patterns": ["从家园、亲人或具体自然物进入", "以情绪性画面建立基调"],
        "ending_patterns": ["以亲情或记忆回声收束", "保留温柔悲伤的余韵"],
        "paragraph_structure": ["诗行组织", "情绪线较明显"],
        "imagery": ["泥土", "家", "树", "暮色", "火车"],
        "rhetorical_devices": ["抒情意象", "记忆回环", "亲情象征"],
        "narrative_distance": "贴近自我经验和亲情记忆",
        "emotional_intensity": "high",
        "structure_patterns": ["意象/亲人进入 -> 记忆展开 -> 情绪深化 -> 抒情收束"],
    },
}


def read_manifest() -> list[dict[str, str]]:
    with MANIFEST_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_tasks() -> list[dict[str, str]]:
    with TASKS_PATH.open(encoding="utf-8-sig", newline="") as handle:
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


def material_text(row: dict[str, str]) -> str:
    return extract_docx_text(Path(row["source_path"]))


def split_materials(items: list[dict[str, str]]) -> list[tuple[str, dict[str, str]]]:
    sorted_items = sorted(items, key=lambda row: row["material_id"])
    total = len(sorted_items)
    holdout_count = max(1, round(total * 0.2))
    dev_count = 1 if total >= 5 else 0
    profile_count = total - holdout_count - dev_count
    output = []
    for index, item in enumerate(sorted_items):
        if index < profile_count:
            role = "profile_rag"
        elif index < profile_count + dev_count:
            role = "development"
        else:
            role = "blind_holdout"
        output.append((role, item))
    return output


def corpus_text(materials: list[dict[str, str]]) -> str:
    chunks = []
    for row in materials:
        try:
            chunks.append(material_text(row))
        except Exception:
            continue
    return "\n".join(chunks)


def corpus_metrics(materials: list[dict[str, str]]) -> dict:
    text = corpus_text(materials)
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    sentences = [
        item.strip()
        for item in re.split(r"[。！？!?]+", text)
        if item.strip()
    ]
    sentence_lengths = [len(re.sub(r"\s+", "", item)) for item in sentences]
    punctuation_counter = Counter(char for char in text if char in "，。！？；：、“”‘’（）《》——…,.!?;:")
    total_chars = sum(int(row["doc_char_count"] or 0) for row in materials)
    total_paragraphs = len(paragraphs)
    avg_paragraph_len = round(total_chars / total_paragraphs, 2) if total_paragraphs else 0
    avg_doc_len = round(total_chars / len(materials), 2) if materials else 0
    avg_sentence_len = round(sum(sentence_lengths) / len(sentence_lengths), 2) if sentence_lengths else 0
    short_ratio = round(sum(1 for length in sentence_lengths if length <= 15) / len(sentence_lengths), 3) if sentence_lengths else 0
    long_ratio = round(sum(1 for length in sentence_lengths if length >= 45) / len(sentence_lengths), 3) if sentence_lengths else 0
    return {
        "average_sentence_length": avg_sentence_len,
        "short_sentence_ratio": short_ratio,
        "long_sentence_ratio": long_ratio,
        "average_paragraph_length": avg_paragraph_len,
        "average_doc_length": avg_doc_len,
        "paragraph_count": total_paragraphs,
        "sentence_count": len(sentence_lengths),
        "punctuation": punctuation_counter,
        "notes": f"Automated profile/RAG-pool metrics: avg sentence {avg_sentence_len} chars, short ratio {short_ratio}, long ratio {long_ratio}, avg paragraph {avg_paragraph_len} chars.",
    }


def genre_scope(materials: list[dict[str, str]]) -> list[str]:
    genres = Counter(row["genre"] for row in materials)
    if "诗歌" in genres and len(genres) == 1:
        return ["poetry"]
    if any("散文" in genre or "随笔" in genre for genre in genres):
        return ["prose"]
    return ["mixed"]


def style_profile(writer_id: str, materials: list[dict[str, str]]) -> dict:
    notes = STYLE_NOTES[writer_id]
    metrics = corpus_metrics(materials)
    punctuation_notes = [
        f"{mark}: {count}"
        for mark, count in metrics["punctuation"].most_common(8)
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "style_profile_id": f"style_{writer_id}_v1",
        "writer_id": writer_id,
        "version": 1,
        "language": "zh-CN",
        "genre_scope": genre_scope(materials),
        "source_material_ids": [row["material_id"] for row in materials],
        "summary": {
            "one_sentence": notes["one_sentence"],
            "long_description": notes["long_description"],
        },
        "features": {
            "themes": notes["themes"],
            "opening_patterns": notes["opening_patterns"],
            "ending_patterns": notes["ending_patterns"],
            "sentence_rhythm": {
                "average_sentence_length": metrics["average_sentence_length"],
                "short_sentence_ratio": metrics["short_sentence_ratio"],
                "long_sentence_ratio": metrics["long_sentence_ratio"],
                "notes": metrics["notes"],
            },
            "paragraph_structure": notes["paragraph_structure"]
            + [
                f"profile/RAG pool average paragraph length: {metrics['average_paragraph_length']} chars",
                f"profile/RAG pool paragraph count: {metrics['paragraph_count']}",
            ],
            "punctuation": punctuation_notes
            + ["Use punctuation distribution as a hint, not as a rigid rule."],
            "lexical_preferences": [
                "Candidate semantic fields: " + ", ".join(notes["themes"]),
                "Candidate imagery fields: " + ", ".join(notes["imagery"]),
                "Needs human review before public-facing use.",
            ],
            "imagery": notes["imagery"],
            "rhetorical_devices": notes["rhetorical_devices"],
            "narrative_distance": notes["narrative_distance"],
            "emotional_intensity": notes["emotional_intensity"],
            "structure_patterns": notes["structure_patterns"],
        },
        "constraints": {
            "must_do": [
                "只把材料作为风格证据，不复述原文内容",
                "优先学习语气、节奏、结构和意象选择",
                "生成后必须做复制检测",
            ],
            "must_avoid": [
                "大段沿用源材料表达",
                "直接声称作品由原作者本人创作",
                "把内部评测结论当成公网宣传结论",
            ],
            "copying_guardrails": [
                "检查最长公共子串",
                "检查连续 n-gram 重合",
                "记录所有召回 material_id 和 chunk_id",
            ],
        },
        "provenance": {
            "created_at": now,
            "created_by": "codex",
            "method": "automated_eval_pack_v1_plus_manual_topic_notes",
            "approval_status": "draft",
        },
    }


def writer_profile_md(writer_id: str, display_name: str, materials: list[dict[str, str]], split_rows: list[tuple[str, dict[str, str]]]) -> str:
    total_chars = sum(int(row["doc_char_count"] or 0) for row in materials)
    genres = ", ".join(f"{genre}({count})" for genre, count in Counter(row["genre"] for row in materials).items())
    role_to_ids = defaultdict(list)
    for role, row in split_rows:
        role_to_ids[role].append(row["material_id"])
    titles = "\n".join(f"- {row['material_id']}: {row['title']}" for row in materials)
    notes = STYLE_NOTES[writer_id]
    return f"""# {display_name} Writer Profile

## Identity

- writer_id: {writer_id}
- display_name: {display_name}
- approved_use: internal_eval, internal_rag_experiment
- training_use: false
- profile_status: draft

## Corpus Summary

- material_count: {len(materials)}
- character_count: {total_chars}
- genres: {genres}
- profile_rag_material_ids: {", ".join(role_to_ids["profile_rag"])}
- development_material_ids: {", ".join(role_to_ids["development"])}
- blind_holdout_material_ids: {", ".join(role_to_ids["blind_holdout"])}

## Materials

{titles}

## Draft Style Notes

- summary: {notes["one_sentence"]}
- recurring_themes: {", ".join(notes["themes"])}
- opening_patterns: {"; ".join(notes["opening_patterns"])}
- ending_patterns: {"; ".join(notes["ending_patterns"])}
- imagery: {", ".join(notes["imagery"])}
- narrative_distance: {notes["narrative_distance"]}
- emotional_intensity: {notes["emotional_intensity"]}

## Review Notes

- This is a draft profile for the first internal evaluation run.
- Do not paste full source text into this profile.
- Human review should refine punctuation, lexical habits, sentence rhythm, and examples before public-facing use.
"""


def main() -> None:
    rows = read_manifest()
    tasks = read_tasks()
    selected = [row for row in rows if row["writer_id"] in SELECTED_WRITER_IDS]
    by_writer: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        by_writer[row["writer_id"]].append(row)

    selected_writer_rows = []
    holdout_rows = []
    for writer_id in SELECTED_WRITER_IDS:
        materials = sorted(by_writer[writer_id], key=lambda row: row["material_id"])
        display_name = materials[0]["writer_display_name"]
        split_rows = split_materials(materials)
        writer_dir = WRITERS_ROOT / writer_id
        writer_dir.mkdir(parents=True, exist_ok=True)
        profile_materials = [row for role, row in split_rows if role == "profile_rag"]
        (writer_dir / "writer_profile.md").write_text(
            writer_profile_md(writer_id, display_name, materials, split_rows),
            encoding="utf-8",
        )
        (writer_dir / "style_profile.json").write_text(
            json.dumps(style_profile(writer_id, profile_materials), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        total_chars = sum(int(row["doc_char_count"] or 0) for row in materials)
        selected_writer_rows.append(
            {
                "run_id": "mvp_style_eval_v1",
                "writer_id": writer_id,
                "writer_display_name": display_name,
                "material_count": str(len(materials)),
                "character_count": str(total_chars),
                "genre_scope": ",".join(genre_scope(materials)),
                "selection_reason": "multi-document corpus supports document-level split",
                "status": "selected",
            }
        )
        for role, row in split_rows:
            holdout_rows.append(
                {
                    "split_id": "split_mvp_v1",
                    "writer_id": writer_id,
                    "material_id": row["material_id"],
                    "split_role": role,
                    "reason": "deterministic document-level split for first internal evaluation",
                    "locked_by": "codex",
                    "locked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "notes": "",
                }
            )

    with SELECTED_WRITERS_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "run_id",
            "writer_id",
            "writer_display_name",
            "material_count",
            "character_count",
            "genre_scope",
            "selection_reason",
            "status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected_writer_rows)

    with HOLDOUT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "split_id",
            "writer_id",
            "material_id",
            "split_role",
            "reason",
            "locked_by",
            "locked_at",
            "notes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(holdout_rows)

    task_instances = []
    round_robin = {
        "ART": ["writer_moyan", "writer_yujian"],
        "ESS": ["writer_yujian", "writer_moyan"],
        "POE": ["writer_wangjiaxin", "writer_bomu", "writer_handong", "writer_gongxueming"],
        "NOV": ["writer_moyan"],
    }
    prefix_counts = defaultdict(int)
    for task in tasks:
        prefix = task["task_id"].split("-", 1)[0]
        writers = round_robin[prefix]
        writer_id = writers[prefix_counts[prefix] % len(writers)]
        prefix_counts[prefix] += 1
        instance = dict(task)
        instance["base_task_id"] = task["task_id"]
        instance["task_id"] = f"{task['task_id']}_{writer_id.replace('writer_', '')}"
        instance["writer_id"] = writer_id
        instance["style_profile_id"] = f"style_{writer_id}_v1"
        instance["reference_material_ids"] = ""
        instance["status"] = "ready"
        task_instances.append(instance)

    task_fieldnames = [
        "task_id",
        "base_task_id",
        "writer_id",
        "genre",
        "style_profile_id",
        "task_type",
        "title",
        "brief",
        "target_length",
        "target_reader",
        "must_include",
        "must_avoid",
        "reference_material_ids",
        "eval_focus",
        "difficulty",
        "status",
    ]
    with TASK_INSTANCES_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=task_fieldnames)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in task_fieldnames} for row in task_instances)

    print(f"selected writers: {len(selected_writer_rows)}")
    print(f"split materials: {len(holdout_rows)}")
    print(f"task instances: {len(task_instances)}")


if __name__ == "__main__":
    main()
