"""Recursive character text splitting (size + overlap).

Pure logic — unit tested. We ship a small self-contained recursive splitter so
the pipeline works without langchain installed; if langchain-text-splitters is
present it is used for parity with the wider ecosystem.
"""
from __future__ import annotations

from typing import List

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Split ``text`` into overlapping chunks of roughly ``chunk_size`` chars.

    Tries langchain's RecursiveCharacterTextSplitter first; falls back to the
    built-in splitter below. Both honour separators and overlap.
    """
    text = text.strip()
    if not text:
        return []
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=_SEPARATORS,
        )
        return [c for c in splitter.split_text(text) if c.strip()]
    except ImportError:
        return _recursive_split(text, chunk_size, chunk_overlap, _SEPARATORS)


def _recursive_split(
    text: str, chunk_size: int, chunk_overlap: int, separators: List[str]
) -> List[str]:
    """Self-contained recursive splitter mirroring langchain's algorithm."""
    final_chunks: List[str] = []

    # Choose the first separator that appears in the text (or the last = "").
    separator = separators[-1]
    next_separators: List[str] = []
    for i, sep in enumerate(separators):
        if sep == "":
            separator = sep
            break
        if sep in text:
            separator = sep
            next_separators = separators[i + 1 :]
            break

    splits = list(text) if separator == "" else text.split(separator)

    good_splits: List[str] = []
    for s in splits:
        if len(s) < chunk_size:
            good_splits.append(s)
        else:
            if good_splits:
                final_chunks.extend(
                    _merge_splits(good_splits, separator, chunk_size, chunk_overlap)
                )
                good_splits = []
            if not next_separators:
                final_chunks.append(s)
            else:
                final_chunks.extend(
                    _recursive_split(s, chunk_size, chunk_overlap, next_separators)
                )
    if good_splits:
        final_chunks.extend(
            _merge_splits(good_splits, separator, chunk_size, chunk_overlap)
        )
    return [c for c in final_chunks if c.strip()]


def _merge_splits(
    splits: List[str], separator: str, chunk_size: int, chunk_overlap: int
) -> List[str]:
    """Greedily merge small splits into chunks <= chunk_size, with overlap."""
    sep_len = len(separator)
    docs: List[str] = []
    current: List[str] = []
    total = 0
    for s in splits:
        s_len = len(s)
        added = s_len + (sep_len if current else 0)
        if total + added > chunk_size and current:
            docs.append(separator.join(current).strip())
            # drop from the front to honour overlap
            while total > chunk_overlap and current:
                removed = current.pop(0)
                total -= len(removed) + (sep_len if current else 0)
        current.append(s)
        total += added
    if current:
        docs.append(separator.join(current).strip())
    return [d for d in docs if d]
