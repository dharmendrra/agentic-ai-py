from retrieval.app.books_catalog import group_by_title, display_titles


def test_group_by_title_collapses_same_title():
    books = [
        {"_id": "a", "title": "Sex And The City"},
        {"_id": "b", "title": "sex and the city"},
        {"_id": "c", "title": "Game Of Thrones"},
    ]
    grouped = group_by_title(books)
    assert set(grouped.keys()) == {"sex and the city", "game of thrones"}
    assert grouped["sex and the city"] == ["a", "b"]
    assert grouped["game of thrones"] == ["c"]


def test_group_by_title_skips_blank_titles_and_ids():
    assert group_by_title([{"_id": "a", "title": ""}]) == {}
    assert group_by_title([{"title": "No Id"}]) == {"no id": []}


def test_display_titles_distinct_first_seen_casing():
    books = [
        {"_id": "a", "title": "Dune"},
        {"_id": "b", "title": "dune"},
        {"_id": "c", "title": "Dune Messiah"},
    ]
    assert display_titles(books) == ["Dune", "Dune Messiah"]
