"""PDF text extraction via pypdf.

Returns a list of ``(page_number, text)`` tuples (1-indexed pages).
"""
from __future__ import annotations

import io
from typing import List, Tuple

from pypdf import PdfReader


def extract_pages(data: bytes) -> List[Tuple[int, str]]:
    """Extract text per page from raw PDF bytes.

    Pages with no extractable text are skipped (scanned/image-only PDFs yield
    empty strings). Page numbers are 1-indexed to match human expectations.
    """
    reader = PdfReader(io.BytesIO(data))
    pages: List[Tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append((idx, text))
    return pages
