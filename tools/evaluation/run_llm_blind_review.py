import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = PROJECT_ROOT / "eval_sets" / "mvp_style_eval_v1"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env.local"
PACKET_MANIFEST_PATH = EVAL_ROOT / "reviews" / "blind_review_packets.csv"
BLIND_KEY_PATH = EVAL_ROOT / "reviews" / "blind_key.csv"
SCORES_PATH = EVAL_ROOT / "scores.csv"
RAW_REVIEW_DIR = EVAL_ROOT / "reviews" / "llm_judge_raw"

SCORE_FIELDS = [
    "score_id",
    "generation_id",
    "task_id",
    "writer_id",
    "rater_id",
    "blind_label",
    "style_similarity",
    "task_completion",
    "genre_quality",
    "editing_cost",
    "rag_use_quality",
    "ai_taste_control",
    "safety_copyright",
    "usable_bucket",
    "preference_group",
    "comments",
    "scored_at",
]

DIMENSIONS = [
    "style_similarity",
    "task_completion",
    "genre_quality",
    "editing_cost",
    "rag_use_quality",
    "ai_taste_control",
    "safety_copyright",
]


def load_env(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def require_config(env: dict[str, str]) -> dict[str, str]:
    api_key = env.get("DASHSCOPE_API_KEY") or env.get("OPENAI_API_KEY")
    if not api_key or "填入" in api_key or "xxxxxxxx" in api_key:
        raise SystemExit("Missing API key. Fill DASHSCOPE_API_KEY in .env.local.")
    return {
        "model_provider": env.get("MODEL_PROVIDER", "alibaba_bailian"),
        "base_url": env.get("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/"),
        "api_key": api_key,
        "model_name": env.get("JUDGE_MODEL_NAME", env.get("MODEL_NAME", "qwen-plus")),
        "temperature": env.get("JUDGE_TEMPERATURE", "0.1"),
        "top_p": env.get("JUDGE_TOP_P", "0.8"),
        "timeout": env.get("REQUEST_TIMEOUT_SECONDS", "120"),
        "sleep": env.get("REQUEST_SLEEP_SECONDS", "0.5"),
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def existing_packet_ids(rows: list[dict[str, str]], blind_key_path: Path) -> set[str]:
    done = set()
    by_task = {}
    blind_key = read_csv(blind_key_path)
    generation_to_packet = {row["generation_id"]: row["packet_id"] for row in blind_key}
    for row in rows:
        packet_id = generation_to_packet.get(row["generation_id"])
        if packet_id:
            by_task.setdefault(packet_id, set()).add(row["blind_label"])
    for packet_id, labels in by_task.items():
        if labels == {"A", "B", "C"}:
            done.add(packet_id)
    return done


def load_writer_context(writer_id: str) -> str:
    writer_dir = EVAL_ROOT / "writers" / writer_id
    profile_md = (writer_dir / "writer_profile.md").read_text(encoding="utf-8")
    style_json = (writer_dir / "style_profile.json").read_text(encoding="utf-8")
    return profile_md + "\n\nStyle Profile JSON:\n" + style_json


def judge_prompt(packet_text: str, writer_context: str) -> list[dict[str, str]]:
    system = (
        "你是中文写作 SaaS 的内部盲评评审。你必须严格按任务和 Writer 风格档案评分。"
        "你不知道 A/B/C 分别来自哪个生成方案，不要猜测方案名。"
        "请只输出 JSON，不要输出 Markdown。"
    )
    user = f"""
请评审下面一个盲评包中的 A/B/C 三个输出。

评分范围：1-5，分数含义：
1=明显失败；2=较弱且难用；3=部分可用；4=较好，轻度编辑可用；5=强，基本可直接用。

维度：
- style_similarity：是否接近 Writer 的语气、句式、节奏、意象、结构和叙述距离。
- task_completion：是否满足主题、字数、结构、必须包含和必须避免。
- genre_quality：是否符合文章/散文/诗歌/小说章节的文体要求。
- editing_cost：用户需要改多少才能用，分数越高表示修改成本越低。
- rag_use_quality：是否合理吸收风格证据而非堆砌或照抄；即使不知道是否使用 RAG，也按输出表现评分。
- ai_taste_control：是否避免 AI 套话、空泛抒情、模板化转折和夸张表达。
- safety_copyright：是否避免明显复制、隐私、敏感或版权风险。

usable_bucket 只能是：usable / usable_after_editing / not_usable。
preference_group：同一个盲评包里最推荐的输出填 winner，第二名填 second，第三名填 third。如果并列，允许 tie_first / tie_second。

Writer 风格档案：
{writer_context}

盲评包：
{packet_text}

请输出这个 JSON 结构：
{{
  "scores": [
    {{
      "blind_label": "A",
      "style_similarity": 1,
      "task_completion": 1,
      "genre_quality": 1,
      "editing_cost": 1,
      "rag_use_quality": 1,
      "ai_taste_control": 1,
      "safety_copyright": 1,
      "usable_bucket": "not_usable",
      "preference_group": "third",
      "comments": "一句具体评价"
    }}
  ]
}}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_openai_compatible(config: dict[str, str], messages: list[dict[str, str]]) -> dict:
    payload = {
        "model": config["model_name"],
        "messages": messages,
        "temperature": float(config["temperature"]),
        "top_p": float(config["top_p"]),
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        config["base_url"] + "/chat/completions",
        data=data,
        headers={
            "Authorization": "Bearer " + config["api_key"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(config["timeout"])) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def parse_json_response(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def validate_score(item: dict) -> None:
    if item.get("blind_label") not in {"A", "B", "C"}:
        raise ValueError(f"invalid blind_label: {item}")
    for key in DIMENSIONS:
        value = int(item[key])
        if value < 1 or value > 5:
            raise ValueError(f"invalid {key}: {item}")
    if item.get("usable_bucket") not in {"usable", "usable_after_editing", "not_usable"}:
        raise ValueError(f"invalid usable_bucket: {item}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--packet-id", default="")
    parser.add_argument("--packet-manifest", default=str(PACKET_MANIFEST_PATH))
    parser.add_argument("--blind-key", default=str(BLIND_KEY_PATH))
    parser.add_argument("--scores", default=str(SCORES_PATH))
    parser.add_argument("--raw-dir", default=str(RAW_REVIEW_DIR))
    parser.add_argument("--rater-suffix", default="v1")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = require_config(load_env(Path(args.env)))
    packet_manifest_path = Path(args.packet_manifest)
    blind_key_path = Path(args.blind_key)
    scores_path = Path(args.scores)
    raw_review_dir = Path(args.raw_dir)
    packets = read_csv(packet_manifest_path)
    if args.packet_id:
        packets = [row for row in packets if row["packet_id"] == args.packet_id]
    if args.limit:
        packets = packets[: args.limit]

    blind_key = read_csv(blind_key_path)
    packet_label_to_generation = {
        (row["packet_id"], row["blind_label"]): row["generation_id"]
        for row in blind_key
    }
    score_rows = [] if args.overwrite else read_csv(scores_path)
    completed = set() if args.overwrite else existing_packet_ids(score_rows, blind_key_path)

    print(f"packets selected: {len(packets)}")
    if args.dry_run:
        for packet in packets[:5]:
            print(packet["packet_id"], packet["packet_path"])
        return

    raw_review_dir.mkdir(parents=True, exist_ok=True)
    scored_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for index, packet in enumerate(packets, start=1):
        packet_id = packet["packet_id"]
        if packet_id in completed:
            print(f"skip completed {packet_id}")
            continue
        packet_text = (PROJECT_ROOT / packet["packet_path"]).read_text(encoding="utf-8")
        writer_context = load_writer_context(packet["writer_id"])
        print(f"[{index}/{len(packets)}] judging {packet_id}")
        response = call_openai_compatible(config, judge_prompt(packet_text, writer_context))
        content = response["choices"][0]["message"]["content"]
        (raw_review_dir / f"{packet_id}.json").write_text(content, encoding="utf-8")
        data = parse_json_response(content)
        scores = data.get("scores", [])
        if len(scores) != 3:
            raise RuntimeError(f"{packet_id} expected 3 scores, got {len(scores)}")
        for item in scores:
            validate_score(item)
            label = item["blind_label"]
            generation_id = packet_label_to_generation[(packet_id, label)]
            score_rows.append(
                {
                    "score_id": f"score_{packet_id}_{label}",
                    "generation_id": generation_id,
                    "task_id": packet["task_id"],
                    "writer_id": packet["writer_id"],
                    "rater_id": f"llm_judge_{config['model_name']}_{args.rater_suffix}",
                    "blind_label": label,
                    "style_similarity": str(int(item["style_similarity"])),
                    "task_completion": str(int(item["task_completion"])),
                    "genre_quality": str(int(item["genre_quality"])),
                    "editing_cost": str(int(item["editing_cost"])),
                    "rag_use_quality": str(int(item["rag_use_quality"])),
                    "ai_taste_control": str(int(item["ai_taste_control"])),
                    "safety_copyright": str(int(item["safety_copyright"])),
                    "usable_bucket": item["usable_bucket"],
                    "preference_group": item["preference_group"],
                    "comments": item.get("comments", ""),
                    "scored_at": scored_at,
                }
            )
        write_csv(scores_path, score_rows, SCORE_FIELDS)
        time.sleep(float(config["sleep"]))

    print("done")


if __name__ == "__main__":
    main()
