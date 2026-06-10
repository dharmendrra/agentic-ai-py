from retrieval.app.ingest import build_records, _slug


def test_slug():
    assert _slug("Pride and Prejudice") == "pride-and-prejudice"
    assert _slug("") == "book"


def test_build_records_metadata_and_chunk_index():
    pages = [(1, "word " * 300), (2, "more " * 300)]
    records = build_records(pages, "My Book", "sfid1234abcd", chunk_size=200, chunk_overlap=20)
    assert len(records) > 2
    # chunk_index is a running counter across the whole document
    indices = [r["metadata"]["chunk_index"] for r in records]
    assert indices == list(range(len(records)))
    # each record carries the aligned metadata
    for r in records:
        md = r["metadata"]
        assert md["book_title"] == "My Book"
        assert md["source_file_id"] == "sfid1234abcd"
        assert md["page_number"] in (1, 2)
        assert md["text_content"] == r["text"]
        assert r["id"].startswith("my-book-")


def test_build_records_empty_pages():
    assert build_records([], "X", "sfid", 100, 10) == []
