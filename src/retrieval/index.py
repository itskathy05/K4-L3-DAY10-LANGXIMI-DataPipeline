from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any, Literal

import chromadb
import pandas as pd

from core.config import Settings
from core.utils import read_json, safe_slug, write_json
from retrieval.embeddings import MiniLMEmbeddings


SearchStrategy = Literal["dense", "hybrid"]

_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "published",
    "authors_joined",
    "categories_joined",
    "summary",
    "abs_url",
    "pdf_url",
    "text_for_embedding",
}
_RRF_K = 60


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any]


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _terms(text: str) -> list[str]:
    """Return word unigrams and bigrams for the small English paper corpus."""
    tokens = re.findall(r"\b\w+\b", text.casefold())
    return tokens + [f"{left}::{right}" for left, right in zip(tokens, tokens[1:], strict=False)]


class LocalEmbeddingIndex:
    def __init__(
        self,
        settings: Settings,
        collection_name: str,
        documents: list[dict[str, Any]],
        persist_path: Path,
    ):
        if not documents:
            raise ValueError("Cannot load an index without documents.")

        self.settings = settings
        self.collection_name = collection_name
        self.documents = documents
        self.persist_path = persist_path
        self.embedding_backend = "chroma"
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(persist_path))
        self.collection = self.client.get_collection(name=collection_name)
        collection_count = self.collection.count()
        if collection_count != len(documents):
            raise RuntimeError(
                f"Collection {collection_name!r} contains {collection_count} records "
                f"but its manifest contains {len(documents)} documents. Rebuild the index."
            )

        self.documents_by_record_id = {document["record_id"]: document for document in documents}
        self.documents_by_paper_id = {document["paper_id"].casefold(): document for document in documents}
        self.documents_by_title = {document["title"].casefold(): document for document in documents}
        self._lexical_vectors, self._lexical_norms, self._idf = self._build_lexical_index(documents)

    @staticmethod
    def _build_documents(df: pd.DataFrame) -> list[dict[str, Any]]:
        missing = sorted(_REQUIRED_COLUMNS - set(df.columns))
        if missing:
            raise ValueError(f"Missing required retrieval columns: {', '.join(missing)}")
        if df.empty:
            raise ValueError("Cannot build an index from an empty dataframe.")

        occurrences: Counter[str] = Counter()
        documents: list[dict[str, Any]] = []
        for row in df.to_dict(orient="records"):
            paper_id = _as_text(row["paper_id"])
            title = _as_text(row["title"])
            content = _as_text(row["text_for_embedding"])
            if not paper_id or not title or not content:
                raise ValueError("paper_id, title, and text_for_embedding must not be blank.")

            occurrence = occurrences[paper_id.casefold()]
            occurrences[paper_id.casefold()] += 1
            metadata = {
                "paper_id": paper_id,
                "title": title,
                "published": _as_text(row["published"]),
                "authors_joined": _as_text(row["authors_joined"]),
                "categories_joined": _as_text(row["categories_joined"]),
                "summary": _as_text(row["summary"]),
                "abs_url": _as_text(row["abs_url"]),
                "pdf_url": _as_text(row["pdf_url"]),
            }
            documents.append(
                {
                    "record_id": f"{paper_id}::{occurrence}",
                    "paper_id": paper_id,
                    "title": title,
                    "content": content,
                    "metadata": metadata,
                }
            )
        return documents

    @staticmethod
    def _build_lexical_index(
        documents: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, float]], dict[str, float], dict[str, float]]:
        counters: dict[str, Counter[str]] = {}
        document_frequency: Counter[str] = Counter()
        for document in documents:
            counts = Counter(_terms(document["content"]))
            title_counts = Counter(_terms(document["title"]))
            for term, count in title_counts.items():
                counts[term] += 2 * count
            counters[document["record_id"]] = counts
            document_frequency.update(counts.keys())

        count = len(documents)
        idf = {term: math.log((1 + count) / (1 + frequency)) + 1 for term, frequency in document_frequency.items()}
        vectors: dict[str, dict[str, float]] = {}
        norms: dict[str, float] = {}
        for record_id, counts in counters.items():
            vector = {
                term: (1 + math.log(frequency)) * idf[term]
                for term, frequency in counts.items()
            }
            vectors[record_id] = vector
            norms[record_id] = math.sqrt(sum(weight * weight for weight in vector.values()))
        return vectors, norms, idf

    @staticmethod
    def _derive_collection_name(settings: Settings, embeddings_output_path: Path | None) -> str:
        if embeddings_output_path is None:
            return settings.baseline_collection_name

        name_map = {
            settings.paths.embeddings_json.resolve(): settings.baseline_collection_name,
            settings.paths.corrupted_embeddings_json.resolve(): settings.corrupted_collection_name,
            settings.paths.repaired_embeddings_json.resolve(): settings.repaired_collection_name,
        }
        resolved_path = embeddings_output_path.resolve()
        if resolved_path in name_map:
            return name_map[resolved_path]
        return safe_slug(embeddings_output_path.stem)

    @classmethod
    def build(
        cls,
        df: pd.DataFrame,
        settings: Settings,
        embeddings_output_path: Path | None = None,
    ) -> "LocalEmbeddingIndex":
        collection_name = cls._derive_collection_name(settings, embeddings_output_path)
        documents = cls._build_documents(df)
        persist_path = settings.paths.chroma_dir
        persist_path.mkdir(parents=True, exist_ok=True)

        embedding_model = MiniLMEmbeddings(settings.embedding_model)
        embeddings = embedding_model.embed_documents([document["content"] for document in documents])
        client = chromadb.PersistentClient(path=str(persist_path))
        existing_names = {
            collection if isinstance(collection, str) else collection.name
            for collection in client.list_collections()
        }
        if collection_name in existing_names:
            client.delete_collection(name=collection_name)
        collection = client.create_collection(
            name=collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
        collection.add(
            ids=[document["record_id"] for document in documents],
            embeddings=embeddings,
            documents=[document["content"] for document in documents],
            metadatas=[document["metadata"] for document in documents],
        )

        try:
            portable_persist_path = persist_path.relative_to(settings.paths.project_dir).as_posix()
        except ValueError:
            portable_persist_path = str(persist_path)
        manifest_path = embeddings_output_path or settings.paths.embeddings_json
        write_json(
            manifest_path,
            {
                "backend": "chroma",
                "embedding_model": settings.embedding_model,
                "persist_path": portable_persist_path,
                "collection_name": collection_name,
                "document_count": len(documents),
                "documents": documents,
            },
        )
        return cls(
            settings=settings,
            collection_name=collection_name,
            documents=documents,
            persist_path=persist_path,
        )

    @classmethod
    def load(cls, settings: Settings, embeddings_path: Path | None = None) -> "LocalEmbeddingIndex":
        payload = read_json(embeddings_path or settings.paths.embeddings_json)
        required_keys = {"embedding_model", "persist_path", "collection_name", "documents"}
        missing = sorted(required_keys - set(payload))
        if missing:
            raise ValueError(f"Invalid embedding manifest; missing: {', '.join(missing)}")
        if payload["embedding_model"] != settings.embedding_model:
            raise ValueError(
                "Embedding manifest model does not match the configured query model. Rebuild the index."
            )
        persist_path = Path(payload["persist_path"])
        if not persist_path.is_absolute():
            persist_path = settings.paths.project_dir / persist_path
        return cls(
            settings=settings,
            collection_name=payload["collection_name"],
            documents=payload["documents"],
            persist_path=persist_path,
        )

    def _validate_search(self, query: str, top_k: int | None) -> int:
        if not query or not query.strip():
            raise ValueError("Search query must not be empty.")
        limit = self.settings.top_k if top_k is None else top_k
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("top_k must be a positive integer.")
        return min(limit, len(self.documents))

    def _dense_search(self, query: str, limit: int) -> list[tuple[str, SearchResult]]:
        query_embedding = self.embedding_model.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        contents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        scored: list[tuple[str, SearchResult]] = []
        for record_id, content, metadata, distance in zip(ids, contents, metadatas, distances, strict=False):
            if not record_id or not metadata or not content or distance is None:
                continue
            score = min(1.0, max(0.0, 1.0 - float(distance)))
            scored.append(
                (
                    str(record_id),
                    SearchResult(
                        paper_id=str(metadata["paper_id"]),
                        title=str(metadata["title"]),
                        score=score,
                        content=str(content),
                        metadata=dict(metadata),
                    ),
                )
            )
        return scored

    def _lexical_search(self, query: str, limit: int) -> list[tuple[str, float]]:
        counts = Counter(_terms(query))
        query_vector = {
            term: (1 + math.log(frequency)) * self._idf.get(term, 0.0)
            for term, frequency in counts.items()
            if term in self._idf
        }
        query_norm = math.sqrt(sum(weight * weight for weight in query_vector.values()))
        if query_norm == 0:
            return []

        scored: list[tuple[str, float]] = []
        for record_id, document_vector in self._lexical_vectors.items():
            denominator = query_norm * self._lexical_norms[record_id]
            if denominator == 0:
                continue
            dot_product = sum(query_vector.get(term, 0.0) * weight for term, weight in document_vector.items())
            score = dot_product / denominator
            if score > 0:
                scored.append((record_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:limit]

    def _result_from_document(self, record_id: str, score: float) -> SearchResult:
        document = self.documents_by_record_id[record_id]
        return SearchResult(
            paper_id=document["paper_id"],
            title=document["title"],
            score=min(1.0, max(0.0, score)),
            content=document["content"],
            metadata=dict(document["metadata"]),
        )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        strategy: SearchStrategy = "dense",
    ) -> list[SearchResult]:
        """Search with dense cosine or title-weighted TF-IDF plus dense RRF.

        ``score`` is cosine similarity for dense search and normalized RRF score
        for hybrid search. Both are bounded to ``[0, 1]``.
        """
        limit = self._validate_search(query, top_k)
        if strategy not in {"dense", "hybrid"}:
            raise ValueError("strategy must be either 'dense' or 'hybrid'.")
        if strategy == "dense":
            return [result for _, result in self._dense_search(query, limit)]

        candidate_limit = min(len(self.documents), max(10, limit * 3))
        dense = self._dense_search(query, candidate_limit)
        lexical = self._lexical_search(query, candidate_limit)
        if not lexical:
            return [result for _, result in dense[:limit]]

        rrf_scores: Counter[str] = Counter()
        dense_scores: dict[str, float] = {}
        for rank, (record_id, result) in enumerate(dense, start=1):
            rrf_scores[record_id] += 1 / (_RRF_K + rank)
            dense_scores[record_id] = result.score
        for rank, (record_id, _) in enumerate(lexical, start=1):
            rrf_scores[record_id] += 1 / (_RRF_K + rank)

        maximum_rrf = 2 / (_RRF_K + 1)
        ranked_ids = sorted(
            rrf_scores,
            key=lambda record_id: (-rrf_scores[record_id], -dense_scores.get(record_id, 0.0), record_id),
        )
        return [
            self._result_from_document(record_id, rrf_scores[record_id] / maximum_rrf)
            for record_id in ranked_ids[:limit]
        ]

    def lookup(self, value: str) -> dict[str, Any] | None:
        needle = value.strip().casefold()
        if needle in self.documents_by_paper_id:
            return self.documents_by_paper_id[needle]
        if needle in self.documents_by_title:
            return self.documents_by_title[needle]
        return None
