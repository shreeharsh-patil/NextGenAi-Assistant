"""
memory/rag_memory.py — Semantic (RAG) memory for ULTRON.

Stores short text snippets (user utterances, assistant responses, notes,
file summaries) together with vector embeddings, and answers similarity
queries so ULTRON can recall *related* context instead of only the exact
structured facts kept in ``memory_manager.long_term.json``.

Embedding backend, resolved lazily on first use:

  1. ``fastembed`` — local ONNX models, no PyTorch required (preferred).
  2. Pure-Python fallback — hashing TF vectors.  Always works offline and
     is fully deterministic (used by the test suite).

Set the environment variable ``ULTRON_RAG_FALLBACK=1`` to force the
fallback backend.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from utils.logger import get_logger

logger = get_logger("ultron.rag")

_MAX_DOCS     = 2000     # FIFO eviction ceiling
_FALLBACK_DIM = 1024
_MIN_SCORE    = 0.10     # below this, search() returns nothing

_EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


RAG_STORE_PATH = get_base_dir() / "memory" / "rag_store.json"

_lock        = threading.RLock()
_documents   : list[dict]          = []   # [{id, text, source, ts, meta}]
_embeddings  : list[np.ndarray]    = []
_backend     : "object | None"     = None
_loaded      = False
_FORCE_FALLBACK = os.environ.get("ULTRON_RAG_FALLBACK") == "1"


# ── tokenization / fallback embedder ──────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    words: list[str] = []
    current = []
    for ch in text.lower():
        if ch.isalnum():
            current.append(ch)
        else:
            if current:
                words.append("".join(current))
                current = []
    if current:
        words.append("".join(current))
    return words


class _FallbackBackend:
    """Deterministic hashed-TF embedder — no external dependencies."""

    dim = _FALLBACK_DIM

    def embed_many(self, texts: list[str]) -> list[np.ndarray]:
        vecs: list[np.ndarray] = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            for token in _tokenize(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8)
                h = int.from_bytes(digest.digest(), "little")
                idx = h % self.dim
                sign = 1.0 if (h >> 8) & 1 else -1.0
                vec[idx] += sign
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            vecs.append(vec)
        return vecs


class _FastEmbedBackend:
    """wraps fastembed.TextEmbedding (local ONNX)."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding  # type: ignore
        self._model = TextEmbedding(_EMBED_MODEL)

    def embed_many(self, texts: list[str]) -> list[np.ndarray]:
        return [np.asarray(v, dtype=np.float32).flatten()
                for v in self._model.embed(texts)]


def _resolve_backend():
    """Build the embedding backend once (thread-safe)."""
    global _backend
    if _backend is not None:
        return _backend
    with _lock:
        if _backend is not None:
            return _backend
        if not _FORCE_FALLBACK:
            try:
                _backend = _FastEmbedBackend()
                logger.info("RAG: fastembed backend ready (model=%s)", _EMBED_MODEL)
                return _backend
            except Exception as e:
                logger.warning("RAG: fastembed unavailable (%s) — using fallback embedder", e)
        _backend = _FallbackBackend()
        logger.info("RAG: fallback embedder ready")
        return _backend


def _embed(texts: list[str]) -> list[np.ndarray]:
    if not texts:
        return []
    backend = _resolve_backend()
    try:
        return backend.embed_many(texts)
    except Exception as e:
        logger.error("RAG: embed failed (%s) — falling back", e)
        return _FallbackBackend().embed_many(texts)


# ── persistence ───────────────────────────────────────────────────────────────

def _load() -> None:
    global _documents, _embeddings, _loaded
    with _lock:
        if _loaded:
            return
        try:
            data = json.loads(RAG_STORE_PATH.read_text(encoding="utf-8"))
            docs  = data.get("documents", [])
            emb   = data.get("embeddings", [])
            _documents  = [d for d in docs if isinstance(d, dict) and d.get("text")]
            _embeddings = [np.asarray(v, dtype=np.float32).flatten()
                           for v in emb if isinstance(v, list)]
            if len(_documents) != len(_embeddings):
                # stale / truncated store — rebuild embeddings from text
                logger.warning("RAG: store size mismatch (%d docs / %d vecs) — re-embedding",
                               len(_documents), len(_embeddings))
                _embeddings = _embed([d["text"] for d in _documents])
        except FileNotFoundError:
            _documents, _embeddings = [], []
        except Exception as e:
            logger.error("RAG: load failed (%s) — starting empty", e)
            _documents, _embeddings = [], []
        _loaded = True


def _save() -> None:
    with _lock:
        RAG_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = RAG_STORE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "version": 1,
            "documents": _documents,
            "embeddings": [v.tolist() for v in _embeddings],
        }, ensure_ascii=False), encoding="utf-8")
        tmp.replace(RAG_STORE_PATH)


def reset() -> None:
    """Clear in-memory state and reload from disk (used by tests)."""
    global _documents, _embeddings, _loaded
    with _lock:
        _documents, _embeddings = [], []
        _loaded = False
        _load()


# ── public API ────────────────────────────────────────────────────────────────

def _content_key(text: str, source: str) -> str:
    return hashlib.sha1(f"{source}\x1f{text}".encode("utf-8")).hexdigest()


def add(text: str, source: str = "note", meta: dict | None = None) -> bool:
    """Embed and store one snippet. Returns True if a new entry was stored."""
    text = (text or "").strip()
    if len(text) < 2:
        return False
    with _lock:
        _load()
        key = _content_key(text, source)
        for doc in _documents:
            if doc.get("id") == key:
                return False   # duplicate — keep original
        vec = _embed([text])[0]
        _documents.append({
            "id":     key,
            "text":   text,
            "source": source,
            "ts":     time.time(),
            "meta":   meta or {},
        })
        _embeddings.append(vec)
        # FIFO eviction
        while len(_documents) > _MAX_DOCS:
            _documents.pop(0)
            _embeddings.pop(0)
        _save()
        return True


def search(query: str, k: int = 5, min_score: float = _MIN_SCORE) -> list[dict]:
    """Return top-k snippets ranked by cosine similarity to ``query``."""
    query = (query or "").strip()
    if not query:
        return []
    with _lock:
        _load()
        if not _documents:
            return []
        q_vec = _embed([query])[0]
        scores = [float(np.dot(q_vec, v)) for v in _embeddings]
        ranked = sorted(zip(scores, _documents), key=lambda t: t[0], reverse=True)
        results = []
        for score, doc in ranked:
            if score < min_score:
                break
            results.append({**doc, "score": round(score, 4)})
            if len(results) >= k:
                break
        return results


def recall(query: str, k: int = 5, min_score: float = _MIN_SCORE) -> str:
    """Formatted snippet block for injecting into the LLM prompt."""
    results = search(query, k=k, min_score=min_score)
    if not results:
        return ""
    lines = ["[RECALLED CONTEXT — use naturally, do not read this header aloud]"]
    for r in results:
        lines.append(f"- ({r['source']}) {r['text']}")
    return "\n".join(lines)


def count() -> int:
    with _lock:
        _load()
        return len(_documents)


def clear() -> None:
    """Delete the whole RAG store."""
    global _documents, _embeddings, _loaded
    with _lock:
        _documents, _embeddings = [], []
        _loaded = True
        try:
            RAG_STORE_PATH.unlink(missing_ok=True)
        except Exception:
            pass


def store_context(text: str, source: str = "user") -> bool:
    """Convenience wrapper for auto-storing conversation turns."""
    return add(text, source=source)


def semantic_search(query: str, k: int = 5) -> list[dict]:
    """Alias for :func:`search`."""
    return search(query, k=k)
