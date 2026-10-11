"""Unit tests for the chunking logic (pure function, no DB)."""
from app.rag.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("", 100, 10) == []


def test_short_text_is_one_chunk():
    assert chunk_text("hello world", 100, 10) == ["hello world"]


def test_long_text_is_split():
    text = "a" * 250
    chunks = chunk_text(text, 100, 0)
    assert len(chunks) == 3  # 100 + 100 + 50


def test_overlap_repeats_boundary_text():
    text = "0123456789" * 3  # 30 chars
    chunks = chunk_text(text, 10, 5)
    # With overlap the step is 5, so chunks share characters.
    assert len(chunks) > 3
    assert chunks[0][-5:] == chunks[1][:5]
