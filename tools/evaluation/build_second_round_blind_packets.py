import csv
import random
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = PROJECT_ROOT / "eval_sets" / "mvp_style_eval_v1"
ROUND_ROOT = EVAL_ROOT / "second_round_v2"
TASK_INSTANCES_PATH = EVAL_ROOT / "task_instances.csv"
GENERATION_MANIFEST_PATH = EVAL_ROOT / "generation_manifest.csv"
SELECTED_TASKS_PATH = ROUND_ROOT / "selected_tasks_v2.csv"
PACKETS_DIR = ROUND_ROOT / "reviews" / "blind_packets"
PACKET_MANIFEST_PATH = ROUND_ROOT / "reviews" / "blind_review_packets_v2.csv"
BLIND_KEY_PATH = ROUND_ROOT / "reviews" / "blind_key_v2.csv"

VARIANTS = ["style_prompt_only", "style_profile_rag", "style_profile_rag_v2"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    tasks = {row["task_id"]: row for row in read_csv(TASK_INSTANCES_PATH)}
    selected_task_ids = [row["task_id"] for row in read_csv(SELECTED_TASKS_PATH)]
    generations = read_csv(GENERATION_MANIFEST_PATH)
    by_task_variant = {(row["task_id"], row["variant"]): row for row in generations}

    rng = random.Random(202608052)
    packet_rows = []
    key_rows = []
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)

    for index, task_id in enumerate(selected_task_ids, start=1):
        task = tasks[task_id]
        generation_rows = []
        for variant in VARIANTS:
            generation = by_task_variant.get((task_id, variant))
            if generation is None:
                raise SystemExit(f"missing generation for {task_id} {variant}")
            generation_rows.append(generation)

        labels = ["A", "B", "C"]
        rng.shuffle(labels)
        assigned = list(zip(labels, generation_rows))
        assigned.sort(key=lambda item: item[0])
        packet_id = f"v2_packet_{index:03d}_{task_id}"
        packet_path = PACKETS_DIR / f"{packet_id}.md"
        sections = [
            f"# Second Round Blind Review Packet {packet_id}",
            "",
            "## Task",
            "",
            f"- task_id: {task_id}",
            f"- writer_id: {task['writer_id']}",
            f"- genre: {task['genre']}",
            f"- task_type: {task['task_type']}",
            f"- title: {task['title']}",
            f"- brief: {task['brief']}",
            f"- target_length: {task['target_length']}",
            f"- target_reader: {task['target_reader']}",
            f"- must_include: {task['must_include']}",
            f"- must_avoid: {task['must_avoid']}",
            f"- eval_focus: {task['eval_focus']}",
            "",
        ]
        packet_row = {
            "packet_id": packet_id,
            "task_id": task_id,
            "writer_id": task["writer_id"],
            "genre": task["genre"],
            "packet_path": str(packet_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        }
        for label, generation in assigned:
            output_path = PROJECT_ROOT / generation["output_path"]
            output_text = output_path.read_text(encoding="utf-8").strip()
            sections.extend([f"## Output {label}", "", output_text, ""])
            packet_row[f"output_{label.lower()}_generation_id"] = generation["generation_id"]
            key_rows.append(
                {
                    "packet_id": packet_id,
                    "task_id": task_id,
                    "blind_label": label,
                    "generation_id": generation["generation_id"],
                    "variant": generation["variant"],
                    "output_path": generation["output_path"],
                }
            )
        packet_path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
        packet_rows.append(packet_row)

    write_csv(
        PACKET_MANIFEST_PATH,
        packet_rows,
        [
            "packet_id",
            "task_id",
            "writer_id",
            "genre",
            "packet_path",
            "output_a_generation_id",
            "output_b_generation_id",
            "output_c_generation_id",
        ],
    )
    write_csv(
        BLIND_KEY_PATH,
        key_rows,
        ["packet_id", "task_id", "blind_label", "generation_id", "variant", "output_path"],
    )
    print(f"second round blind packets: {len(packet_rows)}")
    print(f"second round blind key rows: {len(key_rows)}")


if __name__ == "__main__":
    main()
