from extract_works_loose import (
    extract_title_prefix, extract_year, extract_language,
    get_popularity_score, extract_authors, is_english_book,
)


def test_title_prefix_alpha_and_fallback():
    assert extract_title_prefix("Deep Work") == "D"
    assert extract_title_prefix("  the great gatsby") == "T"
    assert extract_title_prefix("123 numbers") == "N"  # scans forward; first alpha char is 'n' -> "N"
    assert extract_title_prefix("") == "0"


def test_extract_year_bounds_and_regex():
    assert extract_year("2009") == 2009
    assert extract_year("June 20, 2018") == 2018
    assert extract_year("3025") is None      # > 2025
    assert extract_year("999") is None        # < 1000
    assert extract_year(None) is None
    assert extract_year(2009) is None          # non-str input


def test_extract_language_normalizes_english():
    assert extract_language({"languages": [{"key": "/languages/eng"}]}) == "en"
    assert extract_language({"languages": [{"key": "/languages/en"}]}) == "en"
    assert extract_language({"languages": [{"key": "/languages/fre"}]}) == "fre"
    assert extract_language({}) == "unknown"


def test_popularity_score_weights():
    work = {"edition_count": 3, "ratings_count": 4,
            "subjects": ["a", "b"], "covers": [123]}
    # 3*10 + 4*5 + 2 + 20
    assert get_popularity_score(work) == 72
    assert get_popularity_score({}) == 0


def test_extract_authors_fallback_to_id():
    amap = {"OL1A": "Jane Doe"}
    works = {"authors": [{"author": {"key": "/authors/OL1A"}},
                         {"author": {"key": "/authors/OL2A"}}]}
    out = extract_authors(works, amap)
    assert out[0] == {"author_id": "OL1A", "author_name": "Jane Doe"}
    assert out[1] == {"author_id": "OL2A", "author_name": "OL2A"}  # fallback to id


def test_is_english_book_unknown_lang_alpha_title():
    assert is_english_book({"languages": [{"key": "/languages/eng"}]}) is True
    assert is_english_book({"title": "Apple"}) is True   # unknown lang + A-Z title
    assert is_english_book({"languages": [{"key": "/languages/fre"}], "title": "Le"}) is False
