from __future__ import annotations

from dataclasses import dataclass
import re

from core.config import Settings
from core.utils import first_sentence
from retrieval.index import LocalEmbeddingIndex, SearchResult, SearchStrategy


_UNKNOWN_ANSWER = "I don't know from the indexed corpus."
_QUOTED_REFERENCE = re.compile(r"['\"“‘]([^'\"”’]+)['\"”’]")
_DOI_REFERENCE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_contexts: list[str]
    retrieved_titles: list[str]


def _extract_answer(question: str, top_result: SearchResult) -> str:
    lowered = question.casefold()
    metadata = top_result.metadata
    if "author" in lowered:
        answer = metadata.get("authors_joined", "")
    elif "when" in lowered or "date" in lowered or "published" in lowered:
        answer = metadata.get("published", "")
    elif any(term in lowered for term in ("category", "categories", "field", "subject")):
        answer = metadata.get("categories_joined", "")
    else:
        answer = first_sentence(str(metadata.get("summary", "")))
    return str(answer).strip() or _UNKNOWN_ANSWER


def _extract_exact_reference(question: str) -> str | None:
    quoted = _QUOTED_REFERENCE.search(question)
    if quoted:
        return quoted.group(1).strip()
    doi = _DOI_REFERENCE.search(question)
    if doi:
        return doi.group(0).rstrip(".,;)")
    return None


def answer_question(
    question: str,
    settings: Settings,
    index: LocalEmbeddingIndex,
    top_k: int | None = None,
    strategy: SearchStrategy = "dense",
) -> AnswerResult:
    if not question or not question.strip():
        raise ValueError("Question must not be empty.")

    exact_reference = _extract_exact_reference(question)
    exact = index.lookup(exact_reference) if exact_reference else None
    if exact_reference and not exact:
        return AnswerResult(
            question=question,
            answer=_UNKNOWN_ANSWER,
            retrieved_doc_ids=[],
            retrieved_contexts=[],
            retrieved_titles=[],
        )

    retrieved = index.search(question, top_k=top_k, strategy=strategy)
    if exact:
        exact_result = SearchResult(
            paper_id=exact["paper_id"],
            title=exact["title"],
            score=1.0,
            content=exact["content"],
            metadata=exact["metadata"],
        )
        deduped = [exact_result] + [item for item in retrieved if item.paper_id != exact_result.paper_id]
        retrieved = deduped[: (top_k or settings.top_k)]
    if not retrieved:
        answer = _UNKNOWN_ANSWER
    else:
        answer = _extract_answer(question, retrieved[0])
    return AnswerResult(
        question=question,
        answer=answer,
        retrieved_doc_ids=[item.paper_id for item in retrieved],
        retrieved_contexts=[item.content for item in retrieved],
        retrieved_titles=[item.title for item in retrieved],
    )
