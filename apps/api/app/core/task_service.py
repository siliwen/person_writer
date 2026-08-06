from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.generation_policy import GenerationMode
from app.core.prompt_composer import WritingTaskInput, compose_prompt


@dataclass(frozen=True)
class WritingTask:
    task_id: str
    writer_id: str
    status: str
    effective_mode: GenerationMode
    rag_enabled: bool
    prompt_version: str
    system_prompt: str
    user_prompt: str
    created_at: str
    policy_reason: str


@dataclass
class InMemoryWritingTaskService:
    tasks: dict[str, WritingTask] = field(default_factory=dict)

    def create_task(
        self,
        *,
        writer_id: str,
        task: WritingTaskInput,
        style_profile: dict[str, Any],
        requested_mode: GenerationMode | str | None = None,
        rag_snippets: list[str] | None = None,
    ) -> WritingTask:
        prompt = compose_prompt(
            task=task,
            style_profile=style_profile,
            requested_mode=requested_mode,
            rag_snippets=rag_snippets,
        )
        task_id = f"task_{uuid4().hex[:12]}"
        created = WritingTask(
            task_id=task_id,
            writer_id=writer_id,
            status="pending",
            effective_mode=prompt.mode,
            rag_enabled=prompt.rag_enabled,
            prompt_version=prompt.prompt_version,
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            policy_reason=prompt.policy_reason,
        )
        self.tasks[task_id] = created
        return created

    def get_task(self, task_id: str) -> WritingTask | None:
        return self.tasks.get(task_id)

