"""
Update avg_rating and rating_count in a books JSONL file using an Open Library
rating dump, and select the top-N most popular books by rating.

Example:

    python3 update_book_ratings.py \
        --ratings   ol_ratings_dump.txt \
        --books-in  books_english_150k.jsonl \
        --books-out books_english_top50k_with_ratings.jsonl \
        --limit     50000
"""

import argparse
import gzip
import json
from typing import Iterable, Dict, Tuple, List
from collections import defaultdict

# Valid rating range; entries outside this range are discarded as invalid
RATING_MIN = 0.5
RATING_MAX = 5.0


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


def load_ratings(ratings_path: str) -> Tuple[Dict[str, float], Dict[str, int]]:
    """
    Aggregate ratings per work from the rating dump.

    Expected input format per line (tab-separated):

        /works/OL1629179W    /books/OL22981670M    5    2018-06-20

    Returns:
      - sum_ratings[work_id]   : sum of all ratings for that work
      - count_ratings[work_id] : number of rating entries for that work
    """
    sum_ratings: Dict[str, float] = defaultdict(float)
    count_ratings: Dict[str, int] = defaultdict(int)

    print("=" * 70)
    print(f"Loading ratings from {ratings_path} ...")

    line_count = 0
    used_count = 0

    for line in open_maybe_gzip(ratings_path):
        line_count += 1
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        work_col = parts[0].strip()
        if not work_col.startswith("/works/"):
            continue

        work_id = work_col.split("/")[-1]  # "/works/OL1629179W" -> "OL1629179W"
        rating_str = parts[2].strip()

        try:
            rating = float(rating_str)
        except ValueError:
            continue

        # Discard obviously invalid ratings
        if rating < RATING_MIN or rating > RATING_MAX:
            continue

        sum_ratings[work_id] += rating
        count_ratings[work_id] += 1
        used_count += 1

        if used_count % 100_000 == 0:
            print(f"  Aggregated {used_count:,} ratings...")

    print(f"Done. Read {line_count:,} lines, used {used_count:,} ratings.")
    print(f"Unique works with ratings: {len(sum_ratings):,}\n")
    return sum_ratings, count_ratings


def update_and_select_top_books(
        books_in: str,
        books_out: str,
        sum_ratings: Dict[str, float],
        count_ratings: Dict[str, int],
        limit: int,
) -> None:
    """
    Load all books from `books_in`, attach rating_count / avg_rating from the
    rating aggregates, sort by rating popularity, and write the top-N books.

    Sort criteria (descending):
      1) has_rating   (rating_count > 0)
      2) rating_count
      3) avg_rating
    """
    print("=" * 70)
    print("Updating books with ratings and selecting TOP books...")
    print(f"Input books:   {books_in}")
    print(f"Output books:  {books_out}")
    print(f"Top-N limit:   {limit}")
    print()

    books: List[dict] = []
    in_count = 0
    updated_count = 0

    # Load all books into memory and enrich with ratings
    with open(books_in, "r", encoding="utf-8") as f_in:
        for line in f_in:
            in_count += 1
            line = line.strip()
            if not line:
                continue

            try:
                book = json.loads(line)
            except json.JSONDecodeError:
                continue

            book_id = book.get("book_id") or book.get("key")
            if not book_id:
                # Skip malformed records without an id
                continue

            if book_id in count_ratings:
                c = count_ratings[book_id]
                s = sum_ratings[book_id]
                avg = s / c if c > 0 else 0.0

                book["rating_count"] = c
                book["avg_rating"] = round(avg, 3)
                updated_count += 1
            else:
                # Ensure rating fields exist, even if there are no ratings
                book.setdefault("rating_count", 0)
                book.setdefault("avg_rating", 0.0)

            books.append(book)

    print(f"Done reading books. Total books loaded: {len(books):,}")
    print(f"Books with non-zero ratings: {updated_count:,}\n")

    if not books:
        print("No books loaded. Nothing to write.")
        return

    # Sort key: has_rating, rating_count, avg_rating (all descending)
    def sort_key(b: dict):
        """Return a tuple used as the descending sort key for a book.

        Priority order (highest first):
          1. has_rating  — books with any ratings before unrated books
          2. rating_count — more ratings first
          3. avg_rating   — higher average rating first
        """
        rc = b.get("rating_count", 0)
        ar = b.get("avg_rating", 0.0)
        has_rating = 1 if rc > 0 else 0
        return (has_rating, rc, ar)

    print("Sorting books by rating_count and avg_rating ...")
    books_sorted = sorted(books, key=sort_key, reverse=True)

    # Keep only the top-N records
    top_n = books_sorted[:limit] if limit > 0 else books_sorted
    print(f"Selected top {len(top_n):,} books (limit = {limit:,}).")

    # Write JSONL output
    with open(books_out, "w", encoding="utf-8") as f_out:
        for b in top_n:
            f_out.write(json.dumps(b, ensure_ascii=False) + "\n")

    print(f"\nDone. Wrote {len(top_n):,} books to {books_out}.")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update avg_rating and rating_count in a books JSONL file "
                    "using an Open Library rating dump, and select the top-N books."
    )
    parser.add_argument(
        "--ratings",
        required=True,
        help="Rating dump file (e.g., ol_ratings_dump.txt or .gz)",
    )
    parser.add_argument(
        "--books-in",
        required=True,
        help="Input books JSONL file (e.g., books_english_150k.jsonl)",
    )
    parser.add_argument(
        "--books-out",
        required=True,
        help="Output books JSONL file (e.g., books_english_top50k_with_ratings.jsonl)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50000,
        help="Number of top books to keep (default: 50000)",
    )

    args = parser.parse_args()

    sum_ratings, count_ratings = load_ratings(args.ratings)
    update_and_select_top_books(
        args.books_in,
        args.books_out,
        sum_ratings,
        count_ratings,
        args.limit,
    )


if __name__ == "__main__":
    main()