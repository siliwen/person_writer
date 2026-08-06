from dataclasses import dataclass
from enum import StrEnum


class GenerationMode(StrEnum):
    STYLE_PROMPT_ONLY = "style_prompt_only"
    STYLE_PROFILE_RAG = "style_profile_rag"


RAG_EXPERIMENT_GENRES = {"文章", "散文"}
RAG_DISABLED_GENRES = {"诗歌", "小说章节", "小说"}


@dataclass(frozen=True)
class GenerationPolicy:
    mode: GenerationMode
    rag_enabled: bool
    reason: str


def resolve_generation_policy(
    *,
    genre: str,
    requested_mode: GenerationMode | str | None = None,
    rag_experiment_enabled: bool = True,
) -> GenerationPolicy:
    """Resolve the effective generation mode from product policy.

    MVP default is Style Profile prompt-only. RAG is not part of the default
    path; it can only be enabled as an experiment for article/prose genres.
    Poetry and fiction stay prompt-only because the evaluation showed RAG
    destabilizes rhythm, restraint, and narrative flow.
    """

    requested = GenerationMode(requested_mode or GenerationMode.STYLE_PROMPT_ONLY)
    normalized_genre = genre.strip()

    if requested == GenerationMode.STYLE_PROMPT_ONLY:
        return GenerationPolicy(
            mode=GenerationMode.STYLE_PROMPT_ONLY,
            rag_enabled=False,
            reason="MVP default path uses editable Style Profile without RAG.",
        )

    if normalized_genre in RAG_DISABLED_GENRES:
        return GenerationPolicy(
            mode=GenerationMode.STYLE_PROMPT_ONLY,
            rag_enabled=False,
            reason=f"RAG disabled for poetry/fiction genre: {normalized_genre}.",
        )

    if normalized_genre not in RAG_EXPERIMENT_GENRES or not rag_experiment_enabled:
        return GenerationPolicy(
            mode=GenerationMode.STYLE_PROMPT_ONLY,
            rag_enabled=False,
            reason=f"RAG experiment is not enabled for genre: {normalized_genre}.",
        )

    return GenerationPolicy(
        mode=GenerationMode.STYLE_PROFILE_RAG,
        rag_enabled=True,
        reason="RAG experiment enabled for article/prose genre.",
    )

