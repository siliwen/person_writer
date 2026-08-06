import csv
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = PROJECT_ROOT / "eval_sets" / "mvp_style_eval_v1"
SCORES_PATH = EVAL_ROOT / "scores.csv"
BLIND_KEY_PATH = EVAL_ROOT / "reviews" / "blind_key.csv"
COPYING_REPORT_PATH = EVAL_ROOT / "copying_report.csv"
SUMMARY_PATH = EVAL_ROOT / "reports" / "llm_blind_review_summary.md"

DIMENSIONS = [
    "style_similarity",
    "task_completion",
    "genre_quality",
    "editing_cost",
    "rag_use_quality",
    "ai_taste_control",
    "safety_copyright",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0


def main() -> None:
    scores = read_csv(SCORES_PATH)
    blind_key = read_csv(BLIND_KEY_PATH)
    copying = read_csv(COPYING_REPORT_PATH)
    generation_to_variant = {row["generation_id"]: row["variant"] for row in blind_key}
    copy_risk = {row["generation_id"]: row["risk_level"] for row in copying}

    for row in scores:
        row["variant"] = generation_to_variant[row["generation_id"]]

    by_variant = defaultdict(list)
    for row in scores:
        by_variant[row["variant"]].append(row)

    packets = defaultdict(list)
    generation_to_packet = {row["generation_id"]: row["packet_id"] for row in blind_key}
    for row in scores:
        packets[generation_to_packet[row["generation_id"]]].append(row)

    winners = Counter()
    usable = Counter()
    for row in scores:
        if row["preference_group"] in {"winner", "tie_first"}:
            winners[row["variant"]] += 1
        if row["usable_bucket"] in {"usable", "usable_after_editing"}:
            usable[row["variant"]] += 1

    direct_style = {
        row["task_id"]: int(row["style_similarity"])
        for row in scores
        if row["variant"] == "baseline_direct"
    }
    rag_style = {
        row["task_id"]: int(row["style_similarity"])
        for row in scores
        if row["variant"] == "style_profile_rag"
    }
    style_deltas = [rag_style[task_id] - direct_style[task_id] for task_id in direct_style.keys() & rag_style.keys()]
    rag_over_direct_wins = sum(1 for delta in style_deltas if delta > 0)
    rag_over_direct_ties = sum(1 for delta in style_deltas if delta == 0)

    lines = [
        "# LLM Blind Review Summary",
        "",
        "Evaluator: qwen-plus as blind LLM judge",
        "",
        "## Coverage",
        "",
        f"- Score rows: {len(scores)}",
        f"- Packets scored: {len(packets)}",
        f"- Copying high/medium incidents: {sum(1 for risk in copy_risk.values() if risk in {'high', 'medium'})}",
        "",
        "## Variant Averages",
        "",
        "| Variant | N | Style | Task | Genre | Editing | RAG Use | AI Taste | Safety | Usable Count | Winner/Tie Count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in ["baseline_direct", "style_prompt_only", "style_profile_rag"]:
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
            "## Style-RAG vs Direct",
            "",
            f"- Style score delta average: {avg(style_deltas):.3f}",
            f"- Style-RAG higher style score: {rag_over_direct_wins}/40",
            f"- Style-RAG tied direct style score: {rag_over_direct_ties}/40",
            f"- Style-RAG pairwise non-loss rate: {(rag_over_direct_wins + rag_over_direct_ties) / 40:.3f}",
            "",
            "## Gate Check",
            "",
        ]
    )
    rag_win_rate = winners["style_profile_rag"] / 40
    rag_usable_rate = usable["style_profile_rag"] / 40
    style_delta_avg = avg(style_deltas)
    gates = [
        ("Style-RAG preference win rate >= 60%", rag_win_rate >= 0.6, f"{rag_win_rate:.3f}"),
        ("Average style score improvement >= 0.5", style_delta_avg >= 0.5, f"{style_delta_avg:.3f}"),
        ("At least 60% usable after editing", rag_usable_rate >= 0.6, f"{rag_usable_rate:.3f}"),
        ("No material copying incidents", all(risk not in {"high", "medium"} for risk in copy_risk.values()), "pass"),
    ]
    for name, passed, value in gates:
        lines.append(f"- [{'x' if passed else ' '}] {name}: {value}")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "This is an automated LLM-judge result. Treat it as the first quantitative signal, not final expert validation.",
        ]
    )
    if all(passed for _, passed, _ in gates):
        lines.append("Initial gate result: pass.")
    else:
        lines.append("Initial gate result: not passed; inspect failed dimensions before moving to MVP build.")

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(SUMMARY_PATH))


if __name__ == "__main__":
    main()
