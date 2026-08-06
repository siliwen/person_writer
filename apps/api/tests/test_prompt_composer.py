import unittest

from app.core.generation_policy import GenerationMode, resolve_generation_policy
from app.core.prompt_composer import WritingTaskInput, compose_prompt


STYLE_PROFILE = {
    "style_profile_id": "style_demo_v1",
    "writer_id": "writer_demo",
    "voice": {
        "tone": ["克制", "具体", "避免口号"],
        "narrative_distance": "近距离观察，不替作者解释过多",
    },
    "syntax": {
        "sentence_patterns": ["短句建立停顿", "长句承接观察"],
    },
    "imagery": {
        "preferred": ["门槛", "雨声", "旧物"],
        "avoid": ["空泛抒情", "意象堆叠"],
    },
}


class PromptComposerTests(unittest.TestCase):
    def test_poetry_defaults_to_style_prompt_only_even_when_rag_is_requested(self) -> None:
        policy = resolve_generation_policy(genre="诗歌", requested_mode=GenerationMode.STYLE_PROFILE_RAG)

        self.assertEqual(policy.mode, GenerationMode.STYLE_PROMPT_ONLY)
        self.assertFalse(policy.rag_enabled)
        self.assertIn("RAG disabled for poetry", policy.reason)

    def test_prompt_composer_uses_style_profile_as_primary_instruction(self) -> None:
        task = WritingTaskInput(
            genre="诗歌",
            task_type="新写",
            title="雨伞",
            brief="写一首关于门口雨伞的短诗",
            target_length="12-16行",
            target_reader="诗歌读者",
            must_include="门口；雨声",
            must_avoid="空泛抒情；意象堆叠",
            eval_focus="节奏；留白；收束",
        )

        prompt = compose_prompt(
            task=task,
            style_profile=STYLE_PROFILE,
            requested_mode=GenerationMode.STYLE_PROFILE_RAG,
            rag_snippets=["这段 RAG 证据不应进入诗歌默认 prompt。"],
        )

        self.assertEqual(prompt.mode, GenerationMode.STYLE_PROMPT_ONLY)
        self.assertFalse(prompt.rag_enabled)
        self.assertIn("Style Profile 是最高优先级", prompt.user_prompt)
        self.assertNotIn("RAG 证据", prompt.user_prompt)

    def test_article_can_use_rag_as_experimental_evidence(self) -> None:
        task = WritingTaskInput(
            genre="文章",
            task_type="新写",
            title="附近生活",
            brief="写一篇观点文：县城青年为什么重新重视附近生活",
            target_length="1200字",
            target_reader="普通读者",
            must_include="具体生活场景；清晰论点",
            must_avoid="空泛鸡汤；网络热梗",
            eval_focus="观点结构；开头方式；句式节奏",
        )

        prompt = compose_prompt(
            task=task,
            style_profile=STYLE_PROFILE,
            requested_mode=GenerationMode.STYLE_PROFILE_RAG,
            rag_snippets=["示例片段：从一个具体场景进入观点，但不要复制原句。"],
        )

        self.assertEqual(prompt.mode, GenerationMode.STYLE_PROFILE_RAG)
        self.assertTrue(prompt.rag_enabled)
        self.assertIn("RAG 实验增强", prompt.user_prompt)
        self.assertIn("不要复制原句、专名、真实作品名或连续意象组合", prompt.user_prompt)


if __name__ == "__main__":
    unittest.main()
