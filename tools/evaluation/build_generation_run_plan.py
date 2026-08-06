import csv
import json
from pathlib import Path


EVAL_ROOT = Path("eval_sets/mvp_style_eval_v1")
TASK_INSTANCES_PATH = EVAL_ROOT / "task_instances.csv"
PROMPT_REGISTRY_PATH = EVAL_ROOT / "prompt_registry.json"
HOLDOUT_PATH = EVAL_ROOT / "holdout_manifest.csv"
RUN_PLAN_PATH = EVAL_ROOT / "generation_run_plan.csv"
REQUESTS_PATH = EVAL_ROOT / "prompt_packets" / "generation_requests.jsonl"


REQUIRED_VARIANTS = ["baseline_direct", "style_prompt_only", "style_profile_rag"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def allowed_rag_materials() -> dict[str, list[str]]:
    by_writer: dict[str, list[str]] = {}
    for row in read_csv(HOLDOUT_PATH):
        if row["split_role"] == "profile_rag":
            by_writer.setdefault(row["writer_id"], []).append(row["material_id"])
    return {writer_id: sorted(material_ids) for writer_id, material_ids in by_writer.items()}


def prompt_versions() -> dict[str, str]:
    registry = json.load(PROMPT_REGISTRY_PATH.open(encoding="utf-8"))
    return {
        item["variant"]: item["prompt_version"]
        for item in registry["variants"]
        if item["variant"] in REQUIRED_VARIANTS
    }


def build_system_prompt(variant: str) -> str:
    base = "你是内部评测用中文写作模型。严格完成任务，不要解释你的过程。"
    if variant == "baseline_direct":
        return base + " 不使用任何目标作者风格档案或素材。"
    if variant == "style_prompt_only":
        return base + " 只依据提供的 Style Profile 学习语气、结构和节奏；不要虚构源材料内容。"
    if variant == "style_profile_rag":
        return base + " 依据 Style Profile 和检索到的风格证据生成；吸收风格，不复制原句。"
    raise ValueError(f"unknown variant: {variant}")


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
    tasks = read_csv(TASK_INSTANCES_PATH)
    versions = prompt_versions()
    rag_materials = allowed_rag_materials()
    REQUESTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    run_rows = []
    requests = []
    for task in tasks:
        for variant in REQUIRED_VARIANTS:
            generation_id = f"gen_{task['task_id']}_{variant}"
            prompt_version = versions[variant]
            output_path = f"eval_sets/mvp_style_eval_v1/outputs/{variant}/{generation_id}.md"
            style_profile_path = ""
            retrieval_material_ids = ""
            if variant in {"style_prompt_only", "style_profile_rag"}:
                style_profile_path = f"eval_sets/mvp_style_eval_v1/writers/{task['writer_id']}/style_profile.json"
            if variant == "style_profile_rag":
                retrieval_material_ids = "|".join(rag_materials[task["writer_id"]])

            run_rows.append(
                {
                    "generation_id": generation_id,
                    "task_id": task["task_id"],
                    "writer_id": task["writer_id"],
                    "variant": variant,
                    "prompt_version": prompt_version,
                    "style_profile_path": style_profile_path,
                    "retrieval_split_role": "profile_rag" if variant == "style_profile_rag" else "",
                    "retrieval_material_ids": retrieval_material_ids,
                    "output_path": output_path,
                    "status": "ready",
                }
            )

            requests.append(
                {
                    "generation_id": generation_id,
                    "task_id": task["task_id"],
                    "writer_id": task["writer_id"],
                    "variant": variant,
                    "prompt_version": prompt_version,
                    "system_prompt": build_system_prompt(variant),
                    "user_prompt": build_user_prompt(task),
                    "style_profile_path": style_profile_path,
                    "retrieval_policy": {
                        "enabled": variant == "style_profile_rag",
                        "allowed_split_role": "profile_rag" if variant == "style_profile_rag" else "",
                        "allowed_material_ids": rag_materials[task["writer_id"]] if variant == "style_profile_rag" else [],
                        "max_chunks": 6,
                        "max_chars_per_chunk": 500,
                        "exclude_split_roles": ["development", "blind_holdout"],
                    },
                    "output_path": output_path,
                }
            )

    with RUN_PLAN_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "generation_id",
            "task_id",
            "writer_id",
            "variant",
            "prompt_version",
            "style_profile_path",
            "retrieval_split_role",
            "retrieval_material_ids",
            "output_path",
            "status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(run_rows)

    with REQUESTS_PATH.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(request, ensure_ascii=False) + "\n")

    print(f"generation run rows: {len(run_rows)}")
    print(f"generation requests: {len(requests)}")


if __name__ == "__main__":
    main()
