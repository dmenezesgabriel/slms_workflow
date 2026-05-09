"""Local RAG system with hybrid search (BM25 + semantic embeddings) + reranking.

All components run locally without external services:
- Embeddings: BGE (BAAI General Embeddings) - small, efficient
- Vector store: Chroma (in-memory)
- Reranking: BGE Reranker
- Keyword search: BM25
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, cast

import numpy as np

if TYPE_CHECKING:
    import chromadb
    from sentence_transformers import CrossEncoder, SentenceTransformer

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-base"


@dataclass
class Document:
    """Represents a document in the RAG store."""

    id: str
    content: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Represents a search result with score."""

    document: Document
    score: float
    rank: int


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed(self, texts: list[str]) -> list[np.ndarray]: ...


class SemanticSearcher(Protocol):
    """Protocol for semantic search."""

    def search(self, query: str, top_k: int) -> list[SearchResult]: ...
    def add_documents(self, documents: list[Document]) -> None: ...


class KeywordSearcher(Protocol):
    """Protocol for keyword search."""

    def search(self, query: str, top_k: int) -> list[SearchResult]: ...
    def add_documents(self, documents: list[Document]) -> None: ...


class Reranker(Protocol):
    """Protocol for reranking."""

    def rerank(self, query: str, documents: list[Document], top_k: int) -> list[SearchResult]: ...


class LocalEmbeddingProvider:
    """Local embeddings using sentence-transformers with BGE."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        device: str = "cpu",
        normalize: bool = True,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._normalize = normalize
        self._model: SentenceTransformer | None = None
        self._embedding_dim: int | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name, device=self._device)
            self._embedding_dim = self._model.get_sentence_embedding_dimension()
        return cast(SentenceTransformer, self._model)

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is None:
            _ = self.model
        assert self._embedding_dim is not None
        return self._embedding_dim

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [emb for emb in embeddings]


class ChromaVectorStore:
    """In-memory Chroma vector store for semantic search."""

    def __init__(self, embedding_provider: EmbeddingProvider, decay_rate: float = 0.0) -> None:
        self._embedding_provider = embedding_provider
        self._decay_rate = decay_rate
        self._chroma: Any = None
        self._collection: Any = None
        self._documents: dict[str, Document] = {}

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._chroma = chromadb.PersistentClient(
                path="/tmp/chroma_rag",
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            self._collection = self._chroma.get_or_create_collection(
                name="rag_documents",
                metadata={"hnsw:space": "cosine"},
            )
        return cast(chromadb.Collection, self._collection)

    def add_documents(self, documents: list[Document]) -> None:
        if not documents:
            return

        embeddings = self._embedding_provider.embed([doc.content for doc in documents])
        ids = [doc.id for doc in documents]
        metadatas = [
            {"source": doc.source, "added_at": time.time(), **doc.metadata} for doc in documents
        ]
        documents_text = [doc.content for doc in documents]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,  # type: ignore[arg-type]
            documents=documents_text,
        )
        for doc in documents:
            self._documents[doc.id] = doc

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        query_embedding = self._embedding_provider.embed([query])[0]

        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            include=["distances", "metadatas"],
        )

        now = time.time()
        search_results: list[SearchResult] = []
        result_ids = results["ids"]
        result_distances = results["distances"]
        result_metadatas = results["metadatas"]
        if not result_ids or not result_distances or not result_metadatas:
            return search_results
        for rank, (doc_id, distance, metadata) in enumerate(
            zip(result_ids[0], result_distances[0], result_metadatas[0]), start=1
        ):
            if doc_id in self._documents:
                score = 1.0 - float(distance)
                if self._decay_rate > 0 and metadata:
                    added_at = metadata.get("added_at")
                    if added_at is not None:
                        elapsed = now - float(added_at)  # type: ignore[arg-type]
                        time_decay = self._decay_rate * elapsed
                        score *= math.exp(-time_decay)
                search_results.append(
                    SearchResult(document=self._documents[doc_id], score=score, rank=rank)
                )
        return search_results


class BM25KeywordSearch:
    """BM25 keyword search implementation."""

    def __init__(self) -> None:
        self._ranker = None
        self._indexed_docs: dict[str, Document] = {}
        self._doc_ids: list[str] = []

    def add_documents(self, documents: list[Document]) -> None:
        from rank_bm25 import BM25Okapi

        for doc in documents:
            self._indexed_docs[doc.id] = doc

        self._doc_ids = list(self._indexed_docs.keys())
        tokenized_corpus = [
            self._tokenize(self._indexed_docs[doc_id].content) for doc_id in self._doc_ids
        ]
        self._ranker = BM25Okapi(tokenized_corpus)

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return text.split()

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        if self._ranker is None:
            return []

        tokenized_query = self._tokenize(query)
        scores = self._ranker.get_scores(tokenized_query)

        doc_scores = list(zip(self._doc_ids, scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        search_results = []
        for rank, (doc_id, score) in enumerate(doc_scores[:top_k], start=1):
            search_results.append(
                SearchResult(
                    document=self._indexed_docs[doc_id],
                    score=score,
                    rank=rank,
                )
            )
        return search_results


class BGEReranker:
    """Local BGE reranker for improved result ordering."""

    def __init__(self, model_name: str = DEFAULT_RERANK_MODEL, device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name, max_length=512, device=self._device)
        return cast(CrossEncoder, self._model)

    def rerank(self, query: str, documents: list[Document], top_k: int) -> list[SearchResult]:
        if not documents:
            return []

        pairs = [(query, doc.content) for doc in documents]
        scores = self.model.predict(pairs)  # type: ignore[arg-type]

        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return [
            SearchResult(document=doc, score=score, rank=rank + 1)
            for rank, (doc, score) in enumerate(scored_docs[:top_k])
        ]


class HybridRAG:
    """Hybrid RAG combining BM25 + semantic search + reranking."""

    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        rerank_model: str = DEFAULT_RERANK_MODEL,
        device: str = "cpu",
        semantic_weight: float = 0.5,
        rerank: bool = True,
        dedup_threshold: float = 0.85,
        decay_rate: float = 1e-5,
    ) -> None:
        self._embedding_provider = LocalEmbeddingProvider(model_name=embedding_model, device=device)
        self._semantic_searcher: SemanticSearcher | None = None
        self._keyword_searcher: KeywordSearcher | None = None
        self._reranker: Reranker | None = (
            None if not rerank else BGEReranker(model_name=rerank_model, device=device)
        )
        self._semantic_weight = semantic_weight
        self._dedup_threshold = dedup_threshold
        self._decay_rate = decay_rate
        self._doc_count = 0
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        self._semantic_searcher = ChromaVectorStore(
            self._embedding_provider, decay_rate=self._decay_rate
        )
        self._keyword_searcher = BM25KeywordSearch()
        self._initialized = True

    def _is_near_duplicate(self, content: str) -> bool:
        if not self._initialized or self._dedup_threshold >= 1.0 or self._doc_count == 0:
            return False
        assert self._semantic_searcher is not None
        try:
            results = self._semantic_searcher.search(content, top_k=1)
            return bool(results) and results[0].score >= self._dedup_threshold
        except Exception:
            return False

    def add_documents(self, documents: list[Document]) -> None:
        self._ensure_initialized()
        assert self._semantic_searcher is not None
        assert self._keyword_searcher is not None
        unique = [doc for doc in documents if not self._is_near_duplicate(doc.content)]
        if not unique:
            return
        self._semantic_searcher.add_documents(unique)
        self._keyword_searcher.add_documents(unique)
        self._doc_count += len(unique)

    def add_text(
        self,
        contents: list[str],
        sources: list[str],
        ids: list[str] | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        if ids is None:
            ids = [self._generate_id(content) for content in contents]

        documents = [
            Document(
                id=doc_id,
                content=content,
                source=source,
                metadata=meta or {},
            )
            for doc_id, content, source, meta in zip(
                ids, contents, sources, metadata or [{}] * len(contents)
            )
        ]
        self.add_documents(documents)

    def _generate_id(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def search(
        self, query: str, top_k: int = 5, rerank: bool = True, min_score: float = 0.0
    ) -> list[SearchResult]:
        self._ensure_initialized()
        assert self._semantic_searcher is not None
        assert self._keyword_searcher is not None

        semantic_results = self._semantic_searcher.search(query, top_k=top_k * 2)
        keyword_results = self._keyword_searcher.search(query, top_k=top_k * 2)

        merged = self._merge_results(semantic_results, keyword_results)

        if rerank and self._reranker and len(merged) > 0:
            unique_docs = list({r.document.id: r.document for r in merged}.values())
            results = self._reranker.rerank(query, unique_docs, top_k)
        else:
            results = merged[:top_k]

        if min_score > 0.0:
            results = [r for r in results if r.score >= min_score]
        return results

    def _merge_results(
        self, semantic: list[SearchResult], keyword: list[SearchResult], top_k: int = 10
    ) -> list[SearchResult]:
        doc_scores: dict[str, tuple[Document, float]] = {}

        for result in semantic:
            existing = doc_scores.get(result.document.id)
            if existing is None:
                doc_scores[result.document.id] = (
                    result.document,
                    result.score * self._semantic_weight,
                )
            else:
                doc_scores[result.document.id] = (
                    existing[0],
                    existing[1] + result.score * self._semantic_weight,
                )

        kw_weight = 1.0 - self._semantic_weight
        for result in keyword:
            existing = doc_scores.get(result.document.id)
            if existing is None:
                doc_scores[result.document.id] = (result.document, result.score * kw_weight)
            else:
                doc_scores[result.document.id] = (
                    existing[0],
                    existing[1] + result.score * kw_weight,
                )

        sorted_results = sorted(doc_scores.values(), key=lambda x: x[1], reverse=True)
        return [
            SearchResult(document=doc, score=score, rank=rank + 1)
            for rank, (doc, score) in enumerate(sorted_results[:top_k])
        ]

    def clear(self) -> None:
        self._initialized = False
        self._semantic_searcher = None
        self._keyword_searcher = None
        self._doc_count = 0


class SimpleInMemoryRAG:
    """Simplified in-memory RAG without embeddings for fast prototyping."""

    def __init__(self) -> None:
        self._documents: list[Document] = []

    def add_text(self, contents: list[str], sources: list[str]) -> None:
        for content, source in zip(contents, sources):
            doc_id = hashlib.md5(content.encode()).hexdigest()[:16]
            self._documents.append(Document(id=doc_id, content=content, source=source))

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query_lower = query.lower()
        scored = []

        for doc in self._documents:
            query_terms = set(query_lower.split())
            doc_terms = set(doc.content.lower().split())
            overlap = len(query_terms & doc_terms)
            score = overlap / max(len(query_terms), 1)
            scored.append((doc, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            SearchResult(document=doc, score=score, rank=rank + 1)
            for rank, (doc, score) in enumerate(scored[:top_k])
        ]

    def clear(self) -> None:
        self._documents.clear()


_global_rag: HybridRAG | None = None


def get_rag() -> HybridRAG:
    global _global_rag
    if _global_rag is None:
        _global_rag = HybridRAG(
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            rerank_model=DEFAULT_RERANK_MODEL,
            device="cpu",
            semantic_weight=0.5,
            rerank=True,
            dedup_threshold=0.85,
            decay_rate=1e-5,
        )
    return _global_rag


def reset_rag() -> None:
    global _global_rag
    if _global_rag:
        _global_rag.clear()
    _global_rag = None


def store_retrieval_results(contents: list[str], sources: list[str]) -> None:
    rag = get_rag()
    rag.add_text(contents=contents, sources=sources)


def query_rag(query: str, top_k: int = 5) -> list[SearchResult]:
    rag = get_rag()
    return rag.search(query, top_k=top_k)


def rag_context_from_results(results: list[SearchResult]) -> str:
    if not results:
        return ""

    contexts = []
    for r in results:
        source_marker = f"[Source: {r.document.source}]" if r.document.source else ""
        contexts.append(f"{r.document.content}\n{source_marker}")

    return "\n\n---\n\n".join(contexts)
