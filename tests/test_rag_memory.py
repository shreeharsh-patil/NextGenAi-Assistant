"""
Unit tests for memory/rag_memory.py — semantic recall.
Uses the deterministic pure-Python fallback embedder and a temp store file.
"""
import pytest

import memory.rag_memory as rag


@pytest.fixture()
def rag_store(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "RAG_STORE_PATH", tmp_path / "rag_store.json")
    monkeypatch.setattr(rag, "_FORCE_FALLBACK", True)
    rag._backend = None     # re-resolve backend as fallback
    rag.reset()
    yield rag
    rag._backend = None
    rag.reset()


def test_add_and_count(rag_store):
    assert rag_store.add("User prefers dark mode UI", source="user")
    assert rag_store.count() == 1


def test_add_deduplicates(rag_store):
    rag_store.add("I live in Istanbul", source="user")
    assert not rag_store.add("I live in Istanbul", source="user")
    assert rag_store.count() == 1


def test_short_text_rejected(rag_store):
    assert not rag_store.add("a", source="user")


def test_search_returns_sorted_relevant(rag_store):
    rag_store.add("I love playing chess on weekends", source="user")
    rag_store.add("Need to buy groceries tomorrow", source="user")
    rag_store.add("My favorite food is pizza", source="user")
    results = rag_store.search("what food do I like")
    assert results
    assert results[0]["text"] == "My favorite food is pizza"


def test_search_min_score_filters(rag_store):
    rag_store.add("completely unrelated topic about quantum physics", source="user")
    results = rag_store.search("what should I have for lunch", min_score=0.99)
    assert results == []


def test_recall_formats_snippets(rag_store):
    rag_store.add("Project deadline is Friday", source="note")
    ctx = rag_store.recall("when is the deadline")
    assert "[RECALLED CONTEXT" in ctx
    assert "Project deadline is Friday" in ctx


def test_recall_empty_returns_empty_string(rag_store):
    assert rag_store.recall("anything") == ""


def test_eviction_respects_max_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "RAG_STORE_PATH", tmp_path / "rag_store.json")
    monkeypatch.setattr(rag, "_FORCE_FALLBACK", True)
    monkeypatch.setattr(rag, "_MAX_DOCS", 3)
    rag._backend = None
    rag.reset()
    for i in range(5):
        rag.add(f"memory entry number {i} with distinct content", source="note")
    assert rag.count() == 3
    rag.add("doc number 0 with distinct content", source="note")   # was evicted → re-stored