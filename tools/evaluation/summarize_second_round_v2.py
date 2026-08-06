import csv
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = PROJECT_ROOT / "eval_sets" / "mvp_style_eval_v1"
ROUND_ROOT = EVAL_ROOT / "second_round_v2"
SCORES_PATH = ROUND_ROOT / "scores_v2.csv"
BLIND_KEY_PATH = ROUND_ROOT / "reviews" / "blind_key_v2.csv"
COPYING_REPORT_PATH = ROUND_ROOT / "copying_report_v2.csv"
SUMMARY_PATH = ROUND_ROOT / "reports" / "llm_blind_review_summary_v2.md"

VARIANTS = ["style_prompt_only", "style_profile_rag", "style_profile_rag_v2"]
DIMENSIONS = [
    "style_similarity",
    "task_completion",
    "genre_quality",
    "editing_cost",
    "rag_use_quality",
    "ai_taste_control",
    "safety_copyright",
]
DIMENSIONS_NO_SAFETY = DIMENSIONS[:-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0


def main() -> None:
    scores = read_csv(SCORES_PATH)
    blind_key = read_csv(BLIND_KEY_PATH)
    copying = read_csv(COPYING_REPORT_PATH) if COPYING_REPORT_PATH.exists() else []
    generation_to_variant = {row["generation_id"]: row["variant"] for row in blind_key}
    generation_to_packet = {row["generation_id"]: row["packet_id"] for row in blind_key}
    copy_risk = {row["generation_id"]: row["risk_level"] for row in copying}

    for row in scores:
        row["variant"] = generation_to_variant[row["generation_id"]]
        row["packet_id"] = generation_to_packet[row["generation_id"]]

    by_variant = defaultdict(list)
    by_packet = defaultdict(dict)
    for row in scores:
        by_variant[row["variant"]].append(row)
        by_packet[row["packet_id"]][row["variant"]] = row

    winners = Counter()
    usable = Counter()
    for row in scores:
        if row["preference_group"] in {"winner", "tie_first"}:
            winners[row["variant"]] += 1
        if row["usable_bucket"] in {"usable", "usable_after_editing"}:
            usable[row["variant"]] += 1

    pairwise = {"v2_over_prompt": [], "v2_over_v1": []}
    v2_wins_prompt = 0
    v2_ties_prompt = 0
    v2_wins_v1 = 0
    v2_ties_v1 = 0
    for variants in by_packet.values():
        v2 = variants["style_profile_rag_v2"]
        prompt = variants["style_prompt_only"]
        v1 = variants["style_profile_rag"]
        v2_total = sum(int(v2[dim]) for dim in DIMENSIONS_NO_SAFETY)
        prompt_total = sum(int(prompt[dim]) for dim in DIMENSIONS_NO_SAFETY)
        v1_total = sum(int(v1[dim]) for dim in DIMENSIONS_NO_SAFETY)
        pairwise["v2_over_prompt"].append(v2_total - prompt_total)
        pairwise["v2_over_v1"].append(v2_total - v1_total)
        if v2_total > prompt_total:
            v2_wins_prompt += 1
        elif v2_total == prompt_total:
            v2_ties_prompt += 1
        if v2_total > v1_total:
            v2_wins_v1 += 1
        elif v2_total == v1_total:
            v2_ties_v1 += 1

    packet_count = len(by_packet)
    v2_win_rate = winners["style_profile_rag_v2"] / packet_count if packet_count else 0
    v2_usable_rate = usable["style_profile_rag_v2"] / packet_count if packet_count else 0
    v2_prompt_non_loss = (v2_wins_prompt + v2_ties_prompt) / packet_count if packet_count else 0
    v2_v1_non_loss = (v2_wins_v1 + v2_ties_v1) / packet_count if packet_count else 0
    material_copy_incidents = sum(1 for risk in copy_risk.values() if risk in {"high", "medium"})

    lines = [
        "# Second Round LLM Blind Review Summary",
        "",
        "Scope: first-round tasks where `style_profile_rag` lost to `style_prompt_only`.",
        "",
        "## Coverage",
        "",
        f"- Score rows: {len(scores)}",
        f"- Packets scored: {packet_count}",
        f"- V2 copying high/medium incidents: {material_copy_incidents}",
        "",
        "## Variant Averages",
        "",
        "| Variant | N | Style | Task | Genre | Editing | RAG Use | AI Taste | Safety | Usable Count | Winner/Tie Count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        rows = by_variant[variant]
        values = [avg([int(row[dim]) for row in rows]) for dim in DIMENSIONS]
        lines.append(
            f"| {variant} | {len(rows)} | "
            + " | ".join(f"{value:.3f}" for value in values)
            + f" | {usable[variant]} | {winners[variant]} |"
        )

    lines.extend(
        [
            "",
            "## Pairwise Deltas",
            "",
            f"- V2 minus prompt-only average total delta, excluding safety: {avg(pairwise['v2_over_prompt']):.3f}",
            f"- V2 higher than prompt-only: {v2_wins_prompt}/{packet_count}",
            f"- V2 tied prompt-only: {v2_ties_prompt}/{packet_count}",
            f"- V2 non-loss vs prompt-only: {v2_prompt_non_loss:.3f}",
            f"- V2 minus RAG v1 average total delta, excluding safety: {avg(pairwise['v2_over_v1']):.3f}",
            f"- V2 higher than RAG v1: {v2_wins_v1}/{packet_count}",
            f"- V2 tied RAG v1: {v2_ties_v1}/{packet_count}",
            f"- V2 non-loss vs RAG v1: {v2_v1_non_loss:.3f}",
            "",
            "## Gate Check",
            "",
        ]
    )
    gates = [
        ("V2 winner/tie rate >= 60%", v2_win_rate >= 0.6, f"{v2_win_rate:.3f}"),
        ("V2 non-loss vs prompt-only >= 60%", v2_prompt_non_loss >= 0.6, f"{v2_prompt_non_loss:.3f}"),
        ("V2 improves over RAG v1 on selected losses", avg(pairwise["v2_over_v1"]) > 0, f"{avg(pairwise['v2_over_v1']):.3f}"),
        ("V2 usable/editable >= 60%", v2_usable_rate >= 0.6, f"{v2_usable_rate:.3f}"),
        ("No V2 material copying incidents", material_copy_incidents == 0, "pass" if material_copy_incidents == 0 else str(material_copy_incidents)),
    ]
    for name, passed, value in gates:
        lines.append(f"- [{'x' if passed else ' '}] {name}: {value}")
    lines.extend(["", "## Decision", ""])
    if all(passed for _, passed, _ in gates):
        lines.append("Second-round gate result: pass on selected-loss subset; run a full 40-task confirmation before MVP engineering.")
    else:
        lines.append("Second-round gate result: not passed; consider MVP downgrade to style_prompt_only + editable Style Profile.")

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(SUMMARY_PATH))


if __name__ == "__main__":
    main()
