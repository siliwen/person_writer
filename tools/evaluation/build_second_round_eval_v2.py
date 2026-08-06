import csv
import json
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = PROJECT_ROOT / "eval_sets" / "mvp_style_eval_v1"
ROUND_ROOT = EVAL_ROOT / "second_round_v2"
TASK_INSTANCES_PATH = EVAL_ROOT / "task_instances.csv"
HOLDOUT_PATH = EVAL_ROOT / "holdout_manifest.csv"
SCORES_PATH = EVAL_ROOT / "scores.csv"
BLIND_KEY_PATH = EVAL_ROOT / "reviews" / "blind_key.csv"
RUN_PLAN_PATH = ROUND_ROOT / "generation_run_plan_v2.csv"
SELECTED_TASKS_PATH = ROUND_ROOT / "selected_tasks_v2.csv"
REQUESTS_PATH = EVAL_ROOT / "prompt_packets" / "generation_requests_v2.jsonl"

DIMENSIONS_FOR_SELECTION = [
    "style_similarity",
    "task_completion",
    "genre_quality",
    "editing_cost",
    "rag_use_quality",
    "ai_taste_control",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def allowed_rag_materials() -> dict[str, list[str]]:
    by_writer: dict[str, list[str]] = {}
    for row in read_csv(HOLDOUT_PATH):
        if row["split_role"] == "profile_rag":
            by_writer.setdefault(row["writer_id"], []).append(row["material_id"])
    return {writer_id: sorted(material_ids) for writer_id, material_ids in by_writer.items()}


def select_loss_tasks() -> list[dict[str, str]]:
    blind_key = read_csv(BLIND_KEY_PATH)
    generation_to_variant = {row["generation_id"]: row["variant"] for row in blind_key}
    scores_by_task: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in read_csv(SCORES_PATH):
        variant = generation_to_variant[row["generation_id"]]
        if variant in {"style_prompt_only", "style_profile_rag"}:
            scores_by_task[row["task_id"]][variant] = row

    selected = []
    for task_id, rows in scores_by_task.items():
        prompt = rows.get("style_prompt_only")
        rag = rows.get("style_profile_rag")
        if not prompt or not rag:
            continue
        prompt_total = sum(int(prompt[dim]) for dim in DIMENSIONS_FOR_SELECTION)
        rag_total = sum(int(rag[dim]) for dim in DIMENSIONS_FOR_SELECTION)
        delta = rag_total - prompt_total
        if delta < 0:
            selected.append(
                {
                    "task_id": task_id,
                    "prompt_only_total": str(prompt_total),
                    "rag_v1_total": str(rag_total),
                    "rag_v1_minus_prompt_only": str(delta),
                    "prompt_only_style": prompt["style_similarity"],
                    "rag_v1_style": rag["style_similarity"],
                    "prompt_only_preference": prompt["preference_group"],
                    "rag_v1_preference": rag["preference_group"],
                }
            )
    return sorted(selected, key=lambda row: (int(row["rag_v1_minus_prompt_only"]), row["task_id"]))


def genre_policy(genre: str) -> tuple[int, int, str, str]:
    if genre == "小说章节":
        return (
            2,
            320,
            "叙事视角 冲突推进 动作链 对话节奏 场景调度 叙述距离",
            "\n".join(
                [
                    "1. Style Profile 是主规范，RAG 片段只是叙事机制证据。",
                    "2. 小说章节只学习视角、动作链、冲突推进、对话密度和场景调度。",
                    "3. 不要堆砌乡土物件、动物、食物、地名或旧物件；每个细节必须推动人物关系或冲突。",
                    "4. 不要借用片段里的专名、真实作品名、完整句子或连续意象组合。",
                    "5. 输出要优先保证任务情节、人物关系和叙事推进，而不是炫示风格元素。",
                ]
            ),
        )
    if genre == "诗歌":
        return (
            2,
            240,
            "诗行节奏 停顿 留白 重复 收束 句法压缩 情绪克制",
            "\n".join(
                [
                    "1. Style Profile 是主规范，RAG 片段只是节奏机制证据。",
                    "2. 诗歌只学习行长、停顿、复沓、留白、转折和收束方式。",
                    "3. 不要照搬主题词、意象词、物件组合或片段里的表达。",
                    "4. 意象必须少而准；宁可克制，不要堆叠。",
                    "5. 输出要优先保证诗歌内部节奏和余味，而不是把风格关键词塞进去。",
                ]
            ),
        )
    if genre == "散文":
        return (
            3,
            360,
            "空间进入 观察顺序 身体感 句长变化 思考转折 开放式收束",
            "\n".join(
                [
                    "1. Style Profile 是主规范，RAG 片段只是观察机制证据。",
                    "2. 散文只学习进入场景的方式、观察顺序、句长变化和思考转折。",
                    "3. 少用片段中的实体名词；不要复制专名、地点名或完整比喻。",
                    "4. 先让场景自然成立，再做思考，不要概念先行。",
                ]
            ),
        )
    return (
        3,
        360,
        "观点结构 观察细节 例子组织 开头方式 论证推进 收束方式",
        "\n".join(
            [
                "1. Style Profile 是主规范，RAG 片段只是论证和观察机制证据。",
                "2. 文章可以学习具体观察如何服务观点，但不要复制片段事实或原句。",
                "3. 保持清晰论点、具体场景和可读结构，不要为了风格牺牲任务完成度。",
            ]
        ),
    )


def build_system_prompt(genre: str) -> str:
    shared = (
        "你是内部评测用中文写作模型。严格完成任务，不解释过程。"
        "你必须以 Style Profile 为最高优先级，RAG 只作为低权重风格机制证据。"
        "不要复制 RAG 片段原句、专名、真实作品名或连续意象组合。"
    )
    if genre == "小说章节":
        return shared + "本任务优先保证叙事推进、人物动作、视角稳定和冲突结构；禁止风格元素堆砌。"
    if genre == "诗歌":
        return shared + "本任务优先保证诗行节奏、停顿、留白和收束；禁止把意象词表写成诗。"
    if genre == "散文":
        return shared + "本任务优先保证观察顺序、空间进入和思考自然发生。"
    return shared + "本任务优先保证观点清楚、细节有效和结构可读。"


def build_user_prompt(task: dict[str, str]) -> str:
    return "\n".join(
        [
            f"任务类型：{task['task_type']}",
            f"文体：{task['genre']}",
            f"标题/主题：{task['title']}",
            f"需求：{task['brief']}",
            f"目标长度：{task['target_length']}",
            f"目标读者：{task['target_reader']}",
            f"必须包含：{task['must_include']}",
            f"必须避免：{task['must_avoid']}",
            f"评测重点：{task['eval_focus']}",
        ]
    )


def main() -> None:
    tasks = {row["task_id"]: row for row in read_csv(TASK_INSTANCES_PATH)}
    selected = select_loss_tasks()
    rag_materials = allowed_rag_materials()
    ROUND_ROOT.mkdir(parents=True, exist_ok=True)
    REQUESTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    plan_rows = []
    requests = []
    for row in selected:
        task = tasks[row["task_id"]]
        max_chunks, max_chars, retrieval_hint, usage_instruction = genre_policy(task["genre"])
        generation_id = f"gen_{task['task_id']}_style_profile_rag_v2"
        output_path = f"eval_sets/mvp_style_eval_v1/outputs/style_profile_rag_v2/{generation_id}.md"
        style_profile_path = f"eval_sets/mvp_style_eval_v1/writers/{task['writer_id']}/style_profile.json"
        plan_rows.append(
            {
                "generation_id": generation_id,
                "task_id": task["task_id"],
                "writer_id": task["writer_id"],
                "genre": task["genre"],
                "variant": "style_profile_rag_v2",
                "prompt_version": "style_profile_rag_v2",
                "style_profile_path": style_profile_path,
                "retrieval_material_ids": "|".join(rag_materials[task["writer_id"]]),
                "max_chunks": str(max_chunks),
                "max_chars_per_chunk": str(max_chars),
                "output_path": output_path,
                "status": "ready",
            }
        )
        retrieval_query = " ".join(
            [
                task["genre"],
                task["task_type"],
                task["title"],
                task["brief"],
                task["eval_focus"],
                retrieval_hint,
            ]
        )
        requests.append(
            {
                "generation_id": generation_id,
                "task_id": task["task_id"],
                "writer_id": task["writer_id"],
                "variant": "style_profile_rag_v2",
                "prompt_version": "style_profile_rag_v2",
                "system_prompt": build_system_prompt(task["genre"]),
                "user_prompt": build_user_prompt(task),
                "style_profile_path": style_profile_path,
                "retrieval_query": retrieval_query,
                "rag_usage_instruction": usage_instruction,
                "retrieval_policy": {
                    "enabled": True,
                    "allowed_split_role": "profile_rag",
                    "allowed_material_ids": rag_materials[task["writer_id"]],
                    "max_chunks": max_chunks,
                    "max_chars_per_chunk": max_chars,
                    "exclude_split_roles": ["development", "blind_holdout"],
                    "evidence_mode": "genre_mechanism_v2",
                },
                "output_path": output_path,
            }
        )

    write_csv(
        SELECTED_TASKS_PATH,
        selected,
        [
            "task_id",
            "prompt_only_total",
            "rag_v1_total",
            "rag_v1_minus_prompt_only",
            "prompt_only_style",
            "rag_v1_style",
            "prompt_only_preference",
            "rag_v1_preference",
        ],
    )
    write_csv(
        RUN_PLAN_PATH,
        plan_rows,
        [
            "generation_id",
            "task_id",
            "writer_id",
            "genre",
            "variant",
            "prompt_version",
            "style_profile_path",
            "retrieval_material_ids",
            "max_chunks",
            "max_chars_per_chunk",
            "output_path",
            "status",
        ],
    )
    with REQUESTS_PATH.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(request, ensure_ascii=False) + "\n")

    print(f"selected loss tasks: {len(selected)}")
    print(f"generation requests: {len(requests)}")
    print(str(REQUESTS_PATH))


if __name__ == "__main__":
    main()
