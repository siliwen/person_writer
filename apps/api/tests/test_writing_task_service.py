import unittest

from app.core.generation_policy import GenerationMode
from app.core.prompt_composer import WritingTaskInput
from app.core.task_service import InMemoryWritingTaskService


STYLE_PROFILE = {
    "style_profile_id": "style_demo_v1",
    "writer_id": "writer_demo",
    "voice": {"tone": ["克制"]},
}


class WritingTaskServiceTests(unittest.TestCase):
    def test_create_task_records_effective_prompt_only_mode_for_poetry(self) -> None:
        service = InMemoryWritingTaskService()
        task = WritingTaskInput(
            genre="诗歌",
            task_type="新写",
            title="远方电话",
            brief="写一首关于远方电话的短诗",
            target_length="12行",
            target_reader="诗歌读者",
            must_include="停顿",
            must_avoid="剧情化；意象堆叠",
            eval_focus="节奏；留白",
        )

        created = service.create_task(
            writer_id="writer_demo",
            task=task,
            style_profile=STYLE_PROFILE,
            requested_mode=GenerationMode.STYLE_PROFILE_RAG,
            rag_snippets=["诗歌默认不能使用这段 RAG 证据。"],
        )

        self.assertEqual(created.status, "pending")
        self.assertEqual(created.effective_mode, GenerationMode.STYLE_PROMPT_ONLY)
        self.assertFalse(created.rag_enabled)
        self.assertEqual(created.prompt_version, "style_prompt_only_v1")
        self.assertEqual(service.get_task(created.task_id), created)


if __name__ == "__main__":
    unittest.main()

