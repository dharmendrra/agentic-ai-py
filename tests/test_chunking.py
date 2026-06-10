from retrieval.app.chunking import split_text, _recursive_split, _SEPARATORS


def test_empty_returns_empty():
    assert split_text("", 100, 10) == []
    assert split_text("   ", 100, 10) == []


def test_overlap_must_be_smaller():
    import pytest

    with pytest.raises(ValueError):
        split_text("hello world", 10, 10)


def test_short_text_single_chunk():
    chunks = split_text("hello world", 100, 10)
    assert chunks == ["hello world"]


def test_long_text_splits_into_multiple():
    text = "para one is here.\n\n" + ("word " * 400)
    chunks = split_text(text, 200, 40)
    assert len(chunks) > 1
    # No chunk should be drastically larger than chunk_size for word-splittable text.
    assert all(len(c) <= 400 for c in chunks)


def test_builtin_recursive_splitter_directly():
    text = ("a" * 50 + "\n\n" + "b" * 50 + "\n\n" + "c" * 50)
    chunks = _recursive_split(text, 60, 10, _SEPARATORS)
    assert len(chunks) >= 2
    joined = "".join(chunks)
    assert "a" in joined and "b" in joined and "c" in joined


def test_no_overlap():
    text = " ".join(f"w{i}" for i in range(50))
    chunks = _recursive_split(text, 30, 0, _SEPARATORS)
    assert len(chunks) > 1
