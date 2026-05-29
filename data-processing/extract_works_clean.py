"""
Extract and normalize English Open Library works into a cleaned JSONL dataset.
"""

import argparse
import gzip
import json
import re
from typing import Iterable, Optional, Dict, Any, List
from collections import Counter

# Year validity range used in extract_year
YEAR_MIN = 1000
YEAR_MAX = 2025

# Weights used in get_popularity_score
EDITION_WEIGHT = 10
RATINGS_WEIGHT = 5
COVER_BONUS = 20

# Maximum number of subjects kept per book record
SUBJECT_LIMIT = 10

# Candidate over-fetch multiplier relative to the requested limit
CANDIDATE_MULTIPLIER = 5


def open_maybe_gzip(path: str) -> Iterable[str]:
    """Open a plain text or gzip-compressed file and yield lines."""
    if path.endswith(".gz"):
        f = gzip.open(path, "rt", encoding="utf-8", errors="ignore")
    else:
        f = open(path, "r", encoding="utf-8", errors="ignore")
    try:
        for line in f:
            yield line
    finally:
        f.close()


def extract_title_prefix(title: str) -> str:
    """
    Extract a single A–Z prefix character from a title.

    Used as a simple sharding key.
    """
    if not title:
        return "0"

    for ch in title.strip():
        if ch.isalpha() and "A" <= ch.upper() <= "Z":
            return ch.upper()

    return "0"


def extract_year(first_publish_date) -> Optional[int]:
    """Extract a four-digit year from a date-like string.

    Returns the year as an int if it falls within [YEAR_MIN, YEAR_MAX],
    otherwise returns None.
    """
    if not isinstance(first_publish_date, str):
        return None

    m = re.search(r"\d{4}", first_publish_date)
    if not m:
        return None

    try:
        year = int(m.group(0))
        if YEAR_MIN <= year <= YEAR_MAX:
            return year
    except ValueError:
        pass

    return None


def load_author_map(authors_dump_path: str, max_authors: int = 2_000_000) -> Dict[str, str]:
    """
    Build a mapping from author keys/ids to author names from the authors dump.

    Produces entries for both:
      "/authors/OL34184A" -> "Some Author Name"
      "OL34184A"          -> "Some Author Name"
    """
    author_map: Dict[str, str] = {}
    count = 0

    print("=" * 70)
    print(f"Loading authors from {authors_dump_path} ...")
    for line_num, line in enumerate(open_maybe_gzip(authors_dump_path), start=1):
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        json_str = parts[-1]
        try:
            author = json.loads(json_str)
        except json.JSONDecodeError:
            continue

        key = author.get("key")   # e.g. "/authors/OL10000507A"
        name = author.get("name")
        if not key or not name:
            continue

        # Full key
        author_map[key] = name

        # Short id form
        if key.startswith("/authors/"):
            short_id = key.split("/")[-1]
            author_map[short_id] = name

        count += 1

        if count >= max_authors:
            print(f"  Loaded {count:,} authors (limit reached)")
            break

        if count > 0 and count % 100_000 == 0:
            print(f"  Loaded {count:,} authors...")

    print(f"Author map ready with {len(author_map):,} entries.\n")
    return author_map


def extract_authors(work_json: dict, author_map: Dict[str, str]) -> List[dict]:
    """
    Normalize the authors field of a work to a list of:

        {"author_id": "...", "author_name": "..."}

    If a name cannot be resolved from the author dump, the id is used as fallback.
    """
    authors: List[dict] = []
    raw_authors = work_json.get("authors") or []

    for a in raw_authors:
        author_key: Optional[str] = None

        if isinstance(a, str):
            author_key = a
        elif isinstance(a, dict):
            if "key" in a and not author_key:
                author_key = a["key"]
            if "author" in a and isinstance(a["author"], dict):
                inner = a["author"]
                if "key" in inner and not author_key:
                    author_key = inner["key"]

        if not author_key:
            continue

        if isinstance(author_key, str) and author_key.startswith("/authors/"):
            author_id = author_key.split("/")[-1]
            full_key = author_key
        else:
            author_id = str(author_key)
            full_key = author_key

        author_name = author_map.get(full_key) or author_map.get(author_id) or author_id

        authors.append({
            "author_id": author_id,
            "author_name": author_name,
        })

    return authors


def extract_language(work_json: dict) -> str:
    """
    Extract a normalized language code from a work.

    Returns:
      - "en" for English
      - another code (e.g. "fre") if present
      - "unknown" if missing or malformed
    """
    langs = work_json.get("languages") or []
    if not langs:
        return "unknown"

    first = langs[0] if isinstance(langs, list) else {}
    if not isinstance(first, dict):
        return "unknown"

    key = first.get("key", "")
    code = key.split("/")[-1] if key else ""

    if code in ["eng", "en"]:
        return "en"

    return code or "unknown"


def is_english_book(work_json: dict) -> bool:
    """
    Decide whether a work should be treated as English.

    Primary signal:
      - language == "en"

    Fallback:
      - language == "unknown" and title starts with A–Z
    """
    lang = extract_language(work_json)
    if lang == "en":
        return True

    title = work_json.get("title", "")
    if title:
        first_char = title[0]
        if "A" <= first_char.upper() <= "Z" and lang == "unknown":
            return True

    return False


def get_popularity_score(work_json: dict) -> int:
    """Compute a simple popularity score for ranking candidates.

    Score = edition_count * EDITION_WEIGHT
           + ratings_count * RATINGS_WEIGHT
           + len(subjects)
           + COVER_BONUS if at least one cover exists.

    Non-integer edition_count or ratings_count fields contribute 0.
    """
    score = 0

    edition_count = work_json.get("edition_count", 0)
    if isinstance(edition_count, int):
        score += edition_count * EDITION_WEIGHT

    ratings = work_json.get("ratings_count", 0)
    if isinstance(ratings, int):
        score += ratings * RATINGS_WEIGHT

    subjects = work_json.get("subjects") or []
    score += len(subjects)

    if work_json.get("covers"):
        score += COVER_BONUS

    return score


def extract_description(work_json: dict) -> Optional[str]:
    """
    Extract a plain-text description from a work.

    The field may be:
      - a string
      - a dict with a "value" field
    """
    desc = work_json.get("description")
    if isinstance(desc, dict):
        return desc.get("value")
    if isinstance(desc, str):
        return desc
    return None


def extract_cover_id(work_json: dict) -> Optional[int]:
    """Extract the first cover id from a work, if present."""
    covers = work_json.get("covers") or []
    if isinstance(covers, list) and covers:
        first = covers[0]
        if isinstance(first, int):
            return first
    return None


def process_works_dump(
    input_path: str,
    authors_path: str,
    output_path: str,
    limit: int = 50000,
) -> None:
    """
    Main pipeline:

      1. Load author name mapping.
      2. Scan the works dump and collect English candidates with a basic filter.
      3. Sort candidates by a popularity score.
      4. Apply stricter "clean" filters and emit up to `limit` books
         in the final JSONL schema.
    """
    print("=" * 70)
    print("OPEN LIBRARY WORKS EXTRACTOR")
    print("=" * 70)
    print(f"Input works:   {input_path}")
    print(f"Input authors: {authors_path}")
    print(f"Output:        {output_path}")
    print(f"Target:        {limit:,} English books (clean)")
    print("Filter:        English only, A-Z titles, clean authors/desc/subjects")
    print("Sort:          By popularity (edition count, ratings)")
    print()

    author_map = load_author_map(authors_path)

    # Pass 1: collect candidates with basic filters
    print("Pass 1: Collecting and scoring English books...")
    candidates: List[Dict[str, Any]] = []

    for line_num, line in enumerate(open_maybe_gzip(input_path), start=1):
        line = line.rstrip("\n")
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        type_col = parts[0].strip()
        if "/type/work" not in type_col:
            continue

        json_str = parts[-1]

        try:
            work = json.loads(json_str)
        except json.JSONDecodeError:
            continue

        if not is_english_book(work):
            continue

        title = work.get("title") or work.get("full_title")
        if not title or not isinstance(title, str):
            continue

        key = work.get("key")
        if not key:
            continue

        authors = extract_authors(work, author_map)
        if not authors:
            continue

        title_prefix = extract_title_prefix(title)
        if title_prefix not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            continue

        popularity = get_popularity_score(work)

        candidates.append({
            "work": work,
            "key": key,
            "title": title,
            "authors": authors,
            "title_prefix": title_prefix,
            "popularity": popularity,
        })

        if len(candidates) % 10_000 == 0:
            print(f"  Collected: {len(candidates):,} basic-filtered books (line {line_num:,})")

        if len(candidates) >= limit * CANDIDATE_MULTIPLIER:
            print(f"  Enough candidates collected ({len(candidates):,})")
            break

    print(f"\nPass 1 complete: {len(candidates):,} English books collected (basic filters)")

    if len(candidates) < limit:
        print(f"WARNING: Only found {len(candidates):,} basic candidates, less than target {limit:,}")

    # Pass 2: sort by popularity
    print(f"\nPass 2: Sorting by popularity and selecting up to {limit:,} clean books...")
    candidates.sort(key=lambda x: x["popularity"], reverse=True)

    # Pass 3: apply "clean" filters and write final JSONL
    print(f"\nPass 3: Writing clean books to {output_path}...")
    count_written = 0
    written_prefixes: List[str] = []

    with open(output_path, "w", encoding="utf-8") as out_f:
        for item in candidates:
            if count_written >= limit:
                break

            work = item["work"]
            authors = item["authors"]

            # Require all authors to have a resolved name
            all_real_authors = all(
                a.get("author_name") and a["author_name"] != a["author_id"]
                for a in authors
            )
            if not all_real_authors:
                continue

            description = extract_description(work)
            if not description:
                continue

            subjects = [
                s for s in (work.get("subjects") or [])
                if isinstance(s, str)
            ][:SUBJECT_LIMIT]
            if not subjects:
                continue

            raw_key = item["key"]
            if isinstance(raw_key, str) and raw_key.startswith("/works/"):
                book_id = raw_key.split("/")[-1]
            else:
                book_id = raw_key

            cover_id = extract_cover_id(work)

            simplified: Dict[str, Any] = {
                "book_id": book_id,
                "title": item["title"],
                "title_prefix": item["title_prefix"],
                "title_lower": item["title"].lower(),
                "authors": authors,
                "isbn_13": work.get("isbn_13") or [],
                "first_publish_year": extract_year(work.get("first_publish_date")),
                "subjects": subjects,
                "language": "en",
                "description": description,
                "avg_rating": 0.0,
                "rating_count": 0,
            }

            if cover_id is not None:
                simplified["cover_id"] = cover_id

            out_f.write(json.dumps(simplified, ensure_ascii=False) + "\n")
            count_written += 1
            written_prefixes.append(item["title_prefix"])

            if count_written % 5_000 == 0:
                print(f"  Written clean books: {count_written:,}")

    print(f"\nCOMPLETE: {count_written:,} clean books written to {output_path}")
    if count_written < limit:
        print(f"WARNING: Only {count_written:,} books passed clean filters (target was {limit:,}).")

    print("\n" + "=" * 70)
    print("STATISTICS (CLEAN BOOKS)")
    print("=" * 70)

    if written_prefixes:
        prefix_dist = Counter(written_prefixes)
        print("\nTitle Prefix Distribution:")
        for prefix in sorted(prefix_dist.keys()):
            count = prefix_dist[prefix]
            percentage = (count / len(written_prefixes)) * 100
            bar = "█" * int(percentage / 2)
            print(f"  {prefix}: {count:>5,} ({percentage:>5.1f}%) {bar}")
    else:
        print("No clean books written; prefix distribution not available.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract and normalize English works from an Open Library dump."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input works dump file (e.g., ol_dump_works_2025-09-30.txt.gz)",
    )
    parser.add_argument(
        "--authors",
        required=True,
        help="Authors dump file (e.g., ol_dump_authors_latest.txt.gz)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSONL file (e.g., books_english_50k.jsonl)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50000,
        help="Maximum number of clean books to extract (default: 50000)",
    )

    args = parser.parse_args()
    process_works_dump(args.input, args.authors, args.output, args.limit)


if __name__ == "__main__":
    main()