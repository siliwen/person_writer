from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env.local"


@dataclass(frozen=True)
class ModelResult:
    content: str
    model_provider: str
    model_name: str
    input_token_count: int
    output_token_count: int


def _load_env_file(path: Path = DEFAULT_ENV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lstrip("\ufeff")] = value.strip().strip('"').strip("'")
    return values


class ModelGateway:
    def __init__(self) -> None:
        env_file = _load_env_file()
        self.mode = env_file.get("MODEL_GATEWAY_MODE") or os.getenv("MODEL_GATEWAY_MODE", "auto")
        self.api_key = env_file.get("DASHSCOPE_API_KEY") or env_file.get("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (
            env_file.get("BASE_URL")
            or os.getenv("BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ).rstrip("/")
        self.model_name = env_file.get("MODEL_NAME") or os.getenv("MODEL_NAME") or "qwen-plus"
        self.timeout = float(env_file.get("REQUEST_TIMEOUT_SECONDS") or os.getenv("REQUEST_TIMEOUT_SECONDS") or "120")

    def generate(self, *, messages: list[dict[str, str]], purpose: str, fallback: str) -> ModelResult:
        if self.mode != "mock" and self.api_key:
            try:
                return self._call_qwen(messages=messages)
            except Exception:
                if self.mode == "qwen":
                    raise
        return self._mock_result(fallback=fallback, purpose=purpose, messages=messages)

    def _call_qwen(self, *, messages: list[dict[str, str]]) -> ModelResult:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9,
        }
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + str(self.api_key),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Qwen API failed: HTTP {exc.code}") from exc

        usage = body.get("usage", {})
        content = body["choices"][0]["message"]["content"].strip()
        return ModelResult(
            content=content,
            model_provider="alibaba_bailian",
            model_name=self.model_name,
            input_token_count=int(usage.get("prompt_tokens") or 0),
            output_token_count=int(usage.get("completion_tokens") or 0),
        )

    @staticmethod
    def _mock_result(*, fallback: str, purpose: str, messages: list[dict[str, str]]) -> ModelResult:
        prompt_size = sum(len(item.get("content", "")) for item in messages)
        return ModelResult(
            content=fallback.strip(),
            model_provider="mock",
            model_name=f"mock-{purpose}",
            input_token_count=max(1, prompt_size // 2),
            output_token_count=max(1, len(fallback) // 2),
        )
